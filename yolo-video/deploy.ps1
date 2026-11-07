# YOLOv8实时人体检测系统 - PowerShell部署脚本
# 适配Windows PowerShell和PowerShell Core

param(
    [switch]$SkipTest,
    [switch]$AutoStart,
    [string]$RTSPUrl = ""
)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "YOLOv8实时人体检测系统 - 自动部署脚本" -ForegroundColor Cyan
Write-Host "硬件优化: RTX 4060 + i9-13900HX" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "建议以管理员权限运行此脚本以确保完整功能"
}

# 检查conda安装
try {
    $condaVersion = & conda --version 2>$null
    Write-Host "✅ 发现Conda: $condaVersion" -ForegroundColor Green
} catch {
    Write-Error "❌ 未发现Conda，请先安装Anaconda或Miniconda"
    Write-Host "下载地址: https://www.anaconda.com/download" -ForegroundColor Yellow
    exit 1
}

# 检查CUDA支持
try {
    $nvidiaOutput = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
    if ($nvidiaOutput) {
        Write-Host "✅ 发现GPU: $nvidiaOutput" -ForegroundColor Green
    } else {
        Write-Warning "⚠️ 未检测到NVIDIA GPU，将使用CPU模式"
    }
} catch {
    Write-Warning "⚠️ 未检测到nvidia-smi，GPU支持可能不可用"
}

# 检查模型文件
if (Test-Path "yolov8n.pt") {
    Write-Host "✅ 模型文件已存在" -ForegroundColor Green
} else {
    Write-Error "❌ 模型文件 yolov8n.pt 不存在"
    Write-Host "请确保YOLOv8模型文件在当前目录" -ForegroundColor Yellow
    exit 1
}

# 更新RTSP配置
if ($RTSPUrl) {
    Write-Host "🔧 更新RTSP配置..." -ForegroundColor Yellow
    $configContent = Get-Content "config.env" -Raw
    $configContent = $configContent -replace "RTSP_URL=.*", "RTSP_URL=$RTSPUrl"
    Set-Content "config.env" $configContent -Encoding UTF8
    Write-Host "✅ RTSP地址已更新" -ForegroundColor Green
}

# 创建或更新conda环境
Write-Host "📦 设置conda环境..." -ForegroundColor Yellow

$envExists = & conda env list | Select-String "yolo-detection"
if ($envExists) {
    Write-Host "发现现有环境 yolo-detection" -ForegroundColor Yellow
    $choice = Read-Host "是否重新创建环境? (y/n)"
    if ($choice -eq "y" -or $choice -eq "Y") {
        Write-Host "删除旧环境..." -ForegroundColor Yellow
        & conda env remove -n yolo-detection -y
        & conda env create -f environment.yml
    }
} else {
    Write-Host "创建新环境..." -ForegroundColor Yellow
    & conda env create -f environment.yml
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Conda环境创建失败"
    exit 1
}

Write-Host "✅ Conda环境设置完成" -ForegroundColor Green

# 系统测试
if (-not $SkipTest) {
    Write-Host "🧪 运行系统测试..." -ForegroundColor Yellow
    
    # 激活环境并运行测试
    $testCommand = @"
& conda activate yolo-detection
if (`$LASTEXITCODE -eq 0) {
    python test_system.py
} else {
    Write-Error "环境激活失败"
    exit 1
}
"@
    
    Invoke-Expression $testCommand
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "⚠️ 系统测试发现问题，请检查输出"
        $continueChoice = Read-Host "是否继续部署? (y/n)"
        if ($continueChoice -ne "y" -and $continueChoice -ne "Y") {
            exit 1
        }
    }
}

# 创建快捷方式
Write-Host "🔗 创建桌面快捷方式..." -ForegroundColor Yellow

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "YOLOv8人体检测.lnk"))
$Shortcut.TargetPath = Join-Path $PWD "start.bat"
$Shortcut.WorkingDirectory = $PWD
$Shortcut.Description = "YOLOv8实时人体检测系统"
$Shortcut.Save()

Write-Host "✅ 桌面快捷方式已创建" -ForegroundColor Green

# 防火墙配置提示
Write-Host "🔥 防火墙配置提示:" -ForegroundColor Yellow
Write-Host "   系统将使用端口 8000，请确保防火墙允许此端口" -ForegroundColor White
Write-Host "   如需外部访问，请配置路由器端口转发" -ForegroundColor White

# 显示完成信息
Write-Host "`n=================================================" -ForegroundColor Cyan
Write-Host "🎉 部署完成!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 文件位置:" -ForegroundColor White
Write-Host "   主程序: $(Join-Path $PWD 'main.py')" -ForegroundColor Gray
Write-Host "   配置文件: $(Join-Path $PWD 'config.env')" -ForegroundColor Gray
Write-Host "   测试客户端: $(Join-Path $PWD 'client.html')" -ForegroundColor Gray
Write-Host ""
Write-Host "🚀 启动方式:" -ForegroundColor White
Write-Host "   方式1: 双击桌面上的 'YOLOv8人体检测' 快捷方式" -ForegroundColor Gray
Write-Host "   方式2: 运行 start.bat" -ForegroundColor Gray
Write-Host "   方式3: conda activate yolo-detection && python main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "🌐 访问地址:" -ForegroundColor White
Write-Host "   服务API: http://localhost:8000" -ForegroundColor Gray
Write-Host "   健康检查: http://localhost:8000/health" -ForegroundColor Gray
Write-Host "   测试页面: 浏览器打开 client.html" -ForegroundColor Gray
Write-Host ""
Write-Host "⚙️ 配置文件: config.env" -ForegroundColor White
Write-Host "   请根据实际情况修改RTSP地址" -ForegroundColor Gray

if ($AutoStart) {
    Write-Host "`n🔄 自动启动服务..." -ForegroundColor Yellow
    Start-Process -FilePath "start.bat" -WorkingDirectory $PWD
}

Write-Host "`n=================================================" -ForegroundColor Cyan
