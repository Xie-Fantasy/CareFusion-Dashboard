@echo off
echo 正在激活conda环境并运行性能诊断...

call conda activate yolo-detection
if %ERRORLEVEL% neq 0 (
    echo 错误：无法激活conda环境 'yolo-detection'
    echo 请先创建环境：conda env create -f environment.yml
    pause
    exit /b 1
)

echo 环境已激活，开始性能诊断...
python test_performance.py

echo.
echo 诊断完成，按任意键退出...
pause
