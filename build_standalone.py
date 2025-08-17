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
    print("   Building SeaTable Sync Tool")
    print("====================================")
    
    # 1. Install dependencies
    print("1. Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 2. Clean old files
    print("\n2. Cleaning previous build files...")
    for folder in ["dist", "build"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)
    
    # 3. Collect config files
    config_files = []
    if os.path.exists("config"):
        config_files = [f"config/{f}" for f in os.listdir("config") if f.endswith(".json")]
    print(f"\n3. Found config files: {', '.join(config_files)}")
    
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
    
    print(f"\n4. Executing build command...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n[OK] Build successful!")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed: {e}")
        return False
    
    # 5. Create deployment package
    print("\n5. Creating deployment package...")
    
    # Create deployment directory
    deploy_dir = "seatable-sync-deploy"
    if os.path.exists(deploy_dir):
        shutil.rmtree(deploy_dir)
    os.makedirs(deploy_dir)
    
    # Copy executable file
    exe_name = "seatable-sync.exe" if sys.platform.startswith("win") else "seatable-sync"
    src_exe = os.path.join("dist", exe_name)
    dst_exe = os.path.join(deploy_dir, exe_name)
    
    if os.path.exists(src_exe):
        shutil.copy2(src_exe, dst_exe)
        print(f"[OK] Copied executable: {exe_name}")
    else:
        print(f"[ERROR] Executable not found: {src_exe}")
        return False
    
    # Copy config folder
    if os.path.exists("config"):
        shutil.copytree("config", os.path.join(deploy_dir, "config"))
        print("[OK] Copied config folder")
    
    # Copy .env example file
    if os.path.exists(".env.example"):
        shutil.copy2(".env.example", deploy_dir)
        print("[OK] Copied .env example file")
    
    # Copy documentation
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
    
    with open(os.path.join(deploy_dir, "USAGE.txt"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("\n====================================")
    print("[SUCCESS] Deployment package created successfully!")
    print(f"Package location: {deploy_dir}/")
    print(f"Executable: {deploy_dir}/{exe_name}")
    print("Share the entire folder with your team")
    print("====================================")
    
    return True

if __name__ == "__main__":
    success = create_standalone_build()
    if not success:
        sys.exit(1)