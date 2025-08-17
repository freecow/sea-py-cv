# SeaTable 快速同步工具

基于 Python 的 SeaTable 数据同步工具，支持高效的数据同步、聚合计算和批量处理。采用本地数据准备模式，大幅减少API调用次数，提高同步速度。

## 🚀 快速开始

### 方式1: 下载可执行文件（推荐）

1. **下载预编译版本**
   - 访问 [Releases 页面](../../releases)
   - 下载对应平台的可执行文件：
     - Windows: `seatable-sync-windows.exe`
     - Linux: `seatable-sync-linux`
     - macOS: `seatable-sync-macos`

2. **配置环境变量**
   ```bash
   # 复制配置模板
   cp .env.example .env
   
   # 编辑.env文件，填入你的配置
   SEATABLE_TOKEN=your_api_token_here
   SEATABLE_CONFIG_FILE=config/project_stats_config.json
   ```
   
   > ⚠️ **安全提醒**: .env文件包含敏感信息（API Token），已通过.gitignore排除，不会被提交到版本控制系统。

3. **运行同步工具**
   ```bash
   # Windows
   seatable-sync-windows.exe
   
   # Linux/macOS
   ./seatable-sync-linux
   ./seatable-sync-macos
   ```

### 方式2: Python 源码运行

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境**
   ```bash
   cp .env.example .env
   # 编辑.env文件填入配置
   ```
   
   > ⚠️ **安全提醒**: .env文件包含API Token等敏感信息，已通过.gitignore排除，请勿提交到版本控制。

3. **运行同步**
   ```bash
   # 使用.env文件配置
   python run_sync.py
   
   # 或使用命令行参数
   python run_sync.py --token YOUR_TOKEN --config config/project_stats_config.json
   ```

## 📦 自动构建

项目使用 GitHub Actions 自动构建多平台可执行文件：
- **触发条件**: Push到main分支、Pull Request、Release发布
- **构建平台**: Windows, Linux, macOS
- **输出文件**: 包含所有依赖的单个可执行文件

### 本地构建

```bash
# 使用构建脚本
python build_standalone.py
```

## ⚙️ 配置方式

### 环境变量配置（推荐）
```bash
# .env文件
SEATABLE_TOKEN=your_api_token_here
SEATABLE_SERVER_URL=https://cloud.seatable.cn
SEATABLE_CONFIG_FILE=config/project_stats_config.json
SEATABLE_MAX_CONCURRENT=5
```

### 命令行参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config`, `-c` | 配置文件路径 | 从.env读取或`config/sync_rules.json` |
| `--token`, `-t` | SeaTable API Token | 从.env读取 |
| `--server-url`, `-s` | SeaTable服务器URL | 从.env读取或`https://cloud.seatable.cn` |
| `--max-concurrent` | 最大并发请求数 | 从.env读取或`5` |

**配置优先级**: 命令行参数 > .env文件 > 默认值

## 🌟 核心特性

- **🔥 高效同步引擎** - 本地数据准备，一次性批量写入，减少API调用
- **🎯 多种聚合模式** - 支持求和(sum)、广播(broadcast)、最新记录(latest)、复制(copy)等
- **🔀 多字段映射** - 支持单规则多字段映射，大幅简化配置文件
- **🎛️ 智能数据处理** - 支持条件过滤、排除条件、数据变换、日期和数值比较
- **📚 数据字典支持** - 支持变量解析，如 `{报表截止时间}`、`{阶段目标比例}` 等
- **⚡ 批量操作优化** - 智能批次大小调整、重试机制、并发控制
- **📋 完善的日志系统** - 详细的执行日志，便于调试和监控
- **🖥️ 跨平台支持** - Windows, Linux, macOS 单文件可执行程序
- **🔧 灵活配置** - 支持.env文件和命令行参数

## 配置文件详解

### 配置文件结构

完整的配置文件包含三个主要部分：

```json
{
  "sync_rules": [
    // 同步规则数组
  ],
  "data_dictionary": {
    // 数据字典变量
  },
  "latest_aggregation_config": {
    // 最新记录聚合配置
  }
}
```

### 1. 单字段映射规则

#### 基础同步规则示例

```json
{
  "source_table": "PMS-确认收入",           // 源表名
  "target_table": "A1-新签合同对比2025",    // 目标表名
  "source_keys": ["营销辅助部门"],          // 源表主键字段
  "target_keys": ["销售组"],               // 目标表主键字段
  "source_fields": ["合同金额"],           // 源表数据字段
  "target_fields": ["新签额"],             // 目标表数据字段
  "conditions": [                          // 数据过滤条件
    {
      "field": "合同签订日期",
      "op": ">=", 
      "value": "2025-01-01"
    },
    {
      "field": "签单标识",
      "op": "包含",
      "value": "2025签单"
    }
  ],
  "aggregation": "sum",                    // 聚合类型
  "factor": 0.0001,                       // 数值转换因子(万元转换)
  "clear_before_sync": true,               // 同步前清空字段
  "allow_insert": false,                   // 是否允许插入新行
  "should_run": true,                      // 是否启用此规则
  "note": "A1各销售组2025年新签额"         // 规则说明
}
```

#### 复制模式配置示例

完整数据迁移：

```json
{
  "source_table": "PMS-确认收入",
  "target_table": "底表-本年截止日新签合同",
  "source_keys": ["合同编号"],
  "target_keys": ["合同编号"],
  "source_fields": [
    "合同编号", "项目名称", "合同金额", 
    "自有软件额", "合同签订日期", "销售负责人"
  ],
  "target_fields": [
    "合同编号", "项目名称", "合同金额",
    "自有软件额", "合同签订日期", "销售负责人"
  ],
  "conditions": [
    {"field": "签单标识", "op": "包含", "value": "2025签单"},
    {"field": "合同签订日期", "op": "<=", "value": "{报表截止时间}"}
  ],
  "aggregation": "copy",                   // 复制模式
  "clear_before_sync": true,               // 清空目标表
  "allow_insert": true,                    // 允许插入新行
  "should_run": true,
  "note": "清空底表并从PMS生成本年新签合同数据"
}
```

#### 广播模式配置示例

将配置值复制到目标表所有行：

```json
{
  "source_table": "config",                // 虚拟配置表
  "target_table": "A1-新签合同对比2025",
  "source_keys": [],                       // 无主键
  "target_keys": [],                       // 无主键
  "source_fields": ["阶段目标比例"],       // 从数据字典获取
  "target_fields": ["阶段目标比例"],       // 更新到所有行
  "conditions": [],                        // 无条件
  "aggregation": "broadcast",              // 广播模式
  "clear_before_sync": false,
  "allow_insert": false,
  "should_run": true,
  "note": "A1各销售组阶段目标比例，读取数据字典变量"
}
```

### 2. 多字段映射规则 🆕

多字段映射允许在一个规则中同时处理多个字段，大幅简化配置：

#### 按项目类型分类统计

```json
{
  "source_table": "PMS-工时数据",
  "target_table": "部门工时汇总",
  "source_keys": ["主交付部门"],
  "target_keys": ["部门名称"],
  "multi_field_mappings": [
    {
      "source_field": "工时数",
      "target_field": "售前类工时",
      "conditions": [
        { "field": "项目类型", "op": "=", "value": "售前" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "合同类工时",
      "conditions": [
        { "field": "项目类型", "op": "=", "value": "合同" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "公共类工时",
      "conditions": [
        { "field": "项目类型", "op": "=", "value": "公共" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "研发类工时",
      "conditions": [
        { "field": "项目类型", "op": "=", "value": "研发" }
      ],
      "aggregation": "sum"
    }
  ],
  "clear_before_sync": true,
  "allow_insert": false,
  "should_run": true,
  "note": "部门工时汇总—>按项目类型分类统计"
}
```

#### 按月份统计工时

```json
{
  "source_table": "PMS-工时数据",
  "target_table": "部门项目工时汇总",
  "source_keys": ["主交付部门", "项目编号"],
  "target_keys": ["部门名称", "项目编号"],
  "multi_field_mappings": [
    {
      "source_field": "工时数",
      "target_field": "202501工时",
      "conditions": [
        { "field": "工时月份", "op": "=", "value": "202501" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "202502工时",
      "conditions": [
        { "field": "工时月份", "op": "=", "value": "202502" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "202503工时",
      "conditions": [
        { "field": "工时月份", "op": "=", "value": "202503" }
      ],
      "aggregation": "sum"
    }
    // ... 更多月份
  ],
  "clear_before_sync": true,
  "allow_insert": false,
  "should_run": true,
  "note": "部门项目工时汇总—>按月份统计工时数"
}
```

#### 按部门横向统计（含排除条件）

```json
{
  "source_table": "PMS-工时数据",
  "target_table": "项目横向工时汇总-非运维已验收",
  "source_keys": ["项目编号"],
  "target_keys": ["项目编号"],
  "multi_field_mappings": [
    {
      "source_field": "工时数",
      "target_field": "政务产品实施部",
      "conditions": [
        { "field": "主交付部门", "op": "=", "value": "政务产品实施部" },
        { "field": "工时日期晚于验收日", "op": "包含", "value": "T" }
      ],
      "exclude_conditions": [
        { "field": "项目类别", "op": "=", "value": "运维服务" }
      ],
      "aggregation": "sum"
    },
    {
      "source_field": "工时数",
      "target_field": "数据产品实施部",
      "conditions": [
        { "field": "主交付部门", "op": "=", "value": "数据产品实施部" },
        { "field": "工时日期晚于验收日", "op": "包含", "value": "T" }
      ],
      "exclude_conditions": [
        { "field": "项目类别", "op": "=", "value": "运维服务" }
      ],
      "aggregation": "sum"
    }
    // ... 更多部门
  ],
  "clear_before_sync": true,
  "allow_insert": false,
  "should_run": true,
  "note": "项目横向工时汇总-非运维已验收—>按部门统计"
}
```

### 3. 条件和操作符

#### 支持的操作符

| 操作符 | 说明 | 示例 |
|-------|------|------|
| `=` | 等于 | `{"field": "状态", "op": "=", "value": "已完成"}` |
| `!=` | 不等于 | `{"field": "状态", "op": "!=", "value": "草稿"}` |
| `>` | 大于 | `{"field": "金额", "op": ">", "value": "10000"}` |
| `>=` | 大于等于 | `{"field": "日期", "op": ">=", "value": "2025-01-01"}` |
| `<` | 小于 | `{"field": "金额", "op": "<", "value": "100000"}` |
| `<=` | 小于等于 | `{"field": "日期", "op": "<=", "value": "{报表截止时间}"}` |
| `包含` | 包含文本 | `{"field": "标识", "op": "包含", "value": "2025签单,验收"}` |

#### 多条件组合（AND逻辑）

```json
"conditions": [
  { "field": "合同签订日期", "op": ">=", "value": "2025-01-01" },
  { "field": "合同签订日期", "op": "<=", "value": "{报表截止时间}" },
  { "field": "签单标识", "op": "包含", "value": "2025签单" }
]
```

#### 排除条件示例

使用 `exclude_conditions` 排除特定数据：

```json
{
  "conditions": [
    {"field": "在建总标识", "op": "包含", "value": "自签已确未验"}
  ],
  "exclude_conditions": [
    {"field": "合同类型", "op": "包含", "value": "框架合同"}
  ]
}
```

### 4. 聚合类型详解

#### 聚合类型对照表

| 聚合类型 | 说明 | 适用场景 | 示例 |
|---------|------|----------|------|
| `sum` | 数值求和 | 金额汇总、数量统计 | 各部门工时总数 |
| `broadcast` | 广播到所有行 | 配置值分发、比例设置 | 阶段目标比例 |
| `latest` | 最新记录 | 状态更新、最新数据 | 项目基本信息 |
| `copy` | 直接复制 | 数据迁移、字段填充 | 底表数据生成 |
| `""` | 普通模式 | 一对一更新 | 人员信息同步 |

#### Latest模式示例

获取最新的项目信息：

```json
{
  "source_table": "PMS-工时数据",
  "target_table": "项目横向工时汇总",
  "source_keys": ["项目编号"],
  "target_keys": ["项目编号"],
  "source_fields": [
    "项目编号", "项目名称", "销售负责人", 
    "项目类型", "验收日", "项目类别"
  ],
  "target_fields": [
    "项目编号", "项目名称", "销售负责人",
    "项目类型", "验收日", "项目类别"
  ],
  "aggregation": "latest",
  "clear_before_sync": true,
  "allow_insert": true,
  "should_run": true,
  "note": "项目横向工时汇总—>基本字段"
}
```

### 5. 数据字典配置

数据字典用于定义可重用的变量：

```json
"data_dictionary": {
  "报表截止时间": "2025-07-31",              // 报表截止日期
  "2024签单截止时间": "2024-7-31",           // 2024年同期截止时间
  "2023签单截止时间": "2023-7-31",           // 2023年同期截止时间
  "阶段目标比例": "40%",                     // 阶段目标比例
  "预算计算年份": "2025",                    // 预算年份
  "签单计算年份": "2025",                    // 签单年份
  "签单起算日期": "2025-01-01"               // 签单起始日期
}
```

#### 变量使用方式

1. **在条件中使用**：
```json
{"field": "合同签订日期", "op": "<=", "value": "{报表截止时间}"}
```

2. **在broadcast模式中使用**：
```json
{
  "source_fields": ["阶段目标比例"],  // 从数据字典获取值
  "aggregation": "broadcast"
}
```

### 6. Latest聚合配置

用于配置latest聚合模式的行为：

```json
"latest_aggregation_config": {
  "enabled": true,                           // 启用最新记录功能
  "default_time_field": "录入时间",          // 默认时间字段
  "default_sort_order": "desc",              // 排序方式(desc/asc)
  "fallback_time_fields": [                  // 备选时间字段
    "创建时间", "更新时间", "修改时间"
  ],
  "field_fill_config": {                     // 字段填充配置
    "enabled": true,
    "fill_fields": [                         // 需要填充的字段
      "合同编号", "项目名称", "销售负责人", 
      "项目类别", "销售团队"
    ],
    "key_field": "项目编号"                  // 关键字段
  }
}
```

## 配置优化技巧

### 1. 单字段 vs 多字段映射

**优化前**（43条规则）：
```json
// 需要4个单独的规则
{"target_fields": ["售前类工时"], "conditions": [{"field": "项目类型", "op": "=", "value": "售前"}]},
{"target_fields": ["合同类工时"], "conditions": [{"field": "项目类型", "op": "=", "value": "合同"}]},
{"target_fields": ["公共类工时"], "conditions": [{"field": "项目类型", "op": "=", "value": "公共"}]},
{"target_fields": ["研发类工时"], "conditions": [{"field": "项目类型", "op": "=", "value": "研发"}]}
```

**优化后**（7条规则）：
```json
// 1个多字段映射规则搞定
{
  "multi_field_mappings": [
    {"target_field": "售前类工时", "conditions": [{"field": "项目类型", "op": "=", "value": "售前"}]},
    {"target_field": "合同类工时", "conditions": [{"field": "项目类型", "op": "=", "value": "合同"}]},
    {"target_field": "公共类工时", "conditions": [{"field": "项目类型", "op": "=", "value": "公共"}]},
    {"target_field": "研发类工时", "conditions": [{"field": "项目类型", "op": "=", "value": "研发"}]}
  ]
}
```

### 2. 配置文件模板

#### 项目统计配置模板
参考：`config/project_stats_config.json`
- 适用于项目收入、验收、签单统计
- 包含A1-A5、F1-F5系列报表

#### 工时统计配置模板  
参考：`config/worktime_stats_config.json`
- 适用于工时数据统计分析
- 支持部门、项目、月份多维度统计
- 大量使用多字段映射优化

## 📁 项目结构

```
sea-py-cv/
├── 📁 config/                        # 配置文件目录
│   └── project_stats_config.json    # 项目统计配置示例
├── 📁 .github/workflows/             # GitHub Actions 自动构建
│   └── build.yml                    # 多平台构建配置
├── 🐍 run_sync.py                    # 主程序入口
├── ⚡ fast_sync.py                   # 核心同步引擎
├── 🔌 seatable_official_adapter.py   # SeaTable API适配器
├── 🔨 build_standalone.py            # 构建脚本
├── 📋 requirements.txt               # Python依赖
├── 🔧 .env.example                   # 环境变量模板 (.env文件不会被提交)
├── 🛡️ .gitignore                     # Git忽略文件配置
├── 📄 README.md                      # 本文档
├── 📄 PREPROCESS_GUIDE.md            # 数据预处理指南
└── 📜 LICENSE                        # 开源许可证
```

## 💡 使用示例

### 可执行文件方式
```bash
# Windows - 使用.env配置
seatable-sync-windows.exe

# Linux/macOS - 使用.env配置  
./seatable-sync-linux

# 覆盖特定参数
./seatable-sync-linux --max-concurrent 10
```

### Python源码方式
```bash
# 使用.env文件配置
python run_sync.py

# 指定不同配置文件
python run_sync.py --config config/project_stats_config.json

# 完全自定义参数
python run_sync.py \
  --config config/custom_config.json \
  --token YOUR_TOKEN \
  --server-url https://cloud.seatable.cn \
  --max-concurrent 8
```

### 配置文件验证
```bash
python -c "import json; print('配置正确' if json.load(open('config/project_stats_config.json')) else '配置错误')"
```

## 性能优化

### 1. 配置优化

- **多字段映射**：减少规则数量，提升解析速度
- **条件合并**：将相似条件的规则合并
- **字段筛选**：只同步必需字段，减少数据传输

### 2. 批处理优化

程序会根据数据量自动调整批次大小：
- ≤100行：批次大小20
- ≤500行：批次大小30  
- >500行：批次大小50

### 3. 并发控制

默认并发数为5，可以根据SeaTable API限制调整：

```bash
# 可执行文件方式
./seatable-sync-linux --max-concurrent 10   # 高并发
./seatable-sync-linux --max-concurrent 3    # 低并发

# Python源码方式  
python run_sync.py --max-concurrent 10      # 高并发
python run_sync.py --max-concurrent 3       # 低并发

# 或在.env文件中设置
SEATABLE_MAX_CONCURRENT=10
```

### 4. 内存管理

程序在完成后会自动清理内存缓存，适合处理大量数据。

## 常见问题

### 1. API限流问题

如果遇到API限流，可以：
- 减少 `--max-concurrent` 参数
- 增加重试等待时间
- 检查批次大小设置

### 2. 数据类型匹配

- **百分比字段**：数据字典中使用字符串格式如 `"40%"`
- **日期字段**：使用 `YYYY-MM-DD` 格式
- **数值字段**：支持自动类型转换和因子计算

### 3. 字段名匹配

确保源表和目标表的字段名完全匹配，区分大小写。

### 4. 多条件逻辑

- **conditions内部**：AND逻辑（所有条件都要满足）
- **exclude_conditions**：排除逻辑（满足任一条件就排除）
- **多字段映射**：每个映射独立处理条件

### 5. 调试技巧

查看详细日志信息：

```bash
# 可执行文件方式
./seatable-sync-linux                       # INFO级别日志
./seatable-sync-linux --help               # 查看帮助信息

# Python源码方式
python run_sync.py                          # INFO级别日志  
python run_sync.py --help                  # 查看帮助信息
```

查看配置文件统计：
```bash
python -c "
import json
with open('config/project_stats_config.json') as f:
    config = json.load(f)
    rules = config.get('sync_rules', [])
    multi_rules = [r for r in rules if 'multi_field_mappings' in r]
    single_rules = [r for r in rules if 'multi_field_mappings' not in r]
    print(f'总规则数: {len(rules)}')
    print(f'多字段映射规则: {len(multi_rules)}')
    print(f'单字段规则: {len(single_rules)}')
    if multi_rules:
        total_mappings = sum(len(r['multi_field_mappings']) for r in multi_rules)
        print(f'等效单字段规则数: {len(single_rules) + total_mappings}')
"
```

## 🔄 更新日志

### v4.0 (最新) - 跨平台构建支持
- 🚀 **GitHub Actions 自动构建** - 支持Windows/Linux/macOS三平台
- 🔧 **.env文件支持** - 简化配置管理，提升Windows兼容性
- 📦 **单文件可执行程序** - 无需Python环境，开箱即用
- 🎛️ **灵活配置优先级** - 命令行参数 > .env文件 > 默认值

### v3.0 - 多字段映射支持
- 🆕 **多字段映射支持** - 配置文件优化84%，支持条件级别的字段映射
- 📝 **配置文件大幅简化** - 从43条规则减少到7条规则

### v2.x - 核心功能
- **v2.1** - 完善底表同步、事业部分拆、多字段映射支持
- **v2.0** - 重构为fast_sync引擎，大幅提升性能
- **v1.5** - 增加广播模式和数据字典支持  
- **v1.0** - 基础同步功能和聚合计算

## 🆘 技术支持

### 常见问题
1. **Token错误**: 检查API Token是否有效，是否有表格访问权限
2. **配置文件错误**: 验证JSON格式，检查字段名是否匹配
3. **网络问题**: 确认能访问SeaTable服务器
4. **性能问题**: 调整并发数和批次大小

### 获取帮助
- 📖 **查看文档**: 详细配置说明见本README和PREPROCESS_GUIDE.md
- 🐛 **报告问题**: 提交Issue到GitHub仓库
- 💻 **源码研究**: 查看源码中的详细注释和示例

### 支持的SeaTable版本
- ☁️ **SeaTable云服务版** (cloud.seatable.cn)
- 🏢 **SeaTable私有部署版** (自定义域名)
- 📱 **SeaTable API v2.x** 及以上版本

## 📄 开源许可

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。