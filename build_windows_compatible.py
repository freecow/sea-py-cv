
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
