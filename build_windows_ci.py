#!/usr/bin/env python3
"""
Windows CI专用构建脚本
解决GitHub Actions中的Windows PyInstaller问题
"""

import os
import sys
import subprocess
import shutil

def build_windows_executable():
    print("Windows CI Build Starting...")
    
    # 清理旧文件
    for folder in ["dist", "build"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)
    
    # Windows优化的PyInstaller命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",
        "--name", "seatable-sync-windows",
        "--noupx",              # 禁用UPX压缩
        "--clean",              # 清理缓存
        "--noconfirm",          # 不确认覆盖
        "--collect-all", "seatable_api",
        "--collect-all", "aiohttp",
        "--hidden-import", "seatable_api",
        "--hidden-import", "aiohttp", 
        "--hidden-import", "asyncio",
        "--hidden-import", "dateutil",
        "--hidden-import", "colorlog",
        "--hidden-import", "typing_extensions", 
        "--hidden-import", "dotenv",
        "--hidden-import", "json",
        "--hidden-import", "datetime",
        "--hidden-import", "ssl",
        "--hidden-import", "socket",
        "--hidden-import", "urllib3",
        "--hidden-import", "certifi",
        "--hidden-import", "charset_normalizer"
    ]
    
    # 添加配置文件
    if os.path.exists("config"):
        cmd.extend(["--add-data", "config;config"])
    
    # 添加主文件
    cmd.append("run_sync.py")
    
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build Output:")
        print(result.stdout)
        if result.stderr:
            print("Build Warnings:")
            print(result.stderr)
        print("[SUCCESS] Windows executable built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

if __name__ == "__main__":
    success = build_windows_executable()
    if not success:
        sys.exit(1)