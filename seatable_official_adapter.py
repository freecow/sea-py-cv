#!/usr/bin/env python3
"""
SeaTable官方SDK适配器
使用官方seatable-api包提供与同步脚本兼容的接口

Author: Assistant  
Date: 2025-08-07
"""

import logging
from typing import List, Dict, Any, Optional
from seatable_api import Base


class SeaTableOfficialAdapter:
    """SeaTable官方SDK适配器，提供与同步脚本兼容的接口"""
    
    def __init__(self, server_url: str, api_token: str):
        """
        初始化SeaTable官方SDK适配器
        
        Args:
            server_url: SeaTable服务器地址
            api_token: API Token  
        """
        self.server_url = server_url
        self.api_token = api_token
        self.logger = logging.getLogger(__name__)
        
        # 初始化Base对象
        self.base = Base(api_token, server_url)
        
        # 缓存表结构信息
        self._tables_cache = None
        self._columns_cache: Dict[str, List[Dict[str, Any]]] = {}
        
    async def _ensure_auth(self):
        """确保已认证"""
        if not hasattr(self, '_authenticated'):
            self.base.auth()
            self._authenticated = True
            self.logger.debug("SeaTable SDK认证确认")
    
    async def get_table(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        根据表名获取表信息（与MockBaseAdapter兼容的接口）
        
        Args:
            table_name: 表名
            
        Returns:
            表信息字典
        """
        try:
            await self._ensure_auth()
            
            # 获取所有表信息（使用缓存）
            if self._tables_cache is None:
                self._tables_cache = self.base.list_tables()
            
            # 查找指定表
            for table in self._tables_cache:
                if table.get('name') == table_name:
                    return table
                    
            self.logger.warning(f"表 '{table_name}' 未找到")
            return {}
            
        except Exception as e:
            self.logger.error(f"获取表信息失败: {e}")
            return {}

    async def get_rows(
        self, 
        table_name: str, 
        view_name: str = "默认视图"
    ) -> List[Dict[str, Any]]:
        """
        获取表格行数据（与MockBaseAdapter兼容的接口）
        使用SQL查询获取完整数据，避免记录限制
        
        Args:
            table_name: 表名
            view_name: 视图名
            
        Returns:
            行数据列表
        """
        try:
            await self._ensure_auth()
            
            # 使用分页SQL查询获取所有数据
            try:
                # 先查询总行数
                count_sql = f"SELECT COUNT(*) as total_count FROM `{table_name}`"
                count_result = self.base.query(count_sql)
                total_rows = count_result[0]['total_count'] if count_result else 0
                
                if total_rows == 0:
                    self.logger.info(f"表 '{table_name}' 没有数据")
                    return []
                
                # 如果数据量小，直接查询
                if total_rows <= 10000:
                    sql = f"SELECT * FROM `{table_name}` LIMIT {total_rows + 100}"
                    rows = self.base.query(sql)
                    rows = self._normalize_select_values(table_name, rows)
                    self.logger.info(f"通过SQL查询从表 '{table_name}' 获取到 {len(rows)} 行数据")
                    return rows
                
                # 大数据量分页查询
                self.logger.info(f"表 '{table_name}' 有 {total_rows} 行数据，开始分页查询...")
                all_rows = []
                page_size = 10000
                offset = 0
                
                while offset < total_rows:
                    sql = f"SELECT * FROM `{table_name}` LIMIT {page_size} OFFSET {offset}"
                    page_rows = self.base.query(sql)
                    
                    if not page_rows:
                        break
                    
                    all_rows.extend(page_rows)
                    offset += page_size
                    
                    self.logger.info(f"已获取 {len(all_rows)}/{total_rows} 行数据...")
                    
                    # 避免查询过快
                    import time
                    time.sleep(0.1)
                
                all_rows = self._normalize_select_values(table_name, all_rows)
                self.logger.info(f"分页查询完成，从表 '{table_name}' 总共获取到 {len(all_rows)} 行数据")
                return all_rows
                
            except Exception as sql_error:
                self.logger.warning(f"SQL查询失败，回退到list_rows: {sql_error}")
                
                # 回退到list_rows方法
                try:
                    rows = self.base.list_rows(table_name, view_name=view_name)
                    rows = self._normalize_select_values(table_name, rows)
                    self.logger.info(f"从表 '{table_name}' 视图 '{view_name}' 获取到 {len(rows)} 行数据")
                    return rows
                except Exception as list_error:
                    self.logger.error(f"list_rows也失败: {list_error}")
                    return []
            
        except Exception as e:
            self.logger.error(f"获取行数据失败: {e}")
            return []

    def _get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取列信息并缓存"""
        if table_name not in self._columns_cache:
            try:
                self._columns_cache[table_name] = self.base.list_columns(table_name)
            except Exception as e:
                self.logger.warning(f"获取列信息失败，将跳过单选映射: {e}")
                self._columns_cache[table_name] = []
        return self._columns_cache[table_name]

    def _normalize_select_values(self, table_name: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将单选/多选字段的内部ID转换为名称，保证条件判断可用"""
        if not rows:
            return rows
        columns = self._get_columns(table_name)
        if not columns:
            return rows

        # 构建映射: 字段名 -> {option_id: option_name}
        field_to_option_map: Dict[str, Dict[str, str]] = {}
        multi_select_fields: set[str] = set()
        for col in columns:
            try:
                col_type = col.get('type')
                if col_type in ['single-select', 'multiple-select']:
                    data = col.get('data') or {}
                    options = data.get('options') or []
                    opt_map = {}
                    for opt in options:
                        opt_id = opt.get('id') or opt.get('key') or opt.get('value')
                        opt_name = opt.get('name') or opt.get('label') or ''
                        if opt_id and opt_name is not None:
                            opt_map[str(opt_id)] = str(opt_name)
                    if opt_map:
                        field_to_option_map[col.get('name')] = opt_map
                        if col_type == 'multiple-select':
                            multi_select_fields.add(col.get('name'))
            except Exception:
                continue

        if not field_to_option_map:
            return rows

        # 替换行中的值
        normalized_rows = []
        for row in rows:
            new_row = dict(row)
            for field_name, opt_map in field_to_option_map.items():
                if field_name not in new_row:
                    continue
                value = new_row[field_name]
                try:
                    # 多选：列表或以逗号分隔的字符串
                    if field_name in multi_select_fields:
                        if isinstance(value, list):
                            mapped = []
                            for v in value:
                                if isinstance(v, dict) and 'id' in v:
                                    mapped.append(opt_map.get(str(v['id']), v.get('name') or v))
                                else:
                                    mapped.append(opt_map.get(str(v), v))
                            new_row[field_name] = mapped
                        elif isinstance(value, str):
                            parts = [p.strip() for p in value.split(',') if p.strip()]
                            mapped = [opt_map.get(p, p) for p in parts]
                            new_row[field_name] = mapped
                        # 其他类型保持原样
                    else:
                        # 单选：可能是id、对象或名称
                        if isinstance(value, dict):
                            vid = value.get('id') or value.get('key') or value.get('value')
                            name = value.get('name') or value.get('label')
                            if vid is not None and str(vid) in opt_map:
                                new_row[field_name] = opt_map[str(vid)]
                            elif name is not None:
                                new_row[field_name] = str(name)
                        else:
                            new_row[field_name] = opt_map.get(str(value), value)
                except Exception:
                    # 出错时保持原值
                    continue
            normalized_rows.append(new_row)
        return normalized_rows

    async def append_row(self, table_name: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加单行数据（与MockBaseAdapter兼容的接口）
        
        Args:
            table_name: 表名
            row_data: 行数据
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            
            result = self.base.append_row(table_name, row_data)
            self.logger.debug(f"成功插入行到表 '{table_name}'")
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"插入行失败: {e}")
            raise

    async def modify_rows(
        self, 
        table_name: str, 
        rows: List[Dict[str, Any]], 
        updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        批量更新行数据（与MockBaseAdapter兼容的接口）
        
        Args:
            table_name: 表名
            rows: 要更新的行列表
            updates: 更新数据列表
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            
            if len(rows) != len(updates):
                raise ValueError("rows和updates数量不匹配")
            
            updated_count = 0
            for i, row in enumerate(rows):
                if i < len(updates):
                    row_id = row.get('_id')
                    if row_id:
                        self.base.update_row(table_name, row_id, updates[i])
                        updated_count += 1
            
            self.logger.debug(f"成功更新 {updated_count} 行数据到表 '{table_name}'")
            return {'success': True, 'updated_count': updated_count}
            
        except Exception as e:
            self.logger.error(f"更新行失败: {e}")
            raise

    async def delete_row(self, table_name: str, row_id: str) -> Dict[str, Any]:
        """
        删除单行数据（与MockBaseAdapter兼容的接口）
        
        Args:
            table_name: 表名
            row_id: 行ID
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            
            result = self.base.delete_row(table_name, row_id)
            self.logger.debug(f"成功删除行 {row_id} 从表 '{table_name}'")
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"删除行失败: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        测试连接是否正常
        
        Returns:
            连接是否成功
        """
        try:
            # 认证和测试连接，使用默认的API网关设置
            self.base.auth()
            tables = self.base.list_tables()
            self._authenticated = True
            
            self.logger.info(f"SeaTable SDK连接测试成功，找到 {len(tables)} 个表")
            return True
            
        except Exception as e:
            self.logger.error(f"SeaTable SDK连接测试失败: {e}")
            return False

    async def batch_append_rows(self, table_name: str, rows_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量添加行
        
        Args:
            table_name: 表名
            rows_data: 行数据列表
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            result = self.base.batch_append_rows(table_name, rows_data)
            self.logger.debug(f"批量添加 {len(rows_data)} 行到表 '{table_name}'")
            return result
        except Exception as e:
            self.logger.error(f"批量添加行失败: {e}")
            raise

    async def batch_update_rows(self, table_name: str, rows_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量更新行
        
        Args:
            table_name: 表名
            rows_data: 包含行ID和更新数据的列表
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            result = self.base.batch_update_rows(table_name, rows_data)
            self.logger.debug(f"批量更新 {len(rows_data)} 行到表 '{table_name}'")
            return result
        except Exception as e:
            self.logger.error(f"批量更新行失败: {e}")
            raise

    async def batch_delete_rows(self, table_name: str, row_ids: List[str]) -> Dict[str, Any]:
        """
        批量删除行
        
        Args:
            table_name: 表名
            row_ids: 行ID列表
            
        Returns:
            操作结果
        """
        try:
            await self._ensure_auth()
            result = self.base.batch_delete_rows(table_name, row_ids)
            self.logger.debug(f"批量删除 {len(row_ids)} 行从表 '{table_name}'")
            return result
        except Exception as e:
            self.logger.error(f"批量删除行失败: {e}")
            raise