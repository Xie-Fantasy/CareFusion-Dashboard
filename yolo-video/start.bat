@echo off
echo ==================================================
echo YOLOv8实时人体检测系统 - Windows启动脚本
echo 硬件加速: RTX 4060 + i9-13900HX
echo ==================================================

:: 检查conda环境
echo 正在激活conda环境: yolo-detection
call conda activate yolo-detection

if %ERRORLEVEL% NEQ 0 (
    echo 错误: 找不到conda环境 'yolo-detection'
    echo 请先运行: conda env create -f environment.yml
    pause
    exit /b 1
)

:: 检查模型文件
if not exist "yolov8n.pt" (
    echo 错误: 找不到YOLOv8模型文件 yolov8n.pt
    echo 请确保模型文件在当前目录下
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "config.env" (
    echo 错误: 找不到配置文件 config.env
    echo 请检查配置文件是否存在
    pause
    exit /b 1
)

:: 设置环境变量
set PYTHONPATH=%cd%;%PYTHONPATH%

echo 正在启动YOLOv8人体检测服务...
echo 服务地址: http://localhost:8000
echo 流媒体地址: ws://localhost:8000/ws/stream
echo 测试客户端: client.html
echo.
echo 按 Ctrl+C 停止服务
echo ==================================================

:: 启动服务
python main.py

pause
