#!/usr/bin/env python3
"""
快速同步脚本 - 本地数据准备，一次性写入
大幅减少API调用次数，提高同步速度
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FastSync:
    """快速同步引擎"""
    
    def __init__(self, base_adapter, data_dictionary: Optional[Dict[str, Any]] = None, max_concurrent: int = 10):
        self.base = base_adapter
        self.source_data = {}
        self.target_data = {}
        self.batch_operations = defaultdict(list)
        self.data_dictionary = data_dictionary or {}
        self.max_concurrent = max_concurrent
        self.semaphore = None
        
    async def load_all_data(self, sync_rules):
        """分阶段加载数据，区分源表和目标表"""
        # 收集所有表名
        source_tables = set(rule['source_table'] for rule in sync_rules if rule.get('should_run', True))
        target_tables = set(rule['target_table'] for rule in sync_rules if rule.get('should_run', True))
        all_tables = source_tables | target_tables
        
        logger.info(f"开始加载 {len(all_tables)} 个表的数据...")
        
        # 初始化信号量控制并发
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 并行加载但限制并发数
        tasks = []
        for table_name in all_tables:
            task = self._load_table_data_with_semaphore(table_name)
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        logger.info("所有数据加载完成")
        
        # 记录加载的数据统计
        total_rows = sum(len(rows) for rows in self.source_data.values()) + sum(len(rows) for rows in self.target_data.values())
        logger.info(f"总计加载数据行数: {total_rows}")
    
    async def _load_table_data_with_semaphore(self, table_name):
        """使用信号量控制的表数据加载"""
        async with self.semaphore:
            await self._load_table_data(table_name)
    
    async def _load_table_data(self, table_name):
        """加载单个表数据，区分源数据和目标数据，支持特殊数据源"""
        try:
            # 检查是否是特殊的配置数据源
            if table_name in ['config', 'data_dictionary', 'json_config']:
                # 从数据字典创建虚拟数据行
                rows = self._create_config_rows(table_name)
                logger.info(f"从配置创建虚拟表 '{table_name}': {len(rows)} 行")
            else:
                # 正常加载数据库表
                rows = await self.base.get_rows(table_name, '默认视图')
                logger.info(f"加载表 '{table_name}': {len(rows)} 行")
            
            # 为源数据和目标数据分别存储，避免相互影响
            if table_name not in self.source_data:
                self.source_data[table_name] = rows.copy()
            if table_name not in self.target_data:
                self.target_data[table_name] = rows.copy()
                
        except Exception as e:
            logger.error(f"加载表 '{table_name}' 失败: {e}")
            # 加载失败时初始化为空列表
            if table_name not in self.source_data:
                self.source_data[table_name] = []
            if table_name not in self.target_data:
                self.target_data[table_name] = []
    
    def _create_config_rows(self, table_name):
        """从数据字典创建虚拟数据行"""
        if not self.data_dictionary:
            logger.warning(f"数据字典为空，无法创建虚拟表 '{table_name}'")
            return []
        
        # 将数据字典的每个键值对转换为一行数据
        rows = []
        for key, value in self.data_dictionary.items():
            row = {
                '键名': key,
                '键值': value,
                key: value  # 同时使用键名作为列名，方便直接引用
            }
            rows.append(row)
        
        logger.info(f"创建配置数据行: {rows}")
        return rows
    
    def prepare_operations(self, sync_rules):
        """准备所有操作，包括清空和更新操作"""
        logger.info("准备批量操作...")
        
        enabled_rules = [rule for rule in sync_rules if rule.get('should_run', True)]
        logger.info(f"已启用的同步规则: {len(enabled_rules)}/{len(sync_rules)}")
        
        # 预分析：找出将被完全清空（删除所有行）的表
        tables_to_be_cleared = set()
        for rule in enabled_rules:
            if rule.get('clear_before_sync', False) and rule.get('allow_insert', False):
                tables_to_be_cleared.add(rule['target_table'])
        
        if tables_to_be_cleared:
            logger.info(f"以下表将被完全清空: {list(tables_to_be_cleared)}")
        
        # 第一步：处理清空操作
        self._prepare_clear_operations(enabled_rules)
        
        # 第二步：处理同步操作
        for rule in enabled_rules:
            try:
                # 标记此表是否会被清空
                rule['_will_be_cleared'] = rule['target_table'] in tables_to_be_cleared
                self._process_rule(rule)
            except Exception as e:
                logger.error(f"处理规则失败 {rule.get('source_table', 'unknown')} -> {rule.get('target_table', 'unknown')}: {e}")
        
        total_ops = sum(len(ops) for ops in self.batch_operations.values())
        logger.info(f"准备完成，总操作数: {total_ops}")
    
    def _process_rule(self, rule):
        """处理单个规则"""
        source_table = rule['source_table']
        target_table = rule['target_table']
        source_keys = rule.get('source_keys', [])
        target_keys = rule.get('target_keys', [])
        allow_insert = rule.get('allow_insert', False)
        
        # 检查是否使用多字段映射
        if 'multi_field_mappings' in rule:
            logger.info(f"处理多字段映射规则: {source_table} -> {target_table}, {len(rule['multi_field_mappings'])}个字段映射")
            self._process_multi_field_rule(rule)
            return
        
        # 原有单字段映射处理逻辑
        source_fields = rule['source_fields']
        target_fields = rule['target_fields']
        conditions = rule.get('conditions', [])
        exclude_conditions = rule.get('exclude_conditions', [])
        factor = rule.get('factor', 1.0)
        aggregation = rule.get('aggregation', '')
        
        logger.info(f"处理规则: {source_table} -> {target_table}, 聚合模式: {aggregation}, 源字段: {source_fields}, 目标字段: {target_fields}")
        
        source_rows = self.source_data.get(source_table, [])
        target_rows = self.target_data.get(target_table, [])
        
        logger.info(f"数据统计: 源表'{source_table}' {len(source_rows)}行, 目标表'{target_table}' {len(target_rows)}行")
        
        if not source_rows:
            logger.warning(f"源表'{source_table}'没有数据，跳过处理")
            return
        
        # 如果目标表为空且不允许插入，则跳过
        if not target_rows and not allow_insert:
            logger.warning(f"目标表'{target_table}'为空且不允许插入，跳过处理")
            return
        
        # 过滤源数据
        filtered_source = []
        total_source = len(source_rows)
        
        # 对于底表规则，增加详细的过滤日志
        is_bottom_table = target_table.startswith('底表-')
        
        for row in source_rows:
            include = self._check_conditions(row, conditions)
            # 若满足排除条件则剔除
            if include and exclude_conditions:
                if self._check_conditions(row, exclude_conditions):
                    include = False
                    if is_bottom_table:
                        logger.debug(f"底表规则排除记录: {row.get('合同编号', 'N/A')}")
            if include:
                filtered_source.append(row)
            elif is_bottom_table and len(filtered_source) < 5:  # 只记录前5个未匹配的记录样例
                logger.debug(f"底表规则条件不匹配样例: 合同编号={row.get('合同编号', 'N/A')}, 验收总标识={row.get('验收总标识', 'N/A')}, 验收日={row.get('验收日', 'N/A')}")
        
        # 记录过滤结果
        logger.info(f"表 '{source_table}' 过滤: {len(filtered_source)}/{total_source} 行符合条件")
        
        if not filtered_source:
            logger.warning(f"表 '{source_table}' 没有符合条件的数据")
            return
        
        # 按主键分组源数据
        source_by_key = {}
        for row in filtered_source:
            if source_keys:
                # 构建源主键
                source_key_parts = []
                for key_field in source_keys:
                    source_key_parts.append(str(row.get(key_field, '')))
                source_key = '|'.join(source_key_parts)
                
                if source_key not in source_by_key:
                    source_by_key[source_key] = []
                source_by_key[source_key].append(row)
            else:
                # 如果没有主键，所有数据归为一组
                source_key = '__all__'
                if source_key not in source_by_key:
                    source_by_key[source_key] = []
                source_by_key[source_key].append(row)
        
        # 准备更新数据和插入数据
        updates = []
        updated_rows = []
        inserts = []
        
        # 如果目标表有数据，处理更新逻辑
        # 只有当前规则会删除所有行时才跳过更新逻辑
        clear_before_sync = rule.get('clear_before_sync', False)
        should_skip_updates = clear_before_sync and allow_insert
        if target_rows and not should_skip_updates:
            for target_row in target_rows:
                update = {}
                has_update = False
                
                # 构建目标主键
                target_key = '__all__'
                if target_keys:
                    target_key_parts = []
                    for key_field in target_keys:
                        target_key_parts.append(str(target_row.get(key_field, '')))
                    target_key = '|'.join(target_key_parts)
                
                # 获取对应的源数据
                source_rows_for_target = source_by_key.get(target_key, [])
                
                # broadcast模式特殊处理：当没有主键时，所有目标行都使用相同的源数据
                if aggregation == 'broadcast' and not target_keys and '__all__' in source_by_key:
                    source_rows_for_target = source_by_key['__all__']
                    logger.debug(f"broadcast模式: 源数据={len(source_rows_for_target)}行, 字段={source_fields}, 目标字段={target_fields}")
                
                if source_rows_for_target:
                    update, has_update = self._prepare_row_data(source_rows_for_target, aggregation, source_fields, target_fields, factor, rule)
                
                if has_update:
                    updates.append(update)
                    updated_rows.append(target_row)
        
        # 如果允许插入，处理插入逻辑
        logger.debug(f"插入检查: allow_insert={allow_insert}, source_by_key数量={len(source_by_key) if 'source_by_key' in locals() else 'undefined'}")
        if allow_insert:
            # 构建目标表现有主键集合（用于判断是否需要插入）
            existing_target_keys = set()
            if target_rows and target_keys:
                for target_row in target_rows:
                    target_key_parts = []
                    for key_field in target_keys:
                        target_key_parts.append(str(target_row.get(key_field, '')))
                    target_key = '|'.join(target_key_parts)
                    existing_target_keys.add(target_key)
            
            # 找出需要插入的源数据
            logger.debug(f"插入逻辑: target_table='{target_table}', should_skip_updates={should_skip_updates}, 源数据组数={len(source_by_key)}")
            for source_key, source_rows_for_key in source_by_key.items():
                # 如果有主键且该主键已存在于目标表，跳过插入
                # 但如果表将被完全清空，则插入所有数据
                if target_keys and source_key in existing_target_keys and not should_skip_updates:
                    logger.debug(f"跳过插入 '{target_table}': source_key={source_key} 已存在于目标表")
                    continue
                
                # broadcast模式的特殊处理：应该更新所有现有行，而不是插入新行
                # 但如果表将被完全清空，则忽略这个限制
                if not target_keys and target_rows and aggregation == 'broadcast' and not should_skip_updates:
                    continue
                
                # 准备插入数据
                insert_data, has_data = self._prepare_row_data(source_rows_for_key, aggregation, source_fields, target_fields, factor, rule)
                
                if has_data:
                    inserts.append(insert_data)
                    logger.debug(f"准备插入数据到 '{target_table}': {insert_data}")
                else:
                    logger.debug(f"源数据无效，跳过插入到 '{target_table}': source_key={source_key}")
        
        # 添加更新操作
        if updates:
            operation = {
                'type': 'update',
                'rows': updated_rows,
                'updates': updates
            }
            self.batch_operations[target_table].append(operation)
            logger.info(f"✓ 准备更新 '{source_table}' -> '{target_table}': {len(updates)} 行")
        else:
            logger.warning(f"✗ 没有生成更新操作 '{source_table}' -> '{target_table}'")
        
        # 添加插入操作
        logger.debug(f"插入操作检查: inserts数量={len(inserts)}")
        if inserts:
            operation = {
                'type': 'insert',
                'data': inserts
            }
            self.batch_operations[target_table].append(operation)
            logger.info(f"✓ 准备插入 '{source_table}' -> '{target_table}': {len(inserts)} 行")
        else:
            logger.warning(f"✗ 没有生成插入操作 '{source_table}' -> '{target_table}'")
    
    def _process_multi_field_rule(self, rule):
        """处理多字段映射规则"""
        source_table = rule['source_table']
        target_table = rule['target_table']
        source_keys = rule.get('source_keys', [])
        target_keys = rule.get('target_keys', [])
        allow_insert = rule.get('allow_insert', False)
        multi_field_mappings = rule['multi_field_mappings']
        
        source_rows = self.source_data.get(source_table, [])
        target_rows = self.target_data.get(target_table, [])
        
        logger.info(f"数据统计: 源表'{source_table}' {len(source_rows)}行, 目标表'{target_table}' {len(target_rows)}行")
        
        if not source_rows:
            logger.warning(f"源表'{source_table}'没有数据，跳过处理")
            return
            
        # 如果目标表为空且不允许插入，则跳过
        if not target_rows and not allow_insert:
            logger.warning(f"目标表'{target_table}'为空且不允许插入，跳过处理")
            return
        
        # 按键分组源数据
        source_groups = defaultdict(list)
        if source_keys:
            # 有主键时，按键分组
            for row in source_rows:
                key = tuple(str(row.get(k, '')) for k in source_keys)
                source_groups[key].append(row)
        else:
            # 无主键时，使用行索引作为键，每行对应自己
            for i, row in enumerate(source_rows):
                source_groups[i] = [row]
        
        # 按键分组目标数据
        target_groups = {}
        if target_keys:
            # 有主键时，按键分组
            for row in target_rows:
                key = tuple(str(row.get(k, '')) for k in target_keys)
                target_groups[key] = row
        else:
            # 无主键时，使用行索引作为键，确保每行都能被处理
            for i, row in enumerate(target_rows):
                target_groups[i] = row
        
        # 批量收集更新和插入操作
        updates = []
        updated_rows = []
        inserts = []
        processed_target_keys = set()
        
        # 处理每个源数据分组
        for source_key, source_rows_for_key in source_groups.items():
            target_key = source_key  # 假设源键和目标键结构相同
            target_row = target_groups.get(target_key)
            
            if target_row is None:
                if allow_insert:
                    # 创建新行
                    new_row = {}
                    if source_keys and target_keys:
                        for i, target_key_field in enumerate(target_keys):
                            if i < len(source_keys):
                                new_row[target_key_field] = source_rows_for_key[0].get(source_keys[i], '')
                    
                    # 处理每个字段映射
                    for mapping in multi_field_mappings:
                        field_value = self._calculate_multi_field_value(source_rows_for_key, mapping)
                        new_row[mapping['target_field']] = field_value
                    
                    inserts.append(new_row)
                    logger.debug(f"新增记录: {new_row}")
            else:
                # 更新现有行
                update_data = {}
                has_update = False
                
                # 处理每个字段映射
                for mapping in multi_field_mappings:
                    field_value = self._calculate_multi_field_value(source_rows_for_key, mapping)
                    if field_value is not None:
                        current_value = target_row.get(mapping['target_field'])
                        # 对于数值类型，比较时转换为float
                        if isinstance(field_value, (int, float)) and current_value is not None:
                            try:
                                if abs(float(field_value) - float(current_value)) > 0.001:
                                    update_data[mapping['target_field']] = field_value
                                    has_update = True
                            except (ValueError, TypeError):
                                if field_value != current_value:
                                    update_data[mapping['target_field']] = field_value
                                    has_update = True
                        elif field_value != current_value:
                            update_data[mapping['target_field']] = field_value
                            has_update = True
                
                if has_update:
                    updates.append(update_data)
                    updated_rows.append(target_row)
                    logger.debug(f"更新记录 ID={target_row.get('_id')}: {update_data}")
                
                processed_target_keys.add(target_key)
        
        # 添加批量更新操作
        if updates:
            operation = {
                'type': 'update',
                'rows': updated_rows,
                'updates': updates
            }
            self.batch_operations[target_table].append(operation)
            logger.info(f"✓ 准备多字段更新 '{source_table}' -> '{target_table}': {len(updates)} 行")
        else:
            logger.warning(f"✗ 没有生成多字段更新操作 '{source_table}' -> '{target_table}'")
        
        # 添加批量插入操作
        if inserts:
            operation = {
                'type': 'insert',
                'data': inserts
            }
            self.batch_operations[target_table].append(operation)
            logger.info(f"✓ 准备多字段插入 '{source_table}' -> '{target_table}': {len(inserts)} 行")
        else:
            logger.debug(f"没有生成多字段插入操作 '{source_table}' -> '{target_table}'")
        
        logger.info(f"多字段映射规则处理完成，更新了 {len(processed_target_keys)} 个目标记录")
    
    def _calculate_multi_field_value(self, source_rows, mapping):
        """计算多字段映射的值"""
        source_field = mapping['source_field']
        aggregation = mapping.get('aggregation', '')
        conditions = mapping.get('conditions', [])
        exclude_conditions = mapping.get('exclude_conditions', [])
        factor = mapping.get('factor', 1.0)
        
        # 过滤符合条件的源数据
        filtered_rows = []
        for row in source_rows:
            include = self._check_conditions(row, conditions) if conditions else True
            # 检查排除条件
            if include and exclude_conditions:
                if self._check_conditions(row, exclude_conditions):
                    include = False
            if include:
                filtered_rows.append(row)
        
        # 添加调试日志
        logger.info(f"调试: 字段={source_field}, 聚合={aggregation}, 源数据行数={len(source_rows)}, 过滤后行数={len(filtered_rows)}")
        if conditions:
            logger.info(f"调试: 条件={conditions}")
        if len(filtered_rows) > 0:
            sample_row = filtered_rows[0]
            logger.info(f"调试: 样本数据 - 项目类型={sample_row.get('项目类型')}, 工时数={sample_row.get('工时数')}, {source_field}={sample_row.get(source_field)}")
        
        if not filtered_rows:
            return 0 if aggregation == 'sum' else None
        
        if aggregation == 'sum':
            total = 0
            for row in filtered_rows:
                value = row.get(source_field, 0)
                try:
                    total += float(value or 0)
                except (ValueError, TypeError):
                    logger.warning(f"无法转换为数值: {value}")
            return total * factor
        elif aggregation == 'latest':
            # 返回最新的非空值
            for row in reversed(filtered_rows):
                value = row.get(source_field)
                if value is not None and str(value).strip() != '':
                    return value
            return None
        elif aggregation == 'firstPart':
            # 取分隔符前内容
            value = filtered_rows[0].get(source_field, '') if filtered_rows else ''
            if value:
                separators = [',', '，', ';', '；', '|', '/', '\\']
                str_value = str(value)
                first_index = len(str_value)
                for sep in separators:
                    index = str_value.find(sep)
                    if index != -1 and index < first_index:
                        first_index = index
                if first_index < len(str_value):
                    return str_value[:first_index].strip()
            return str(value) if value else ''
        elif aggregation == 'conditional_concat':
            # 条件拼接 - 如果条件满足则拼接指定字段
            if filtered_rows:
                concat_fields = mapping.get('concat_fields', [])
                parts = []
                for field in concat_fields:
                    # 如果字段存在于源数据中，使用字段值；否则作为常量
                    val = filtered_rows[0].get(field, field)
                    if val is not None and str(val).strip():
                        parts.append(str(val))
                return ''.join(parts)
            return ''
        elif aggregation == 'year_if':
            # 条件提取年份
            if filtered_rows:
                date_value = filtered_rows[0].get(source_field)
                if date_value:
                    try:
                        # 尝试解析日期
                        parsed_date = self._try_parse_datetime(date_value)
                        if parsed_date:
                            return parsed_date.year
                    except Exception as e:
                        logger.warning(f"解析日期失败 {date_value}: {e}")
            return None
        elif aggregation == 'month_if':
            # 提取月份（几月）
            if filtered_rows:
                date_value = filtered_rows[0].get(source_field)
                if date_value:
                    try:
                        parsed_date = self._try_parse_datetime(date_value)
                        if parsed_date:
                            return f"{parsed_date.month}月"
                    except Exception as e:
                        logger.warning(f"解析日期失败 {date_value}: {e}")
            return ''
        elif aggregation == 'date_year_month':
            # 提取年月（如202403）
            if filtered_rows:
                date_value = filtered_rows[0].get(source_field)
                if date_value:
                    try:
                        parsed_date = self._try_parse_datetime(date_value)
                        if parsed_date:
                            month = f"{parsed_date.month:02d}"  # 月份补零
                            return f"{parsed_date.year}{month}"
                    except Exception as e:
                        logger.warning(f"解析日期失败 {date_value}: {e}")
            return ''
        elif aggregation == 'math_expression':
            # 数学表达式计算
            if filtered_rows:
                expression = mapping.get('math_expression', '')
                if expression:
                    try:
                        # 安全的表达式计算
                        result = self._evaluate_math_expression(expression, filtered_rows[0])
                        if result is not None:
                            return result * factor
                    except Exception as e:
                        logger.warning(f"数学表达式计算失败 {expression}: {e}")
            return 0
        elif aggregation == 'string_replace':
            # 字符串替换
            if filtered_rows:
                value = filtered_rows[0].get(source_field, '')
                replace_mappings = mapping.get('replace_mappings', {})
                result = str(value)
                for old_val, new_val in replace_mappings.items():
                    if old_val in result:
                        result = result.replace(old_val, new_val)
                return result
            return ''
        else:
            # 默认返回第一个值
            return filtered_rows[0].get(source_field) if filtered_rows else None
    
    def _prepare_row_data(self, source_rows_for_target, aggregation, source_fields, target_fields, factor, rule):
        """准备行数据，用于更新或插入"""
        update = {}
        has_update = False
        
        if aggregation == 'broadcast':
            # 广播模式：需要找到包含所需字段的行
            source_row = None
            for row in source_rows_for_target:
                # 检查这一行是否包含我们需要的字段
                if all(field in row and row[field] is not None and str(row[field]).strip() != '' for field in source_fields):
                    source_row = row
                    break
            
            # 如果没找到合适的行，尝试查找包含字段的任意行
            if source_row is None:
                for row in source_rows_for_target:
                    if any(field in row for field in source_fields):
                        source_row = row
                        break
            
            # 最后备选使用第一行
            if source_row is None:
                source_row = source_rows_for_target[0]
            
            logger.info(f"broadcast模式更新: 选中源行={source_row}")
            for i, source_field in enumerate(source_fields):
                if i < len(target_fields):
                    value = source_row.get(source_field, '')
                    update[target_fields[i]] = value
                    has_update = True
                    logger.info(f"broadcast字段映射: {source_field}='{value}' -> {target_fields[i]}")
        
        elif aggregation == 'sum':
            # 求和模式
            total = 0
            for row in source_rows_for_target:
                value = row.get(source_fields[0], 0)
                if isinstance(value, (int, float)):
                    total += value
            total *= factor
            
            if len(target_fields) > 0:
                update[target_fields[0]] = total
                has_update = True
        
        elif aggregation == 'latest':
            # 最新记录模式
            latest_row = self._get_latest_record(source_rows_for_target, rule)
            if latest_row:
                for i, source_field in enumerate(source_fields):
                    if i < len(target_fields):
                        value = latest_row.get(source_field, '')
                        update[target_fields[i]] = value
                        has_update = True
        
        else:
            # 普通模式
            source_row = source_rows_for_target[0]
            for i, source_field in enumerate(source_fields):
                if i < len(target_fields):
                    value = source_row.get(source_field, '')
                    if isinstance(value, (int, float)) and factor != 1.0:
                        value = value * factor
                    update[target_fields[i]] = value
                    has_update = True
        
        return update, has_update
    
    def _check_conditions(self, row, conditions):
        """检查条件，支持变量解析和日期/数值比较"""
        if not conditions:
            return True
            
        for condition in conditions:
            field = condition.get('field', '')
            op = condition.get('op', '=')
            raw_value = condition.get('value', '')

            field_value = row.get(field, '')
            if field_value is None:
                field_value = ''

            # 解析数据字典变量（如 {报表截止时间}）
            comp_value = self._resolve_variable(raw_value)

            # 执行比较
            result = self._compare_with_operator(field_value, comp_value, op)
            
            # 添加调试日志
            if not result:
                logger.debug(f"条件不匹配: {field}='{field_value}' (type:{type(field_value)}) {op} '{comp_value}' (type:{type(comp_value)})")
            
            if not result:
                return False
        return True

    def _resolve_variable(self, value: Any) -> Any:
        """解析类似 {报表截止时间} 的数据字典变量"""
        if not isinstance(value, str):
            return value
        simple_pattern = r'^\{([^:\.=]+)\}$'
        m = re.match(simple_pattern, value)
        if m:
            key = m.group(1)
            if key in self.data_dictionary:
                return self.data_dictionary[key]
        return value

    def _try_parse_date(self, v: Any) -> Optional[date]:
        """尽力将值解析为 date。支持 YYYY-M-D/YYYY-MM-DD 以及包含时间的字符串。"""
        if not isinstance(v, str):
            return None
        s = v.strip()
        if not s:
            return None
        # 去掉时间部分
        if 'T' in s:
            s = s.split('T', 1)[0]
        if ' ' in s:
            s = s.split(' ', 1)[0]
        # 仅处理形如 2025-07-31 或 2025-7-31
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', s):
            try:
                parts = s.split('-')
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, d)
            except Exception:
                return None
        return None

    def _try_parse_number(self, v: Any) -> Optional[float]:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip().replace(',', '')
            try:
                return float(s)
            except Exception:
                return None
        return None

    def _compare_with_operator(self, field_value: Any, raw_comp_value: Any, op: str) -> bool:
        """根据操作符比较，优先按日期，其次数值，最后字符串。"""
        # 先尝试日期比较
        fv_date = self._try_parse_date(field_value)
        cv_date = self._try_parse_date(raw_comp_value)
        if fv_date is not None and cv_date is not None:
            return self._compare(fv_date, cv_date, op)

        # 再尝试数值比较
        fv_num = self._try_parse_number(field_value)
        cv_num = self._try_parse_number(raw_comp_value)
        if fv_num is not None and cv_num is not None:
            return self._compare(fv_num, cv_num, op)

        # 字符串比较（保持与原逻辑兼容）
        # 若是SeaTable单选字段，通常为对象，优先取 name
        if isinstance(field_value, dict) and 'name' in field_value:
            fv_str = str(field_value.get('name') or '')
        else:
            fv_str = '' if field_value is None else str(field_value)
        cv_str = '' if raw_comp_value is None else str(raw_comp_value)

        if op == '=':
            # 特殊处理空值比较
            if cv_str == '' and (field_value is None or fv_str == ''):
                return True
            return fv_str == cv_str
        if op == '!=':
            # 特殊处理空值比较
            if cv_str == '' and (field_value is None or fv_str == ''):
                return False
            return fv_str != cv_str
        if op == '包含':
            # 支持条件值为逗号分隔的多个关键字（, 或 ，），任意一个匹配即通过
            tokens = [t.strip() for t in re.split(r'[\uff0c,]', cv_str) if t.strip()]
            if not tokens and cv_str.strip():  # 如果没有逗号但有内容，则使用原值
                tokens = [cv_str.strip()]

            # 如果字段值本身是数组（多选），逐个元素判断
            if isinstance(field_value, list):
                elements = []
                for item in field_value:
                    if isinstance(item, dict) and 'name' in item:
                        elements.append(str(item['name']))
                    else:
                        elements.append(str(item))
                for token in tokens:
                    for elem in elements:
                        if token and token in elem:
                            return True
                return False

            # 普通字符串字段
            for token in tokens:
                if token and token in fv_str:
                    return True
            return False
        if op == '<=':
            return fv_str <= cv_str
        if op == '>=':
            return fv_str >= cv_str
        if op == '<':
            return fv_str < cv_str
        if op == '>':
            return fv_str > cv_str
        # 未知操作符，默认通过
        return True
    
    def _get_clear_value(self, current_value, field_name):
        """根据当前值和字段名称确定清空值"""
        # 默认所有字段清空时都填充0，适用于大多数数值列
        # 特殊需求可以在这里添加例外情况
        
        # 特殊字段例外处理（如果将来需要）
        special_fields = {
            # '字段名': '特殊清空值',
            # 例如：'状态': None, '备注': '', '创建人': None
        }
        
        if field_name in special_fields:
            return special_fields[field_name]
        
        # 默认使用0清空所有字段
        return 0
    
    def _prepare_clear_operations(self, rules):
        """准备清空操作"""
        # 收集需要清空的表信息
        clear_operations = defaultdict(lambda: {'delete_rows': False, 'clear_fields': set()})
        
        for rule in rules:
            if rule.get('clear_before_sync', False):
                target_table = rule['target_table']
                allow_insert = rule.get('allow_insert', False)
                
                # 如果允许插入，则删除所有行重新创建；否则只清空字段
                # 注意：一旦设置为删除行，就不能再改为只清空字段
                if allow_insert:
                    clear_operations[target_table]['delete_rows'] = True
                    logger.info(f"计划删除表 '{target_table}' 的所有行")
                elif not clear_operations[target_table]['delete_rows']:
                    # 处理多字段映射规则
                    if 'multi_field_mappings' in rule:
                        target_fields = [mapping['target_field'] for mapping in rule['multi_field_mappings']]
                    else:
                        target_fields = rule.get('target_fields', [])
                    
                    for field in target_fields:
                        clear_operations[target_table]['clear_fields'].add(field)
                    
                    logger.info(f"计划清空表 '{target_table}' 的字段: {target_fields}")
        
        # 为每个需要清空的表创建清空操作
        for table_name, clear_info in clear_operations.items():
            target_rows = self.target_data.get(table_name, [])
            if not target_rows:
                continue
                
            if clear_info['delete_rows']:
                # 删除所有行
                delete_operation = {
                    'type': 'delete_all',
                    'table': table_name,
                    'rows': target_rows
                }
                
                if table_name not in self.batch_operations:
                    self.batch_operations[table_name] = []
                self.batch_operations[table_name].insert(0, delete_operation)
                
                logger.info(f"创建删除操作表 '{table_name}': {len(target_rows)} 行")
                
            elif clear_info['clear_fields']:
                # 清空字段
                clear_updates = []
                for row in target_rows:
                    update = {}
                    for field in clear_info['clear_fields']:
                        if field in row:  # 只清空存在的字段
                            clear_value = self._get_clear_value(row[field], field)
                            update[field] = clear_value
                    if update:
                        clear_updates.append(update)
                
                if clear_updates:
                    clear_operation = {
                        'type': 'clear',
                        'rows': target_rows,
                        'updates': clear_updates,
                        'fields': list(clear_info['clear_fields'])
                    }
                    
                    if table_name not in self.batch_operations:
                        self.batch_operations[table_name] = []
                    self.batch_operations[table_name].insert(0, clear_operation)
                    
                    logger.info(f"创建清空操作表 '{table_name}': {len(clear_updates)} 行, 清空字段 {list(clear_info['clear_fields'])}")
    
    def _evaluate_math_expression(self, expression: str, row: Dict) -> Optional[float]:
        """安全地计算数学表达式"""
        import re
        
        # 将表达式中的字段名替换为实际值
        def replace_field(match):
            field_name = match.group(0)
            # 跳过纯数字
            if field_name.replace('.', '').replace('-', '').isdigit():
                return field_name
            # 获取字段值
            value = row.get(field_name, 0)
            if value is None or value == '':
                return '0'
            try:
                return str(float(value))
            except (ValueError, TypeError):
                return '0'
        
        # 使用正则表达式匹配中文字段名和英文字段名
        pattern = r'[a-zA-Z0-9_\u4e00-\u9fa5]+'
        safe_expr = re.sub(pattern, replace_field, expression)
        
        # 只允许安全的数学运算符
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in safe_expr):
            logger.warning(f"表达式包含不安全字符: {safe_expr}")
            return None
        
        try:
            # 使用eval计算表达式
            result = eval(safe_expr)
            return float(result) if result is not None else None
        except Exception as e:
            logger.warning(f"表达式计算失败 '{safe_expr}': {e}")
            return None
    
    def _get_latest_record(self, records: List[Dict], rule: Dict) -> Optional[Dict]:
        """获取最新记录"""
        if not records:
            return None
            
        # 优先使用规则中的latest_config，否则使用全局配置
        latest_config = rule.get('latest_config', {})
        global_config = self.data_dictionary.get('latest_aggregation_config', {}) if self.data_dictionary else {}
        
        time_field = latest_config.get('time_field') or global_config.get('default_time_field')
        sort_order = latest_config.get('sort_order') or global_config.get('default_sort_order', 'desc')
        fallback_fields = latest_config.get('fallback_time_fields') or global_config.get('fallback_time_fields', [])
        
        # 尝试使用主时间字段
        time_fields_to_try = []
        if time_field:
            time_fields_to_try.append(time_field)
        time_fields_to_try.extend(fallback_fields)
        
        for field in time_fields_to_try:
            valid_records = []
            for record in records:
                time_value = record.get(field)
                if time_value and str(time_value).strip():
                    # 尝试解析时间
                    parsed_time = self._try_parse_datetime(time_value)
                    if parsed_time:
                        valid_records.append((record, parsed_time))
            
            if valid_records:
                # 按时间排序
                valid_records.sort(key=lambda x: x[1], reverse=(sort_order == 'desc'))
                return valid_records[0][0]
        
        # 如果没有有效的时间字段，返回第一个记录
        logger.warning(f"无法找到有效时间字段，使用第一条记录")
        return records[0] if records else None
    
    def _try_parse_datetime(self, value: Any) -> Optional[datetime]:
        """尝试解析时间值"""
        if not value:
            return None
            
        if isinstance(value, datetime):
            return value
            
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
                
            # 尝试多种时间格式
            time_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
                '%Y年%m月%d日 %H:%M:%S',
                '%Y年%m月%d日 %H:%M',
                '%Y年%m月%d日',
                '%Y.%m.%d %H:%M:%S',
                '%Y.%m.%d %H:%M',
                '%Y.%m.%d',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y %H:%M',
                '%m/%d/%Y',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%d/%m/%Y'
            ]
            
            for fmt in time_formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
                    
        return None

    def _compare(self, left: Union[float, date], right: Union[float, date], op: str) -> bool:
        if op == '=':
            return left == right
        if op == '!=':
            return left != right
        if op == '<=':
            return left <= right
        if op == '>=':
            return left >= right
        if op == '<':
            return left < right
        if op == '>':
            return left > right
        return True
    
    async def execute_operations(self, max_concurrent_tables: int = 3):
        """执行所有操作，支持多表并发处理"""
        logger.info("开始执行批量操作...")
        
        total_operations = sum(len(ops) for ops in self.batch_operations.values())
        if total_operations == 0:
            logger.warning("没有操作需要执行")
            return
            
        logger.info(f"总操作数: {total_operations}, 最大并发表数: {max_concurrent_tables}")
        
        # 创建并发信号量
        table_semaphore = asyncio.Semaphore(max_concurrent_tables)
        
        # 为每个表创建处理任务
        table_tasks = []
        for table_name, operations in self.batch_operations.items():
            task = self._execute_table_operations_concurrent(table_name, operations, table_semaphore)
            table_tasks.append(task)
        
        # 并发执行所有表的操作
        results = await asyncio.gather(*table_tasks, return_exceptions=True)
        
        # 统计结果
        success_count = 0
        error_count = 0
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                logger.error(f"表操作失败: {result}")
            else:
                success_count += result.get('success', 0)
                error_count += result.get('error', 0)
        
        logger.info(f"批量操作完成: 成功 {success_count}, 失败 {error_count}")
    
    async def _execute_table_operations_concurrent(self, table_name, operations, semaphore):
        """并发执行单个表的所有操作"""
        async with semaphore:
            logger.info(f"开始处理表 '{table_name}': {len(operations)} 个操作")
            
            success_count = 0
            error_count = 0
            
            for operation in operations:
                try:
                    if operation['type'] == 'delete_all':
                        await self._execute_delete_all_operation(table_name, operation)
                        # 删除后重新加载表数据，更新缓存
                        logger.info(f"重新加载表 '{table_name}' 数据（删除后更新缓存）")
                        await self._reload_table_data(table_name)
                    elif operation['type'] == 'clear':
                        await self._execute_clear_operation(table_name, operation)
                    elif operation['type'] == 'update':
                        # 对于更新操作，如果表数据已被重新加载，需要使用最新的目标数据
                        await self._execute_batch_update_with_retry(table_name, operation)
                    elif operation['type'] == 'insert':
                        await self._execute_batch_insert_with_retry(table_name, operation)
                        # 插入后重新加载表数据，供后续更新使用
                        logger.info(f"重新加载表 '{table_name}' 数据（插入后更新缓存）") 
                        await self._reload_table_data(table_name)
                    success_count += 1
                except Exception as e:
                    logger.error(f"执行表 '{table_name}' 操作失败: {e}")
                    error_count += 1
            
            logger.info(f"表 '{table_name}' 处理完成: 成功 {success_count}, 失败 {error_count}")
            return {'success': success_count, 'error': error_count}
        
        if error_count > 0:
            logger.warning(f"存在 {error_count} 个失败操作，请检查日志")
    
    async def _reload_table_data(self, table_name):
        """重新加载指定表的数据，更新目标数据缓存"""
        try:
            rows = await self.base.get_rows(table_name, '默认视图')
            self.target_data[table_name] = rows
            logger.debug(f"表 '{table_name}' 数据已更新: {len(rows)} 行")
        except Exception as e:
            logger.error(f"重新加载表 '{table_name}' 数据失败: {e}")
            # 如果重新加载失败，至少清空缓存避免使用过期数据
            self.target_data[table_name] = []
    
    def _rows_match(self, old_row, current_row):
        """判断两行是否匹配（用于重新匹配行ID）"""
        # 优先使用一些关键字段进行匹配
        key_fields = ['合同编号', '预算编号', '项目编号', '项目名称']
        
        for field in key_fields:
            if field in old_row and field in current_row:
                old_value = old_row.get(field)
                current_value = current_row.get(field)
                if old_value and current_value and str(old_value) == str(current_value):
                    return True
        
        # 如果没有关键字段匹配，返回False
        return False
    
    async def _execute_batch_update_with_retry(self, table_name, operation, max_retries=3):
        """带重试机制的批量更新"""
        for attempt in range(max_retries):
            try:
                await self._execute_batch_update(table_name, operation)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"第 {attempt + 1} 次尝试失败，等待 {2 ** attempt} 秒后重试: {e}")
                await asyncio.sleep(2 ** attempt)
    
    async def _execute_batch_update(self, table_name, operation):
        """执行批量更新，动态调整批次大小，支持动态行匹配"""
        rows = operation['rows']
        updates = operation['updates']
        
        if not rows or not updates:
            logger.debug(f"表 '{table_name}' 没有数据需要更新")
            return
        
        # 检查是否需要动态重新匹配行（当缓存的行ID可能无效时）
        try:
            # 先测试第一行的ID是否有效
            first_row = rows[0]
            first_update = updates[0]
            test_rows = [first_row]
            test_updates = [first_update]
            await self.base.modify_rows(table_name, test_rows, test_updates)
            
            # 如果测试成功，继续正常的批量更新流程
            logger.debug(f"行ID有效，继续正常批量更新")
            
        except Exception as e:
            if "row ids not exist" in str(e):
                logger.warning(f"检测到行ID无效，尝试动态重新匹配行: {e}")
                # 重新加载当前表数据
                current_rows = await self.base.get_rows(table_name, '默认视图')
                
                # 尝试重新匹配行
                matched_pairs = []
                for old_row, update_data in zip(rows, updates):
                    # 根据主键找到对应的当前行
                    matched_row = None
                    for current_row in current_rows:
                        # 这里需要根据具体的匹配逻辑，暂时使用简单的匹配
                        if self._rows_match(old_row, current_row):
                            matched_row = current_row
                            break
                    
                    if matched_row:
                        matched_pairs.append((matched_row, update_data))
                
                if matched_pairs:
                    logger.info(f"重新匹配成功: {len(matched_pairs)}/{len(rows)} 行")
                    rows = [pair[0] for pair in matched_pairs]
                    updates = [pair[1] for pair in matched_pairs]
                else:
                    logger.error(f"无法重新匹配任何行，跳过更新操作")
                    return
            else:
                # 其他错误，直接抛出
                raise
        
        # 根据数据量动态调整批次大小 - 超大批次版本
        total_rows = len(rows)
        if total_rows <= 100:
            batch_size = 50
        elif total_rows <= 500:
            batch_size = 200
        elif total_rows <= 2000:
            batch_size = 500
        else:
            batch_size = 1000
            
        logger.debug(f"表 '{table_name}' 更新 {total_rows} 行，批次大小: {batch_size}")
        
        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i:i + batch_size]
            batch_updates = updates[i:i + batch_size]
            
            try:
                logger.info(f"正在更新表 '{table_name}': 批次{i//batch_size + 1}, 更新数据样例: {batch_updates[0] if batch_updates else 'None'}")
                await self.base.modify_rows(table_name, batch_rows, batch_updates)
                logger.debug(f"批量更新表 '{table_name}': {len(batch_rows)} 行 ({i + 1}-{min(i + batch_size, total_rows)}/{total_rows})")
                
                # 在批次之间添加延迟，避免503错误 - 优化延迟时间
                if i + batch_size < len(rows):
                    await asyncio.sleep(0.2)  # 200ms延迟
                    
            except Exception as e:
                logger.error(f"批量更新失败 表:'{table_name}' 批次:{i + 1}-{min(i + batch_size, total_rows)}: {e}")
                raise
    
    async def _execute_clear_operation(self, table_name, operation):
        """执行清空操作"""
        rows = operation['rows']
        updates = operation['updates']
        fields = operation.get('fields', [])
        
        if not rows or not updates:
            logger.debug(f"表 '{table_name}' 没有数据需要清空")
            return
        
        logger.info(f"清空表 '{table_name}' 的字段 {fields}: {len(rows)} 行")
        
        # 分批清空，使用与更新相同的批次大小策略 - 超大批次版本
        total_rows = len(rows)
        if total_rows <= 100:
            batch_size = 50
        elif total_rows <= 500:
            batch_size = 200
        elif total_rows <= 2000:
            batch_size = 500
        else:
            batch_size = 1000
        
        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i:i + batch_size]
            batch_updates = updates[i:i + batch_size]
            
            try:
                await self.base.modify_rows(table_name, batch_rows, batch_updates)
                logger.debug(f"清空表 '{table_name}': {len(batch_rows)} 行 ({i + 1}-{min(i + batch_size, total_rows)}/{total_rows})")
                
                # 在批次之间添加延迟，避免503错误 - 优化延迟时间
                if i + batch_size < len(rows):
                    await asyncio.sleep(0.2)  # 200ms延迟
                    
            except Exception as e:
                logger.error(f"清空失败 表:'{table_name}' 批次:{i + 1}-{min(i + batch_size, total_rows)}: {e}")
                raise
    
    async def _execute_delete_all_operation(self, table_name, operation):
        """执行删除所有行操作"""
        rows = operation['rows']
        if not rows:
            return
            
        logger.info(f"删除表 '{table_name}' 的所有行: {len(rows)} 行")
        
        # 提取所有行ID
        row_ids = []
        for row in rows:
            row_id = row.get('_id')
            if row_id:
                row_ids.append(row_id)
            else:
                logger.warning(f"行缺少_id字段，跳过删除: {row}")
        
        if not row_ids:
            logger.warning(f"表 '{table_name}' 没有有效的行ID可删除")
            return
        
        # 分批删除，使用适当的批次大小 - 超大批次版本
        total_rows = len(row_ids)
        if total_rows <= 100:
            batch_size = 100
        elif total_rows <= 500:
            batch_size = 300
        elif total_rows <= 2000:
            batch_size = 500
        else:
            batch_size = 800
        
        success_count = 0
        error_count = 0
        
        for i in range(0, len(row_ids), batch_size):
            batch_ids = row_ids[i:i + batch_size]
            
            try:
                await self.base.batch_delete_rows(table_name, batch_ids)
                success_count += len(batch_ids)
                logger.debug(f"批量删除表 '{table_name}': {len(batch_ids)} 行 ({i + 1}-{min(i + batch_size, total_rows)}/{total_rows})")
                
                # 在批次之间添加延迟，避免API频率限制
                if i + batch_size < len(row_ids):
                    await asyncio.sleep(0.2)  # 200ms延迟
                    
            except Exception as e:
                error_count += len(batch_ids)
                logger.error(f"批量删除失败 表:'{table_name}' 批次:{i + 1}-{min(i + batch_size, total_rows)}: {e}")
                # 继续执行其他批次的删除
        
        logger.info(f"表 '{table_name}' 删除完成: 成功 {success_count}, 失败 {error_count}")
        
        if error_count > 0:
            logger.warning(f"删除操作部分失败: 成功 {success_count}, 失败 {error_count}")
    
    async def _execute_batch_insert_with_retry(self, table_name, operation, max_retries=3):
        """带重试机制的批量插入"""
        for attempt in range(max_retries):
            try:
                await self._execute_batch_insert(table_name, operation)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"插入第 {attempt + 1} 次尝试失败，等待 {2 ** attempt} 秒后重试: {e}")
                await asyncio.sleep(2 ** attempt)
    
    async def _execute_batch_insert(self, table_name, operation):
        """执行批量插入，使用适配器的append_row方法"""
        data = operation['data']
        
        if not data:
            logger.debug(f"表 '{table_name}' 没有数据需要插入")
            return
        
        total_rows = len(data)
        logger.info(f"表 '{table_name}' 开始插入 {total_rows} 行数据")
        
        success_count = 0
        error_count = 0
        
        # 逐行插入，因为SeaTableOfficialAdapter只支持单行插入
        for i, row_data in enumerate(data):
            try:
                await self.base.append_row(table_name, row_data)
                success_count += 1
                if (i + 1) % 20 == 0 or i + 1 == total_rows:
                    logger.debug(f"插入进度 表 '{table_name}': {i + 1}/{total_rows}")
            except Exception as e:
                error_count += 1
                logger.error(f"插入失败 表:'{table_name}' 第 {i + 1} 行: {e}")
                # 继续执行其他行的插入
        
        logger.info(f"表 '{table_name}' 插入完成: 成功 {success_count}, 失败 {error_count}")
        
        if error_count > 0:
            raise Exception(f"插入操作部分失败: 成功 {success_count}, 失败 {error_count}")

async def run_fast_sync(base_adapter, sync_rules, data_dictionary: Optional[Dict[str, Any]] = None, max_concurrent: int = 10):
    """运行快速同步，增强内存管理"""
    sync_engine = FastSync(base_adapter, data_dictionary=data_dictionary, max_concurrent=max_concurrent)
    
    try:
        # 1. 加载所有数据
        await sync_engine.load_all_data(sync_rules)
        
        # 2. 准备批量操作
        sync_engine.prepare_operations(sync_rules)
        
        # 3. 执行批量操作
        await sync_engine.execute_operations()
        
        logger.info("快速同步完成")
        
    except Exception as e:
        logger.error(f"快速同步失败: {e}")
        raise
    finally:
        # 清理内存
        sync_engine.source_data.clear()
        sync_engine.target_data.clear()
        sync_engine.batch_operations.clear()
        logger.debug("内存清理完成")

# 使用示例
if __name__ == "__main__":
    import os
    
    # 尝试加载不同的配置文件（优先使用config目录下的文件）
    config_files = [
        'config/worktime_stats_config.json',
        'config/project_stats_config.json',
        'config/sync_rules.json'
    ]
    
    config = None
    config_file = None
    
    for file_path in config_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    config_file = file_path
                    break
            except Exception as e:
                logger.error(f"加载配置文件 {file_path} 失败: {e}")
                continue
    
    if not config:
        logger.error("未找到有效的配置文件")
        exit(1)
    
    logger.info(f"使用配置文件: {config_file}")
    
    sync_rules = config.get('sync_rules', [])
    data_dictionary = config.get('data_dictionary', {})
    
    if not sync_rules:
        logger.error("配置文件中未找到同步规则")
        exit(1)
    
    logger.info(f"加载了 {len(sync_rules)} 个同步规则")
    
    # 这里需要传入实际的base_adapter
    # asyncio.run(run_fast_sync(base_adapter, sync_rules, data_dictionary))
