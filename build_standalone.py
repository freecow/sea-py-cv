#!/usr/bin/env python3
"""
独立打包脚本
创建完全自包含的可执行文件，包含所有配置文件
"""

import os
import sys
import shutil
import subprocess
import json

def create_standalone_build():
    print("====================================")
    print("   创建SeaTable同步工具部署包")
    print("====================================")
    
    # 1. 安装依赖
    print("1. 安装依赖包...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 2. 清理旧文件
    print("\n2. 清理之前的构建文件...")
    for folder in ["dist", "build"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)
    
    # 3. 收集配置文件
    config_files = []
    if os.path.exists("config"):
        config_files = [f"config/{f}" for f in os.listdir("config") if f.endswith(".json")]
    print(f"\n3. 找到配置文件: {', '.join(config_files)}")
    
    # 4. 构建PyInstaller命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",
        "--name", "seatable-sync",
        "--hidden-import", "seatable_api",
        "--hidden-import", "aiohttp",
        "--hidden-import", "asyncio",
        "--hidden-import", "dateutil",
        "--hidden-import", "colorlog",
        "--hidden-import", "typing_extensions",
        "--hidden-import", "dotenv",
        "--hidden-import", "json",
        "--hidden-import", "datetime"
    ]
    
    # 添加配置文件夹
    if os.path.exists("config"):
        cmd.extend(["--add-data", "config:config"])
    
    # 添加主要文件
    main_files = ["run_sync.py", "fast_sync.py", "seatable_official_adapter.py"]
    for main_file in main_files:
        if os.path.exists(main_file):
            cmd.extend(["--add-data", f"{main_file}:."])
    
    # 添加主文件
    cmd.append("run_sync.py")
    
    print(f"\n4. 执行打包命令...")
    print(f"命令: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ 打包成功！")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败: {e}")
        return False
    
    # 5. 创建部署包
    print("\n5. 创建部署包...")
    
    # 创建部署目录
    deploy_dir = "seatable-sync-deploy"
    if os.path.exists(deploy_dir):
        shutil.rmtree(deploy_dir)
    os.makedirs(deploy_dir)
    
    # 复制可执行文件
    exe_name = "seatable-sync.exe" if sys.platform.startswith("win") else "seatable-sync"
    src_exe = os.path.join("dist", exe_name)
    dst_exe = os.path.join(deploy_dir, exe_name)
    
    if os.path.exists(src_exe):
        shutil.copy2(src_exe, dst_exe)
        print(f"✅ 复制可执行文件: {exe_name}")
    else:
        print(f"❌ 找不到可执行文件: {src_exe}")
        return False
    
    # 复制配置文件夹
    if os.path.exists("config"):
        shutil.copytree("config", os.path.join(deploy_dir, "config"))
        print("✅ 复制配置文件夹")
    
    # 复制.env示例文件
    if os.path.exists(".env.example"):
        shutil.copy2(".env.example", deploy_dir)
        print("✅ 复制.env示例文件")
    
    # 复制文档
    if os.path.exists("README.md"):
        shutil.copy2("README.md", deploy_dir)
    if os.path.exists("PREPROCESS_GUIDE.md"):
        shutil.copy2("PREPROCESS_GUIDE.md", deploy_dir)
    
    # 创建使用说明
    readme_content = """# SeaTable 快速同步工具部署包

## 使用步骤：

1. 配置环境变量（推荐）：
   cp .env.example .env
   编辑 .env 文件，填入你的SeaTable Token

2. 运行同步工具：
   # Windows:
   seatable-sync.exe
   
   # Linux/macOS:
   ./seatable-sync

## 配置方式：

### 方式1: .env文件配置（推荐）
1. 复制 .env.example 为 .env
2. 编辑 .env 文件，填入配置信息
3. 直接运行: ./seatable-sync

### 方式2: 命令行参数
./seatable-sync --config config/project_stats_config.json --token YOUR_TOKEN

## 配置说明：

- 该可执行文件已包含所有依赖和配置模板
- 支持多种聚合模式：sum, broadcast, latest, copy
- 支持多字段映射，减少配置复杂度
- 完整的数据字典支持
- 跨平台支持（Windows, Linux, macOS）

## 命令行参数：

--config, -c     配置文件路径 (默认: config/sync_rules.json)
--token, -t      SeaTable API Token (可从.env文件读取)
--server-url, -s SeaTable服务器URL (默认: https://cloud.seatable.cn)
--max-concurrent 最大并发请求数 (默认: 5)

## 示例用法：

# 使用.env文件配置（推荐）
./seatable-sync

# 指定不同配置文件
./seatable-sync --config config/project_stats_config.json

# 命令行覆盖配置
./seatable-sync --token YOUR_TOKEN --max-concurrent 10

## 注意事项：

- 确保网络能访问SeaTable服务
- 确保API Token有相应的表格权限
- 首次运行可能需要管理员权限（某些系统）
- 配置优先级：命令行参数 > .env文件 > 默认值
- 查看README.md获取完整文档
"""
    
    with open(os.path.join(deploy_dir, "使用说明.txt"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("\n====================================")
    print("🎉 部署包创建完成！")
    print(f"📁 部署包位置: {deploy_dir}/")
    print(f"🚀 可执行文件: {deploy_dir}/{exe_name}")
    print("📋 请将整个文件夹发送给同事")
    print("====================================")
    
    return True

if __name__ == "__main__":
    success = create_standalone_build()
    if not success:
        sys.exit(1)