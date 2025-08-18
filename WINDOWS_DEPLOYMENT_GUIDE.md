# Windows部署问题解决指南

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
