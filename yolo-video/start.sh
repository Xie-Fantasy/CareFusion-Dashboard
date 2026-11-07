#!/bin/bash

echo "=================================================="
echo "YOLOv8实时人体检测系统 - Linux/macOS启动脚本"
echo "硬件加速: RTX 4060 + i9-13900HX"
echo "=================================================="

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "错误: 找不到conda命令"
    echo "请先安装Anaconda或Miniconda"
    exit 1
fi

# 激活conda环境
echo "正在激活conda环境: yolo-detection"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate yolo-detection

if [ $? -ne 0 ]; then
    echo "错误: 找不到conda环境 'yolo-detection'"
    echo "请先运行: conda env create -f environment.yml"
    exit 1
fi

# 检查模型文件
if [ ! -f "yolov8n.pt" ]; then
    echo "错误: 找不到YOLOv8模型文件 yolov8n.pt"
    echo "请确保模型文件在当前目录下"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.env" ]; then
    echo "错误: 找不到配置文件 config.env"
    echo "请检查配置文件是否存在"
    exit 1
fi

# 设置环境变量
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "正在启动YOLOv8人体检测服务..."
echo "服务地址: http://localhost:8000"
echo "流媒体地址: ws://localhost:8000/ws/stream"
echo "测试客户端: client.html"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=================================================="

# 启动服务
python main.py
