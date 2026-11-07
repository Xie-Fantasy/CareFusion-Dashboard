#!/usr/bin/env python3
"""
实时RTSP视频流YOLOv8人体检测系统
优化低延迟传输，支持720p@25fps
"""

import asyncio
import base64
import cv2
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Optional

import numpy as np
import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
from fastapi.staticfiles import StaticFiles
from training_api import router as training_router

# 加载环境变量
load_dotenv('config.env')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局配置（可通过config.env覆盖）
CONFIG = {
    'RTSP_URL': os.getenv('RTSP_URL', ''),
    'MODEL_PATH': os.getenv('MODEL_PATH', './yolov8n.pt'),

    # 流/推流分辨率（降低以提升FPS；原720p→默认540p）
    'STREAM_WIDTH': int(os.getenv('STREAM_WIDTH', '960')),
    'STREAM_HEIGHT': int(os.getenv('STREAM_HEIGHT', '540')),

    # 目标帧率（用于限速；自适应，不会阻塞低于目标FPS的处理）
    'TARGET_FPS': int(os.getenv('TARGET_FPS', '25')),

    # YOLO推理参数
    'DETECTION_CONFIDENCE': float(os.getenv('DETECTION_CONFIDENCE', '0.35')),
    'IMG_SIZE': int(os.getenv('IMG_SIZE', '640')),
    'MAX_DET': int(os.getenv('MAX_DET', '20')),
    'GPU_DEVICE': 0 if torch.cuda.is_available() else 'cpu',
    'USE_HALF': (os.getenv('USE_HALF', '1') == '1') and torch.cuda.is_available(),

    # 队列与编码
    'MAX_QUEUE_SIZE': int(os.getenv('MAX_QUEUE_SIZE', '3')),
    'JPEG_QUALITY': int(os.getenv('JPEG_QUALITY', '70')),

    # 性能优化选项
    'BITRATE': os.getenv('BITRATE', '2M'),
    'PRESET': os.getenv('PRESET', 'ultrafast'),
    'TUNE': os.getenv('TUNE', 'zerolatency'),
    
    # 关键点绘制优化
    'DRAW_KEYPOINTS': (os.getenv('DRAW_KEYPOINTS', '1') == '1'),
    'DRAW_SKELETON': (os.getenv('DRAW_SKELETON', '1') == '1'),
    'KEYPOINT_CONFIDENCE_THRESHOLD': float(os.getenv('KEYPOINT_CONFIDENCE_THRESHOLD', '0.7')),
}

class OptimizedRTSPCapture:
    """优化的RTSP捕获类，专为低延迟设计"""
    
    def __init__(self, rtsp_url: str):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.frame_queue = Queue(maxsize=CONFIG['MAX_QUEUE_SIZE'])
        self.running = False
        self.capture_thread = None
        
    def start(self):
        """启动RTSP捕获"""
        logger.info("正在连接视频流")
        
        # 优化的OpenCV参数
        self.cap = cv2.VideoCapture(self.rtsp_url)
        
        # 设置缓冲区大小为1，减少延迟
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # 设置帧率（某些设备忽略）
        self.cap.set(cv2.CAP_PROP_FPS, CONFIG['TARGET_FPS'])

        # 启用硬件解码（如果可用）/ 指定H264
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
        
        if not self.cap.isOpened():
            raise Exception("无法连接到视频流，请检查本地配置")
        
        # 尝试设置解码分辨率（很多RTSP源会忽略）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['STREAM_WIDTH'])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['STREAM_HEIGHT'])
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        self.capture_thread.start()
        
        logger.info("RTSP捕获启动成功")
    
    def _capture_frames(self):
        """捕获帧的后台线程"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("RTSP流中断，尝试重连...")
                time.sleep(1)
                continue
            
            # 如果队列满了，移除最旧的帧（减少延迟）
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            
            try:
                self.frame_queue.put_nowait(frame)
            except:
                pass  # 队列满时跳过
    
    def get_frame(self) -> Optional[np.ndarray]:
        """获取最新帧"""
        try:
            return self.frame_queue.get_nowait()
        except:
            return None
    
    def stop(self):
        """停止捕获"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.cap:
            self.cap.release()

class YOLODetector:
    """YOLO11人体检测与姿态识别器"""
    
    def __init__(self, model_path: str):
        self.device = CONFIG['GPU_DEVICE']
        logger.info(f"加载YOLO11姿态检测模型到设备: {self.device}")
        
        # 加载模型
        self.model = YOLO(model_path)

        # 将模型移到指定设备并优化
        if torch.cuda.is_available():
            self.model.to(self.device)
            if CONFIG['USE_HALF']:
                # 半精度推理（显著提升FPS）
                try:
                    self.model.model.half()
                    logger.info("启用半精度推理")
                except Exception as e:
                    logger.warning(f"半精度推理设置失败: {e}")
                    CONFIG['USE_HALF'] = False

        # cuDNN benchmark可在固定分辨率下提升卷积性能
        try:
            torch.backends.cudnn.benchmark = True
        except Exception:
            pass

        # 模型融合与预热
        try:
            self.model.fuse()
            logger.info("模型层融合完成")
        except Exception as e:
            logger.warning(f"模型融合失败: {e}")

        # 模型预热 - 执行多次预热以优化GPU性能
        try:
            logger.info("正在预热模型...")
            dummy = np.zeros((CONFIG['STREAM_HEIGHT'], CONFIG['STREAM_WIDTH'], 3), dtype=np.uint8)
            
            # 执行3次预热推理
            for i in range(3):
                _ = self.model.predict(
                    source=dummy,
                    imgsz=CONFIG['IMG_SIZE'],
                    conf=CONFIG['DETECTION_CONFIDENCE'],
                    max_det=CONFIG['MAX_DET'],
                    verbose=False,
                    device=self.device,
                    half=CONFIG['USE_HALF'],
                    agnostic_nms=False,
                    stream=False,
                )
                if i == 0:
                    logger.info("第一次预热完成")
            
            logger.info("模型预热完成")
        except Exception as e:
            logger.warning(f"模型预热失败: {e}")
        
        # 人体类别ID (COCO数据集中person的ID是0)
        self.person_class_id = 0
        
        logger.info("YOLO11姿态检测模型加载完成")
    
    def detect_persons(self, frame: np.ndarray) -> list:
        """检测帧中的人体并识别关键点"""
        # YOLO11姿态检测预测 - 优化参数
        with torch.no_grad():  # 禁用梯度计算以节省内存和计算
            results = self.model.predict(
                source=frame,
                imgsz=CONFIG['IMG_SIZE'],
                conf=CONFIG['DETECTION_CONFIDENCE'],
                max_det=CONFIG['MAX_DET'],
                verbose=False,
                device=self.device,
                half=CONFIG['USE_HALF'],
                agnostic_nms=False,
                stream=False,
                save=False,  # 不保存结果
                show=False,  # 不显示结果
                augment=False,  # 禁用测试时增强
            )
        
        persons = []
        if results and len(results) > 0:
            result = results[0]
            
            # 检查是否有检测框
            boxes = result.boxes
            keypoints = result.keypoints if hasattr(result, 'keypoints') else None
            
            if boxes is not None:
                for i, box in enumerate(boxes):
                    # 获取边界框坐标
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    person_data = {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': confidence,
                        'class': 'person',
                        'keypoints': []
                    }
                    
                    # 如果有关键点数据，提取关键点
                    if keypoints is not None and i < len(keypoints.data):
                        try:
                            kpts = keypoints.data[i].cpu().numpy()  # 获取第i个人的关键点
                            
                            # YOLO11关键点格式：shape可能是 (17, 3) 或 (51,)
                            if len(kpts.shape) == 2 and kpts.shape[1] == 3:
                                # 二维数组格式 (17, 3)
                                for kpt_idx in range(kpts.shape[0]):
                                    x, y, visibility = kpts[kpt_idx]
                                    if float(visibility) > CONFIG['KEYPOINT_CONFIDENCE_THRESHOLD']:  # 只保留可见的关键点
                                        person_data['keypoints'].append({
                                            'id': kpt_idx,
                                            'x': float(x),
                                            'y': float(y),
                                            'visibility': float(visibility)
                                        })
                            elif len(kpts.shape) == 1 and len(kpts) >= 51:
                                # 一维数组格式 (51,) - 17个关键点 * 3
                                for j in range(0, min(len(kpts), 51), 3):
                                    if j + 2 < len(kpts):
                                        x, y, visibility = float(kpts[j]), float(kpts[j+1]), float(kpts[j+2])
                                        if visibility > CONFIG['KEYPOINT_CONFIDENCE_THRESHOLD']:  # 只保留可见的关键点
                                            person_data['keypoints'].append({
                                                'id': j//3,
                                                'x': x,
                                                'y': y,
                                                'visibility': visibility
                                            })
                        except Exception as e:
                            # 如果关键点处理失败，记录错误但继续处理
                            logger.debug(f"关键点处理错误: {e}")
                            pass
                    
                    persons.append(person_data)
        
        return persons

class StreamingServer:
    """流媒体服务器"""
    
    def __init__(self):
        self.app = FastAPI(title="YOLO11人体检测与姿态识别流媒体服务")
        self.rtsp_capture = None
        self.detector = None
        self.connected_clients = set()
        # 增加工作线程，允许编码/检测更并行
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # CORS设置
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 设置路由
        self.setup_routes()
        self.app.include_router(training_router, prefix="/training", tags=["Model Training"])
    
    def setup_routes(self):
        """设置API路由"""
        
        @self.app.on_event("startup")
        async def startup_event():
            """启动时初始化"""
            try:
                # 初始化RTSP捕获
                self.rtsp_capture = OptimizedRTSPCapture(CONFIG['RTSP_URL'])
                self.rtsp_capture.start()
                
                # 初始化YOLO11姿态检测器
                self.detector = YOLODetector(CONFIG['MODEL_PATH'])
                
                logger.info("服务启动成功！")
                
            except Exception as e:
                logger.error(f"服务启动失败: {e}")
                raise
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            """关闭时清理资源"""
            if self.rtsp_capture:
                self.rtsp_capture.stop()
            self.executor.shutdown()
            logger.info("服务已关闭")
        
        @self.app.get("/")
        async def root():
            return {"message": "YOLO11人体检测与姿态识别流媒体服务运行中", "status": "running"}
        
        @self.app.get("/health")
        async def health():
            """健康检查"""
            return {
                "status": "healthy",
                "rtsp_connected": self.rtsp_capture is not None and self.rtsp_capture.running,
                "model_loaded": self.detector is not None,
                "active_connections": len(self.connected_clients)
            }
        
        @self.app.websocket("/ws/stream")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket流媒体端点"""
            await websocket.accept()
            self.connected_clients.add(websocket)
            logger.info(f"客户端连接，当前连接数: {len(self.connected_clients)}")
            
            try:
                await self.stream_to_client(websocket)
            except WebSocketDisconnect:
                logger.info("客户端断开连接")
            except Exception as e:
                logger.error(f"WebSocket错误: {e}")
            finally:
                self.connected_clients.discard(websocket)
                logger.info(f"客户端移除，当前连接数: {len(self.connected_clients)}")
    
    async def stream_to_client(self, websocket: WebSocket):
        """向客户端流式传输检测结果"""
        frame_count = 0
        last_fps_time = time.time()
        
        while True:
            try:
                # 获取最新帧（如无则短等待）
                frame = self.rtsp_capture.get_frame()
                if frame is None:
                    await asyncio.sleep(0.01)  # 10ms等待
                    continue
                
                t_start = time.time()

                # 为提升FPS，将帧缩放到推理/推流分辨率
                frame_resized = cv2.resize(
                    frame,
                    (CONFIG['STREAM_WIDTH'], CONFIG['STREAM_HEIGHT']),
                    interpolation=cv2.INTER_AREA,
                )

                # 异步检测人体
                persons = await asyncio.get_event_loop().run_in_executor(
                    self.executor, self.detector.detect_persons, frame_resized
                )
                
                # 绘制检测结果
                annotated_frame = self.draw_detections(frame_resized, persons)
                
                # 编码为JPEG（质量优化）
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), CONFIG['JPEG_QUALITY']]  # 降低质量以提升FPS
                success, buffer = cv2.imencode('.jpg', annotated_frame, encode_param)
                
                if not success:
                    continue
                
                # Base64编码
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # 准备发送数据
                data = {
                    'frame': jpg_as_text,
                    'detections': persons,
                    'timestamp': time.time(),
                    'frame_size': len(buffer)
                }
                
                # 发送到客户端
                await websocket.send_json(data)
                
                # FPS计算
                frame_count += 1
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    fps = frame_count / (current_time - last_fps_time)
                    logger.info(f"处理FPS: {fps:.1f}, 检测到人数: {len(persons)}")
                    frame_count = 0
                    last_fps_time = current_time
                
                # 自适应限速：仅当处理速度超过目标帧率时才sleep
                process_time = current_time - t_start
                frame_period = 1.0 / max(1, CONFIG['TARGET_FPS'])
                if process_time < frame_period:
                    await asyncio.sleep(frame_period - process_time)
                
            except Exception as e:
                logger.error(f"流处理错误: {e}")
                await asyncio.sleep(0.1)
    
    def draw_detections(self, frame: np.ndarray, persons: list) -> np.ndarray:
        """在帧上绘制检测结果和关键点"""
        annotated_frame = frame.copy()
        
        # COCO关键点连接关系（骨架）
        skeleton = [
            [16, 14], [14, 12], [17, 15], [15, 13], [12, 13],  # 头部
            [6, 12], [7, 13], [6, 7], [6, 8], [7, 9],          # 躯干和手臂
            [8, 10], [9, 11], [12, 14], [13, 15], [14, 16],    # 手臂和腿部
            [15, 17]
        ]
        
        # 关键点颜色（不同关键点用不同颜色）
        keypoint_colors = [
            (255, 0, 0),   # 鼻子 - 红色
            (255, 128, 0), # 左眼 - 橙色
            (255, 255, 0), # 右眼 - 黄色
            (128, 255, 0), # 左耳 - 黄绿色
            (0, 255, 0),   # 右耳 - 绿色
            (0, 255, 128), # 左肩 - 绿青色
            (0, 255, 255), # 右肩 - 青色
            (0, 128, 255), # 左肘 - 浅蓝色
            (0, 0, 255),   # 右肘 - 蓝色
            (128, 0, 255), # 左手腕 - 紫色
            (255, 0, 255), # 右手腕 - 品红色
            (255, 0, 128), # 左髋 - 粉红色
            (255, 128, 128), # 右髋 - 浅粉色
            (128, 255, 128), # 左膝 - 浅绿色
            (128, 128, 255), # 右膝 - 浅蓝色
            (255, 255, 128), # 左踝 - 浅黄色
            (128, 255, 255), # 右踝 - 浅青色
        ]
        
        for person in persons:
            x1, y1, x2, y2 = person['bbox']
            confidence = person['confidence']
            keypoints = person.get('keypoints', [])
            
            # 绘制边界框（绿色）
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # 绘制关键点
            keypoint_dict = {}
            if CONFIG['DRAW_KEYPOINTS']:
                for kpt in keypoints:
                    kpt_id = kpt['id']
                    x, y = int(kpt['x']), int(kpt['y'])
                    visibility = kpt['visibility']
                    
                    # 存储关键点位置用于绘制骨架
                    keypoint_dict[kpt_id] = (x, y)
                    
                    # 绘制关键点（根据可见性调整大小）
                    if kpt_id < len(keypoint_colors):
                        color = keypoint_colors[kpt_id]
                        radius = 3 if visibility > 0.8 else 2  # 减小半径提高性能
                        cv2.circle(annotated_frame, (x, y), radius, color, -1)
            else:
                # 即使不绘制关键点，也要存储位置用于骨架绘制
                for kpt in keypoints:
                    keypoint_dict[kpt['id']] = (int(kpt['x']), int(kpt['y']))
            
            # 绘制骨架连接线（根据配置决定是否绘制）
            if CONFIG['DRAW_SKELETON'] and keypoints:
                for connection in skeleton:
                    kpt1_id, kpt2_id = connection[0] - 1, connection[1] - 1  # COCO索引从1开始，我们的从0开始
                    if kpt1_id in keypoint_dict and kpt2_id in keypoint_dict:
                        pt1 = keypoint_dict[kpt1_id]
                        pt2 = keypoint_dict[kpt2_id]
                        # 简化绘制，只绘制一条线
                        cv2.line(annotated_frame, pt1, pt2, (0, 255, 0), 2)
            
            # 绘制标签
            keypoint_count = len(keypoints)
            label = f"Person {confidence:.2f} ({keypoint_count} kpts)"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # 背景矩形
            cv2.rectangle(annotated_frame, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), (0, 255, 0), -1)
            
            # 文本标签
            cv2.putText(annotated_frame, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return annotated_frame

def main():
    """主函数"""
    logger.info("启动YOLO11实时人体检测与姿态识别系统...")
    logger.info(f"系统配置: {json.dumps({**CONFIG, 'RTSP_URL': '***'}, indent=2)}")
    
    # 检查CUDA
    if torch.cuda.is_available():
        logger.info(f"检测到CUDA设备: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA版本: {torch.version.cuda}")
    else:
        logger.info("未检测到CUDA，将使用CPU")
    
    # 检查模型文件
    if not os.path.exists(CONFIG['MODEL_PATH']):
        logger.error(f"模型文件不存在: {CONFIG['MODEL_PATH']}")
        return
    
    # 启动服务
    server = StreamingServer()
    
    try:
        uvicorn.run(
            server.app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务运行错误: {e}")

if __name__ == "__main__":
    main()
