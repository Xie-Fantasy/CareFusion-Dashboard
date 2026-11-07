#!/usr/bin/env python3
"""
简化的环境验证脚本
"""

print("=" * 50)
print("环境验证测试")
print("=" * 50)

try:
    # 1. 基础检查
    import sys
    print(f"Python版本: {sys.version.split()[0]}")
    
    # 2. PyTorch检查
    try:
        import torch
        print(f"PyTorch版本: {torch.__version__}")
        print(f"CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"GPU名称: {torch.cuda.get_device_name(0)}")
            print(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
    except ImportError as e:
        print(f"PyTorch导入失败: {e}")
    
    # 3. OpenCV检查
    try:
        import cv2
        print(f"OpenCV版本: {cv2.__version__}")
    except ImportError as e:
        print(f"OpenCV导入失败: {e}")
    
    # 4. YOLOv8检查
    try:
        from ultralytics import YOLO
        print("YOLOv8导入成功")
        
        # 检查模型文件
        import os
        if os.path.exists('yolov8n.pt'):
            print("模型文件存在")
            # 尝试加载模型
            model = YOLO('yolov8n.pt')
            print("模型加载成功")
        else:
            print("警告: 模型文件yolov8n.pt不存在")
            
    except ImportError as e:
        print(f"YOLOv8导入失败: {e}")
    except Exception as e:
        print(f"模型测试失败: {e}")
    
    # 5. FastAPI检查
    try:
        import fastapi
        import uvicorn
        print(f"FastAPI版本: {fastapi.__version__}")
    except ImportError as e:
        print(f"FastAPI导入失败: {e}")
    
    print("=" * 50)
    print("验证完成")
    print("=" * 50)

except Exception as e:
    print(f"验证过程出错: {e}")

input("按任意键退出...")
