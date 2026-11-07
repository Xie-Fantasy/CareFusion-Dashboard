#!/usr/bin/env python3
"""
YOLO11性能诊断工具
测试模型加载、GPU加速和推理性能
"""

import time
import numpy as np
import torch
import cv2
from ultralytics import YOLO
from dotenv import load_dotenv
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载配置
load_dotenv('config.env')

def test_environment():
    """测试环境配置"""
    logger.info("=== 环境测试 ===")
    
    # Python版本
    import sys
    logger.info(f"Python版本: {sys.version}")
    
    # PyTorch版本和CUDA支持
    logger.info(f"PyTorch版本: {torch.__version__}")
    logger.info(f"CUDA可用: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        logger.info(f"CUDA版本: {torch.version.cuda}")
        logger.info(f"GPU设备数量: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            logger.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")
            # GPU内存信息
            memory_total = torch.cuda.get_device_properties(i).total_memory / 1024**3
            logger.info(f"GPU {i} 总内存: {memory_total:.1f}GB")
    
    # Ultralytics版本
    try:
        import ultralytics
        logger.info(f"Ultralytics版本: {ultralytics.__version__}")
    except:
        logger.error("Ultralytics未安装或版本有问题")
        return False
    
    return True

def test_model_loading():
    """测试模型加载"""
    logger.info("\n=== 模型加载测试 ===")
    
    model_path = os.getenv('MODEL_PATH', './yolo11n-pose.pt')
    logger.info(f"模型路径: {model_path}")
    
    if not os.path.exists(model_path):
        logger.error(f"模型文件不存在: {model_path}")
        return None
    
    try:
        start_time = time.time()
        model = YOLO(model_path)
        load_time = time.time() - start_time
        logger.info(f"模型加载成功，耗时: {load_time:.2f}秒")
        
        # 检查模型类型
        logger.info(f"模型任务类型: {model.task}")
        if hasattr(model.model, 'names'):
            logger.info(f"检测类别数: {len(model.model.names)}")
        
        return model
        
    except Exception as e:
        logger.error(f"模型加载失败: {e}")
        return None

def test_gpu_performance(model):
    """测试GPU性能"""
    logger.info("\n=== GPU性能测试 ===")
    
    if not torch.cuda.is_available():
        logger.warning("CUDA不可用，将使用CPU测试")
        device = 'cpu'
    else:
        device = 0
        # 设置模型到GPU
        model.to(device)
        
        # 尝试半精度
        try:
            model.model.half()
            logger.info("启用半精度推理")
        except Exception as e:
            logger.warning(f"半精度设置失败: {e}")
    
    # 创建测试图像
    test_sizes = [(640, 480), (960, 540), (1280, 720)]
    
    for width, height in test_sizes:
        logger.info(f"\n测试分辨率: {width}x{height}")
        
        # 创建随机图像
        dummy_img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        
        # 预热
        for i in range(3):
            _ = model.predict(
                source=dummy_img,
                imgsz=640,
                conf=0.5,
                verbose=False,
                device=device,
                half=torch.cuda.is_available(),
                save=False,
                show=False
            )
        
        # 性能测试
        num_tests = 10
        start_time = time.time()
        
        for i in range(num_tests):
            results = model.predict(
                source=dummy_img,
                imgsz=640,
                conf=0.5,
                verbose=False,
                device=device,
                half=torch.cuda.is_available(),
                save=False,
                show=False
            )
        
        total_time = time.time() - start_time
        avg_time = total_time / num_tests
        fps = 1.0 / avg_time
        
        logger.info(f"平均推理时间: {avg_time:.3f}秒")
        logger.info(f"理论最大FPS: {fps:.1f}")
        
        # 检查结果
        if results and len(results) > 0:
            result = results[0]
            if hasattr(result, 'boxes') and result.boxes is not None:
                logger.info(f"检测到目标数: {len(result.boxes)}")
            if hasattr(result, 'keypoints') and result.keypoints is not None:
                logger.info(f"关键点数据形状: {result.keypoints.data.shape}")

def test_memory_usage():
    """测试内存使用"""
    logger.info("\n=== 内存使用测试 ===")
    
    if torch.cuda.is_available():
        # GPU内存
        for i in range(torch.cuda.device_count()):
            memory_allocated = torch.cuda.memory_allocated(i) / 1024**3
            memory_reserved = torch.cuda.memory_reserved(i) / 1024**3
            logger.info(f"GPU {i} 已分配内存: {memory_allocated:.2f}GB")
            logger.info(f"GPU {i} 已保留内存: {memory_reserved:.2f}GB")
    
    # CPU内存
    import psutil
    memory_info = psutil.virtual_memory()
    logger.info(f"CPU内存使用率: {memory_info.percent}%")
    logger.info(f"CPU可用内存: {memory_info.available / 1024**3:.1f}GB")

def main():
    """主测试函数"""
    logger.info("开始YOLO11性能诊断...")
    
    # 环境测试
    if not test_environment():
        return
    
    # 模型加载测试
    model = test_model_loading()
    if model is None:
        return
    
    # GPU性能测试
    test_gpu_performance(model)
    
    # 内存使用测试
    test_memory_usage()
    
    logger.info("\n=== 诊断完成 ===")
    logger.info("如果发现问题，请检查：")
    logger.info("1. CUDA驱动是否正确安装")
    logger.info("2. PyTorch CUDA版本是否匹配")
    logger.info("3. 模型文件是否损坏")
    logger.info("4. 系统资源是否充足")

if __name__ == "__main__":
    main()
