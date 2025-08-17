# 数据预处理功能使用指南

## 概述
本数据预处理功能完全替代了原有的`datapre.js`，使用Python实现了更高效、更稳定的数据预处理操作。

## ✨ 主要优势
- **高性能**: Python比JavaScript处理大量数据更快
- **更稳定**: 统一的错误处理和重试机制
- **易维护**: 与现有同步系统集成，统一的代码库
- **功能完备**: 支持所有原datapre.js的处理类型

## 🚀 快速开始

### 1. 运行数据预处理
```bash
# 基本用法
./run_preprocess.sh

# 测试功能
./run_preprocess.sh --test

# 查看帮助
./run_preprocess.sh --help
```

### 2. 配置环境变量（推荐）
```bash
# 设置SeaTable Token
export PREPROCESS_SEATABLE_TOKEN='your_token_here'

# 然后运行
./run_preprocess.sh
```

### 3. 或直接编辑脚本
编辑`run_preprocess.sh`文件，修改`SEATABLE_TOKEN`变量。

## 📋 支持的处理类型

| 处理类型 | 说明 | 示例 |
|----------|------|------|
| `firstPart` | 取分隔符前内容 | "部门A,部门B" → "部门A" |
| `if_and_then_concat` | 条件拼接 | 条件满足时拼接指定字段 |
| `yearIf` | 条件提取年份 | "2025-03-15" → 2025 |
| `monthIf` | 提取月份 | "2025-03-15" → "3月" |
| `dateYearMonth` | 提取年月 | "2025-03-15" → "202503" |
| `math` | 数学表达式计算 | "合同金额-已验收额" |
| `replace` | 字符串替换 | "旧部门名" → "新部门名" |

## 📁 文件结构
```
sea-py-cv/
├── run_preprocess.sh                    # 主运行脚本
├── fast_sync.py                         # 扩展了预处理功能
├── preprocess_config_converter.py       # 配置转换工具
├── test_preprocess_functions.py         # 测试脚本
└── config/
    ├── preprocess_config.json          # 示例配置
    └── full_preprocess_config.json     # 完整配置（从你的原配置转换）
```

## 🔧 配置文件格式

### 基本结构
```json
{
  "sync_rules": [
    {
      "source_table": "确认收入",
      "target_table": "确认收入",
      "multi_field_mappings": [
        {
          "source_field": "实际交付部门",
          "target_field": "主交付部门",
          "aggregation": "firstPart",
          "conditions": [],
          "factor": 1.0
        }
      ],
      "allow_insert": false,
      "should_run": true,
      "execution_category": "第一步"
    }
  ],
  "data_dictionary": {
    "年份": "2025",
    "报表截止时间": "2025-08-13"
  }
}
```

### 处理类型配置示例

#### 1. firstPart - 取分隔符前内容
```json
{
  "source_field": "实际交付部门",
  "target_field": "主交付部门", 
  "aggregation": "firstPart",
  "conditions": []
}
```

#### 2. conditional_concat - 条件拼接
```json
{
  "source_field": "",
  "target_field": "签单标识",
  "aggregation": "conditional_concat",
  "conditions": [
    {"field": "渠道", "op": "!=", "value": "内部"},
    {"field": "有无预算", "op": "=", "value": "已签合同"}
  ],
  "concat_fields": ["年份", "签单"]
}
```

#### 3. math_expression - 数学计算
```json
{
  "source_field": "",
  "target_field": "当前在建总额",
  "aggregation": "math_expression",
  "conditions": [
    {"field": "项目类型", "op": "!=", "value": "运维服务"}
  ],
  "math_expression": "合同金额-阶段已验收额"
}
```

#### 4. string_replace - 字符串替换
```json
{
  "source_field": "部门名称",
  "target_field": "主交付部门",
  "aggregation": "string_replace",
  "replace_mappings": {
    "信访交付组": "信访事业部",
    "政通云交付部": "政务产品实施部"
  }
}
```

## 🔄 执行流程

脚本按执行类别分阶段运行：
1. **第一步**: 基础数据处理（提取、转换基础字段）
2. **第二步**: 关联数据处理（基于第一步结果的进一步处理）  
3. **第三步**: 最终数据处理（最后的清理和标准化）

这样的分阶段执行确保了数据依赖关系的正确处理。

## 🛠️ 配置转换

如果你有现有的CSV格式预处理配置，可以使用转换工具：

```python
# 运行转换脚本
python preprocess_config_converter.py

# 或者在代码中使用
from preprocess_config_converter import PreprocessConfigConverter

converter = PreprocessConfigConverter()
config = converter.convert_csv_to_json('your_config.csv', 'output_config.json')
```

## 🧪 测试和验证

### 运行功能测试
```bash
./run_preprocess.sh --test
```
这将验证所有7种处理类型是否正常工作。

### 手动测试特定功能
```python
python test_preprocess_functions.py
```

## 📊 监控和日志

脚本提供详细的彩色日志输出：
- 🔵 **[INFO]**: 一般信息
- 🟢 **[SUCCESS]**: 成功操作  
- 🟡 **[WARNING]**: 警告信息
- 🔴 **[ERROR]**: 错误信息
- 🟣 **[STEP]**: 执行步骤

## ❓ 常见问题

### Q: 脚本提示找不到配置文件
**A**: 确保存在以下文件之一：
- `config/full_preprocess_config.json` 
- `config/preprocess_config.json`

### Q: 如何修改数据字典变量？
**A**: 编辑配置文件中的`data_dictionary`部分：
```json
{
  "data_dictionary": {
    "年份": "2025",
    "报表截止时间": "2025-12-31"
  }
}
```

### Q: 处理失败怎么办？
**A**: 
1. 查看详细的错误日志
2. 运行测试模式验证功能: `./run_preprocess.sh --test`
3. 检查Token和网络连接
4. 确认配置文件格式正确

### Q: 可以只执行某个阶段吗？
**A**: 脚本会自动检测并按阶段执行。如果需要手动控制，可以：
1. 修改配置文件中的`execution_category`
2. 或者使用`jq`工具过滤特定阶段的规则

## 🚀 迁移从datapre.js

1. **备份现有配置**: 保存你的预处理配置表
2. **转换配置**: 使用转换工具生成JSON配置
3. **测试验证**: 运行测试确保功能正常
4. **正式迁移**: 用新脚本替代原有的datapre.js调用

## 🔗 相关文件
- `run_sync.py` - 底层同步引擎
- `fast_sync.py` - 扩展的快速同步类（包含预处理功能）
- `sync_project_stats.sh` - 项目统计同步脚本（参考）

---

## 📞 技术支持

如遇到问题，请查看：
1. 脚本的详细日志输出
2. `test_preprocess_functions.py`的测试结果
3. 配置文件的JSON格式是否正确

**现在你可以享受比datapre.js更快、更稳定的数据预处理体验！** 🎉