# TaskMaster Windows 一键打包脚本
# 用法: powershell -ExecutionPolicy Bypass -File build_win.ps1
# 产物: dist\TaskMaster-1.0.0-Setup.exe

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if ($env:OS -ne 'Windows_NT') {
    Write-Error '这个脚本只能在 Windows 上运行'
}

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
Write-Host "==> 使用 Python: $(& $python --version)"

# 1) 虚拟环境
if (-not (Test-Path '.venv-build')) {
    Write-Host '==> 创建虚拟环境 .venv-build'
    & $python -m venv .venv-build
}
$venvPython = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
$venvPip = Join-Path $PSScriptRoot '.venv-build\Scripts\pip.exe'

# 2) 装依赖
Write-Host '==> 安装依赖'
& $venvPython -m pip install --upgrade pip wheel | Out-Null
& $venvPip install -r requirements.txt
& $venvPip install pyinstaller

# 3) 清理旧产物
if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
if (Test-Path 'dist')  { Remove-Item -Recurse -Force 'dist' }

# 4) PyInstaller
Write-Host '==> PyInstaller 打包'
$pyinstaller = Join-Path $PSScriptRoot '.venv-build\Scripts\pyinstaller.exe'
& $pyinstaller TaskMaster.win.spec --noconfirm --clean
if (-not (Test-Path 'dist\TaskMaster\TaskMaster.exe')) {
    Write-Error '错误: 没有生成 dist\TaskMaster\TaskMaster.exe'
}

# 5) Inno Setup 编译 —— 找 ISCC.exe;装了 Inno Setup 6 默认就在这儿
$candidates = @(
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    'ISCC.exe'  # 走 PATH
)
$iscc = $null
foreach ($c in $candidates) {
    if ($c -eq 'ISCC.exe') {
        $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source; break }
    } elseif (Test-Path $c) {
        $iscc = $c; break
    }
}
if (-not $iscc) {
    Write-Error '错误: 找不到 ISCC.exe。请安装 Inno Setup 6 (https://jrsoftware.org/isdl.php) 或加入 PATH'
}
Write-Host "==> Inno Setup 编译: $iscc"
& $iscc 'installer.iss'

$setup = Get-ChildItem 'dist\TaskMaster-*-Setup.exe' | Select-Object -First 1
if (-not $setup) {
    Write-Error '错误: 没有生成安装包'
}
Write-Host ''
Write-Host "完成: $($setup.FullName)"
Write-Host ('大小: {0:N2} MB' -f ($setup.Length / 1MB))
