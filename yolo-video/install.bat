@echo off
echo ==================================================
echo YOLOv8实时人体检测系统 - 安装脚本
echo 正在安装依赖和配置环境...
echo ==================================================

:: 检查conda是否安装
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 找不到conda命令
    echo 请先安装Anaconda或Miniconda
    echo 下载地址: https://www.anaconda.com/download
    pause
    exit /b 1
)

:: 检查是否已存在环境
conda env list | findstr "yolo-detection" >nul
if %ERRORLEVEL% EQU 0 (
    echo 发现已存在的conda环境 'yolo-detection'
    set /p choice="是否要重新创建环境? (y/n): "
    if /i "%choice%"=="y" (
        echo 正在删除旧环境...
        call conda env remove -n yolo-detection -y
    ) else (
        echo 跳过环境创建，直接安装依赖...
        goto :install_deps
    )
)

echo 正在创建conda环境: yolo-detection
call conda env create -f environment.yml

if %ERRORLEVEL% NEQ 0 (
    echo 错误: conda环境创建失败
    echo 尝试使用pip安装...
    goto :pip_install
)

echo conda环境创建成功！
goto :post_install

:pip_install
echo 使用pip安装依赖...
pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo 错误: pip安装失败
    pause
    exit /b 1
)

:install_deps
echo 激活环境并验证安装...
call conda activate yolo-detection

:post_install
echo.
echo ==================================================
echo 安装完成！
echo ==================================================
echo.
echo 下一步:
echo 1. 确保 yolov8n.pt 模型文件在当前目录
echo 2. 编辑 config.env 文件，设置正确的RTSP地址
echo 3. 运行 start.bat 启动服务
echo.
echo 验证安装:
python -c "import torch; print(f'CUDA可用: {torch.cuda.is_available()}')"
python -c "import cv2; print(f'OpenCV版本: {cv2.__version__}')"
python -c "from ultralytics import YOLO; print('YOLOv8导入成功')"
echo.
echo 安装完成！按任意键退出...
pause
