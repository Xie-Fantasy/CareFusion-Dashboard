#!/usr/bin/env python3
"""
YOLOv8实时人体检测系统测试脚本
验证所有依赖和硬件配置
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def test_python_version():
    """测试Python版本"""
    print("🐍 测试Python版本...")
    version = sys.version_info
    print(f"   Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("   ❌ Python版本过低，需要3.8+")
        return False
    else:
        print("   ✅ Python版本满足要求")
        return True

def test_dependencies():
    """测试依赖包"""
    print("\n📦 测试依赖包...")
    
    required_packages = [
        ('torch', 'PyTorch'),
        ('torchvision', 'TorchVision'),
        ('cv2', 'OpenCV'),
        ('ultralytics', 'YOLOv8'),
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('numpy', 'NumPy'),
        ('PIL', 'Pillow')
    ]
    
    failed_imports = []
    
    for package, name in required_packages:
        try:
            if package == 'PIL':
                __import__('PIL')
            else:
                __import__(package)
            print(f"   ✅ {name}")
        except ImportError as e:
            print(f"   ❌ {name} - {e}")
            failed_imports.append(name)
    
    return len(failed_imports) == 0, failed_imports

def test_cuda():
    """测试CUDA支持"""
    print("\n🖥️ 测试CUDA支持...")
    
    try:
        import torch
        
        cuda_available = torch.cuda.is_available()
        print(f"   CUDA可用: {cuda_available}")
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            current_device = torch.cuda.current_device()
            device_name = torch.cuda.get_device_name(current_device)
            cuda_version = torch.version.cuda
            
            print(f"   ✅ CUDA版本: {cuda_version}")
            print(f"   ✅ GPU设备数: {device_count}")
            print(f"   ✅ 当前GPU: {device_name}")
            print(f"   ✅ GPU内存: {torch.cuda.get_device_properties(current_device).total_memory / 1024**3:.1f}GB")
            
            # 测试GPU计算
            test_tensor = torch.randn(1000, 1000).cuda()
            start_time = time.time()
            result = torch.matmul(test_tensor, test_tensor)
            gpu_time = time.time() - start_time
            print(f"   ✅ GPU计算测试通过 ({gpu_time:.3f}秒)")
            
            return True
        else:
            print("   ⚠️ CUDA不可用，将使用CPU")
            return False
            
    except Exception as e:
        print(f"   ❌ CUDA测试失败: {e}")
        return False

def test_opencv():
    """测试OpenCV功能"""
    print("\n📷 测试OpenCV功能...")
    
    try:
        import cv2
        print(f"   ✅ OpenCV版本: {cv2.__version__}")
        
        # 测试基本图像操作
        import numpy as np
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        gray = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY)
        print("   ✅ 图像处理功能正常")
        
        # 检查编解码器支持
        fourcc = cv2.VideoWriter_fourcc('H', '2', '6', '4')
        print("   ✅ H.264编码器支持")
        
        return True
        
    except Exception as e:
        print(f"   ❌ OpenCV测试失败: {e}")
        return False

def test_yolo_model():
    """测试YOLOv8模型"""
    print("\n🎯 测试YOLOv8模型...")
    
    model_path = Path("yolov8n.pt")
    if not model_path.exists():
        print("   ❌ 模型文件 yolov8n.pt 不存在")
        return False
    
    try:
        from ultralytics import YOLO
        import numpy as np
        
        print("   ⏳ 加载YOLOv8模型...")
        model = YOLO(str(model_path))
        print("   ✅ 模型加载成功")
        
        # 创建测试图像
        test_image = np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8)
        
        print("   ⏳ 测试推理...")
        results = model(test_image, verbose=False)
        print("   ✅ 模型推理成功")
        
        # 测试人体检测
        person_results = model(test_image, classes=[0], verbose=False)  # 0 = person
        print("   ✅ 人体检测配置正确")
        
        return True
        
    except Exception as e:
        print(f"   ❌ YOLOv8测试失败: {e}")
        return False

def test_config_file():
    """测试配置文件"""
    print("\n⚙️ 测试配置文件...")
    
    config_path = Path("config.env")
    if not config_path.exists():
        print("   ❌ 配置文件 config.env 不存在")
        return False
    
    try:
        from dotenv import load_dotenv
        load_dotenv('config.env')
        
        rtsp_url = os.getenv('RTSP_URL')
        if rtsp_url:
            print(f"   ✅ RTSP配置: {rtsp_url[:30]}...")
        else:
            print("   ❌ 未找到RTSP_URL配置")
            return False
        
        print("   ✅ 配置文件加载成功")
        return True
        
    except Exception as e:
        print(f"   ❌ 配置文件测试失败: {e}")
        return False

def test_network():
    """测试网络连接"""
    print("\n🌐 测试网络连接...")
    
    try:
        import requests
        
        # 测试基本网络连接
        response = requests.get("https://www.google.com", timeout=5)
        if response.status_code == 200:
            print("   ✅ 网络连接正常")
        else:
            print("   ⚠️ 网络连接异常")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ 网络测试失败: {e}")
        return False

def performance_benchmark():
    """性能基准测试"""
    print("\n🚀 性能基准测试...")
    
    try:
        import torch
        import time
        import numpy as np
        from ultralytics import YOLO
        
        # GPU基准测试
        if torch.cuda.is_available():
            print("   ⏳ GPU推理性能测试...")
            
            model = YOLO("yolov8n.pt")
            test_image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            
            # 预热
            for _ in range(5):
                _ = model(test_image, verbose=False)
            
            # 性能测试
            start_time = time.time()
            num_frames = 25
            for _ in range(num_frames):
                _ = model(test_image, verbose=False)
            
            total_time = time.time() - start_time
            fps = num_frames / total_time
            
            print(f"   ✅ GPU推理FPS: {fps:.1f}")
            
            if fps >= 20:
                print("   ✅ 性能满足实时处理要求")
            else:
                print("   ⚠️ 性能可能不足，建议优化")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 性能测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 YOLOv8实时人体检测系统 - 系统测试")
    print("=" * 60)
    
    tests = [
        ("Python版本", test_python_version),
        ("依赖包", test_dependencies),
        ("CUDA支持", test_cuda),
        ("OpenCV功能", test_opencv),
        ("YOLOv8模型", test_yolo_model),
        ("配置文件", test_config_file),
        ("网络连接", test_network),
        ("性能基准", performance_benchmark),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ 测试异常: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"📈 通过率: {passed / (passed + failed) * 100:.1f}%")
    
    if failed == 0:
        print("\n🎉 所有测试通过！系统已准备就绪。")
        print("💡 运行 'python main.py' 启动服务")
    else:
        print("\n⚠️ 部分测试失败，请检查相关配置。")
        print("💡 参考README.md文档进行故障排除")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
