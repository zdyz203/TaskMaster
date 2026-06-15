#!/usr/bin/env bash
# 在 Mac (Apple Silicon) 上一键打包 .app 并生成 .dmg。
# 用法: chmod +x build_mac.sh && ./build_mac.sh
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "错误: 这个脚本只能在 macOS 上运行" >&2
  exit 1
fi

ARCH="$(uname -m)"
echo "==> 当前架构: $ARCH (期望 arm64)"

PY="${PYTHON:-python3}"
echo "==> 使用 Python: $($PY --version)"

# 1) 创建虚拟环境（隔离干净环境，避免污染系统）
if [[ ! -d .venv-build ]]; then
  echo "==> 创建虚拟环境 .venv-build"
  "$PY" -m venv .venv-build
fi
# shellcheck disable=SC1091
source .venv-build/bin/activate

# 2) 装依赖
echo "==> 安装依赖"
pip install --upgrade pip wheel >/dev/null
pip install -r requirements.txt
pip install pyinstaller

# 3) 清理旧产物
rm -rf build dist

# 4) PyInstaller 打 .app
echo "==> PyInstaller 打包 .app"
pyinstaller TaskMaster.spec --noconfirm --clean

APP_PATH="dist/TaskMaster.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "错误: 没有生成 $APP_PATH" >&2
  exit 1
fi

# 4b) 把 notify.py 也打成独立二进制 —— 让 Claude Code hook 不依赖系统 python3。
# 用 --onefile 单文件 + --console (终端模式),放进 .app/Contents/MacOS/notify,
# 与主程序同目录,后面的 codesign --deep 会一起签名。
echo "==> PyInstaller 打包 notify (独立 hook 二进制)"
pyinstaller --onefile --console --name notify \
  --distpath dist/notify-bin --workpath build/notify --specpath build/notify \
  --target-arch arm64 --noconfirm --clean notify.py
NOTIFY_BIN="dist/notify-bin/notify"
if [[ ! -f "$NOTIFY_BIN" ]]; then
  echo "错误: 没有生成 $NOTIFY_BIN" >&2
  exit 1
fi
cp "$NOTIFY_BIN" "$APP_PATH/Contents/MacOS/notify"
chmod +x "$APP_PATH/Contents/MacOS/notify"

# 5) ad-hoc 签名 — 没有开发者证书时也能在本机直接打开
echo "==> ad-hoc 签名 .app"
codesign --force --deep --sign - "$APP_PATH"

# 6) 生成 .dmg —— 优先 create-dmg，没装就用 hdiutil 兜底
DMG_PATH="dist/TaskMaster-1.0.0-arm64.dmg"
rm -f "$DMG_PATH"

if command -v create-dmg >/dev/null 2>&1; then
  echo "==> create-dmg 生成 dmg"
  create-dmg \
    --volname "TaskMaster" \
    --window-pos 200 120 \
    --window-size 600 360 \
    --icon-size 100 \
    --icon "TaskMaster.app" 150 180 \
    --hide-extension "TaskMaster.app" \
    --app-drop-link 450 180 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$APP_PATH"
else
  echo "==> create-dmg 未安装,使用 hdiutil 简化打包 (brew install create-dmg 可获得拖拽美化界面)"
  TMP_DIR="$(mktemp -d)"
  cp -R "$APP_PATH" "$TMP_DIR/"
  ln -s /Applications "$TMP_DIR/Applications"
  hdiutil create -volname "TaskMaster" \
    -srcfolder "$TMP_DIR" \
    -ov -format ULFO \
    "$DMG_PATH"
  rm -rf "$TMP_DIR"
fi

echo ""
echo "完成: $DMG_PATH"
ls -lh "$DMG_PATH"
