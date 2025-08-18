#!/usr/bin/env python3
"""
Windows构建修复脚本
解决PyInstaller在Windows上的常见问题
"""

import os
import sys
import subprocess
import platform

def check_vcredist():
    """检查Visual C++ Redistributable"""
    print("检查Visual C++ Redistributable...")
    
    # 检查注册表中的VC++ Redistributable
    try:
        import winreg
        key_paths = [
            r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        
        for key_path in key_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                print(f"[OK] 找到VC++ Redistributable: {key_path}")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                continue
                
        print("[WARNING] 未找到Visual C++ Redistributable")
        print("请下载安装: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return False
        
    except ImportError:
        print("[INFO] 无法检查注册表，请确保已安装Visual C++ Redistributable")
        return True

def fix_pyinstaller_build():
    """修复PyInstaller构建问题"""
    print("\n开始修复Windows构建问题...")
    
    # 1. 升级PyInstaller到最新版本
    print("1. 升级PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"], check=True)
        print("[OK] PyInstaller升级完成")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] PyInstaller升级失败: {e}")
        return False
    
    # 2. 清理旧的构建文件
    print("2. 清理旧构建文件...")
    cleanup_dirs = ["build", "dist", "__pycache__"]
    for dir_name in cleanup_dirs:
        if os.path.exists(dir_name):
            import shutil
            shutil.rmtree(dir_name)
            print(f"[OK] 清理目录: {dir_name}")
    
    # 清理.spec文件
    for file in os.listdir("."):
        if file.endswith(".spec"):
            os.remove(file)
            print(f"[OK] 清理文件: {file}")
    
    # 3. 创建兼容性构建脚本
    build_script = """
import sys
import subprocess

# Windows兼容构建命令
cmd = [
    "pyinstaller",
    "--onefile",
    "--console", 
    "--name", "seatable-sync-windows",
    "--noupx",
    "--clean",
    "--noconfirm",
    "--collect-all", "seatable_api",
    "--collect-all", "aiohttp", 
    "--collect-all", "asyncio",
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
    "--add-data", "config;config" if os.path.exists("config") else "",
    "run_sync.py"
]

# 移除空字符串
cmd = [c for c in cmd if c]

print("执行构建命令:")
print(" ".join(cmd))

subprocess.run(cmd, check=True)
"""
    
    with open("build_windows_compatible.py", "w", encoding="utf-8") as f:
        f.write(build_script)
    
    print("[OK] 创建兼容性构建脚本: build_windows_compatible.py")
    
    # 4. 创建运行时修复批处理文件
    batch_content = """@echo off
echo Starting SeaTable Sync Tool...
echo.

REM 设置编码为UTF-8
chcp 65001 > nul

REM 检查.env文件
if not exist .env (
    echo [INFO] .env file not found, creating from template...
    if exist .env.example (
        copy .env.example .env
        echo [INFO] Please edit .env file with your settings
        pause
    )
)

REM 运行程序
seatable-sync-windows.exe %*

REM 暂停以查看输出
if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error code: %errorlevel%
    echo.
    pause
)
"""
    
    with open("run_seatable_sync.bat", "w", encoding="gbk") as f:
        f.write(batch_content)
    
    print("[OK] 创建Windows启动脚本: run_seatable_sync.bat")
    
    return True

def create_deployment_guide():
    """创建部署指南"""
    guide_content = """# Windows部署问题解决指南

## 错误：Failed to load Python DLL

### 原因分析：
1. 缺少Microsoft Visual C++ Redistributable
2. PyInstaller版本兼容性问题
3. Windows系统权限问题

### 解决方案：

#### 步骤1：安装Visual C++ Redistributable
下载并安装最新版本：
https://aka.ms/vs/17/release/vc_redist.x64.exe

#### 步骤2：重新构建（在Windows机器上）
```bash
python fix_windows_build.py
python build_windows_compatible.py
```

#### 步骤3：使用批处理文件运行
```cmd
run_seatable_sync.bat
```

### 高级解决方案：

#### 方案A：使用onedir模式（推荐）
修改构建脚本，使用`--onedir`替代`--onefile`：
- 文件较大但兼容性更好
- 包含所有DLL文件

#### 方案B：指定Python路径
在目标机器上安装相同版本Python，设置环境变量。

#### 方案C：使用Docker容器
```bash
docker run -v $(pwd):/app python:3.9-windowsservercore-ltsc2019
```

### 常见问题：

1. **权限问题**：以管理员身份运行
2. **防病毒软件**：添加程序到白名单
3. **网络问题**：检查防火墙设置
4. **编码问题**：确保使用UTF-8编码

### 测试清单：
- [ ] 安装VC++ Redistributable
- [ ] 重新构建exe文件
- [ ] 配置.env文件
- [ ] 测试网络连接
- [ ] 验证API Token权限
"""
    
    with open("WINDOWS_DEPLOYMENT_GUIDE.md", "w", encoding="utf-8") as f:
        f.write(guide_content)
    
    print("[OK] 创建部署指南: WINDOWS_DEPLOYMENT_GUIDE.md")

def main():
    print("Windows构建修复工具")
    print("=" * 50)
    
    if not sys.platform.startswith("win"):
        print("[INFO] 当前不是Windows系统，但仍可生成修复脚本")
    
    # 检查系统依赖
    if sys.platform.startswith("win"):
        check_vcredist()
    
    # 修复构建配置
    if fix_pyinstaller_build():
        print("\n[SUCCESS] 修复脚本生成完成！")
    else:
        print("\n[ERROR] 修复失败")
        return False
    
    # 创建部署指南
    create_deployment_guide()
    
    print("\n下一步操作：")
    print("1. 在Windows机器上运行: python build_windows_compatible.py")
    print("2. 分发整个文件夹，包含.bat启动脚本")
    print("3. 参考 WINDOWS_DEPLOYMENT_GUIDE.md 解决部署问题")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)