# TaskMaster

桌面置顶小浮窗，按 Claude Code 的 `session_id` 区分多窗口，两行展示：上行最近收到的 message，下行当前状态。

| 状态 | 边框 / 文字色 | 含义 |
|---|---|---|
| 空闲中 | 灰 | 等待新一轮交互 |
| 工作中 | 绿 | 正在处理工具调用或回复 |
| 待确认 | 黄 | 阻塞等待用户输入（如权限确认） |

## 状态机

每个 session 维护自己的窗口；窗口的状态由 Claude Code hook 事件驱动：

| Hook 事件 | 动作 |
|---|---|
| `SessionStart` | 创建新浮窗，状态置为 **空闲中** |
| `UserPromptSubmit` / `PreToolUse` / `PostToolUse` | 状态置为 **工作中** |
| `Stop` / `SubagentStop` | 状态置为 **空闲中** |
| `Notification` | 若上一个事件不是 `Stop` / `SubagentStop`，置为 **待确认**；否则忽略 |
| `SessionEnd` | 关闭对应浮窗 |

## 安装

```powershell
pip install -r requirements.txt
```

## 启动

```powershell
python main.py
```

浮窗出现在屏幕右上角，可拖动。
- **左键拖动**：移动位置
- **右键菜单**：手动切状态 / 关闭此浮窗 / 退出
- **托盘图标**：显示/隐藏全部 / 退出

## 接入 Claude Code Hooks

安装包已经把 `notify.py` 打成了独立可执行文件,Claude Code hook 直接调用它,**最终用户机器无需安装 Python**。

### Windows

把 `hooks.example.json` 的内容合并到 `~/.claude/settings.json`,把 `PATH_TO` 替换成安装目录:
- 当前用户安装(默认):`%LOCALAPPDATA%\Programs\TaskMaster`
- 全局安装:`C:\Program Files\TaskMaster`

所有 hook 都调用同一个 `notify.exe`,事件名和 `session_id` 从 stdin 的 hook payload 自动读取,浮窗主程序按 session 路由。

### macOS

参考 `hooks.example.macos.json`,合并到 `~/.claude/settings.json`。`.dmg` 安装后 `notify` 位于 `/Applications/TaskMaster.app/Contents/MacOS/notify`,模板里已经填好这个路径。

### 从源码运行(开发者)

源码运行时 hook 命令仍走系统 Python:`python /path/to/notify.py`(Windows)或 `python3 /path/to/notify.py`(macOS),保留兼容。

## Windows 安装（.exe）

### 用户安装

1. 下载 `TaskMaster-1.0.0-Setup.exe` 双击运行。安装包默认走当前用户目录，不需要管理员权限；如果勾选「为所有用户安装」会请求 UAC 提权。
2. 安装向导可选项：
   - **桌面快捷方式**（默认不勾）
   - **开机自动启动**（默认不勾，原理是把快捷方式放到 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`，无需注册表权限）
3. 启动后没有主窗口，托盘图标和右上角浮窗即正常状态；首次监听本地 7878 端口时 Windows Defender 防火墙可能弹提示，允许「专用网络」即可。
4. 配置 hooks：把 `hooks.example.json` 合并到 `~/.claude/settings.json`，把 `PATH_TO` 替换成安装目录（默认 `%LOCALAPPDATA%\Programs\TaskMaster`，全局安装则是 `C:\Program Files\TaskMaster`）。安装包已捆绑 `notify.exe`，无需系统装 Python。
5. 卸载：「设置 → 应用 → TaskMaster → 卸载」或「控制面板 → 程序」。

### 开发者从源码打包

需要 Python 3.10+ 和 [Inno Setup 6](https://jrsoftware.org/isdl.php)（`ISCC.exe` 在 `C:\Program Files (x86)\Inno Setup 6\`）：

```powershell
powershell -ExecutionPolicy Bypass -File build_win.ps1
# 产物: dist\TaskMaster-1.0.0-Setup.exe
```

脚本会:创建 `.venv-build` 隔离环境 → `pip install -r requirements.txt` + PyInstaller → 按 `TaskMaster.win.spec` 打主程序 + 单独打一份 `notify.exe` 到 `dist/TaskMaster/` → ISCC 编译 `installer.iss` 生成单文件 Setup.exe。

### 通过 GitHub Actions 云端打包

仓库带 `.github/workflows/build-win.yml`，windows-latest runner 自带 Inno Setup：

- Actions 页面手动触发，或
- 推 tag：`git tag v1.0.0 && git push --tags`，产物自动挂到 Release。

## macOS 安装（.dmg）

### 用户安装

1. 双击 `TaskMaster-1.0.0-arm64.dmg`，把 `TaskMaster.app` 拖到 `Applications`。
2. **首次启动会被 Gatekeeper 拦截**（因为没有 Apple Developer ID 签名）。任选一种方式放行：
   - **图形界面**：双击启动 → 弹窗提示"无法打开" → 打开「系统设置 → 隐私与安全性」 → 滚到底部点「仍要打开」。
   - **终端一行**：
     ```bash
     xattr -dr com.apple.quarantine /Applications/TaskMaster.app
     ```
3. 启动后 app 不会出现在 Dock（由 `LSUIElement=true` 控制），只在菜单栏托盘和右上角浮窗展示。
4. 首次监听本地 7878 端口时系统可能弹防火墙提示，允许即可。
5. 配置 hooks：把 `hooks.example.macos.json` 合并到 `~/.claude/settings.json`。

### 开发者从源码打包

需要一台 Apple Silicon Mac（arm64）：

```bash
chmod +x build_mac.sh
brew install create-dmg   # 可选；未安装会自动 fallback 到 hdiutil
./build_mac.sh
# 产物: dist/TaskMaster-1.0.0-arm64.dmg
```

脚本会:创建 `.venv-build` 隔离环境 → `pip install -r requirements.txt` + PyInstaller → 按 `TaskMaster.spec` 打 `.app` → 额外打一份 `notify` 二进制并放进 `.app/Contents/MacOS/` → ad-hoc 签名 → `create-dmg` 制作拖拽式 DMG。

### 通过 GitHub Actions 云端打包

不需要本地 Mac。仓库已带 `.github/workflows/build-mac.yml`：

- 在 Actions 页面手动触发（`workflow_dispatch`），或
- 推 tag：`git tag v1.0.0 && git push --tags`，产物会自动挂到 Release。

runner 用 `macos-14`（Apple Silicon），产物上传为 `TaskMaster-macos-arm64` artifact。

## HTTP 协议

主程序在 `127.0.0.1:7878` 监听：

```
POST /event
Content-Type: application/json

{ "event": "PreToolUse", "session_id": "abc123", "message": "Bash" }
```

合法 `event`（大小写不敏感）：`SessionStart` / `UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop` / `SubagentStop` / `Notification` / `SessionEnd`。

手动调试：

```powershell
python notify.py --event SessionStart --session demo
python notify.py --event PreToolUse   --session demo --message "Bash: ls"
python notify.py --event Notification --session demo --message "需要确认"
python notify.py --event SessionEnd   --session demo
```

## 文件结构

- `main.py` — 浮窗主程序（多窗口 UI + HTTP 服务 + 状态机）
- `notify.py` — Claude Code hook 适配脚本（读 stdin → 推 HTTP）
- `hooks.example.json` — Windows hooks 配置模板
- `hooks.example.macos.json` — macOS hooks 配置模板
- `requirements.txt` — 依赖
- `TaskMaster.spec` — PyInstaller 打包配置（macOS）
- `TaskMaster.win.spec` — PyInstaller 打包配置（Windows）
- `build_mac.sh` — macOS 一键打 `.dmg` 脚本
- `build_win.ps1` — Windows 一键打 `Setup.exe` 脚本
- `installer.iss` — Inno Setup 安装包脚本（Windows）
- `.github/workflows/build-mac.yml` — GitHub Actions macOS 云端打包
- `.github/workflows/build-win.yml` — GitHub Actions Windows 云端打包
