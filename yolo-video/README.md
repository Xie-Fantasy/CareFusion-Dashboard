# YOLO11实时人体检测与姿态识别系统

基于YOLO11n-pose的低延迟RTSP视频流人体检测与姿态识别系统，专为网络带宽受限环境优化。

## 系统特性

- 🎯 **精准检测**: YOLO11n-pose模型同时检测人体目标和关键点
- 🏃‍♂️ **姿态识别**: 实时检测17个COCO格式人体关键点，支持骨架绘制
- ⚡ **低延迟**: 优化的流媒体传输，适合60Mbps网络环境
- 🖥️ **GPU加速**: 支持RTX 4060等CUDA设备硬件加速
- 📺 **高清晰度**: 720p@25fps视频质量
- 🌐 **Web界面**: 基于WebSocket的实时流媒体展示
- 🔧 **易配置**: 通过环境变量灵活配置RTSP源

## 硬件要求

- **显卡**: NVIDIA RTX 4060 (或同等CUDA支持显卡)
- **处理器**: Intel i9-13900HX (或同等性能处理器)
- **内存**: 8GB+ RAM
- **网络**: 60Mbps带宽 (6MB/s下载速度)

## 系统架构

```
RTSP摄像头 → OpenCV捕获 → YOLOv8检测 → WebSocket流媒体 → Web客户端
                ↓              ↓              ↓
            硬件解码      GPU加速处理      低延迟编码
```

## 快速开始

### 1. 环境准备

#### 创建Conda环境
```bash
# 创建环境
conda env create -f environment.yml

# 激活环境
conda activate yolo-detection

# 或者使用pip安装
pip install -r requirements.txt
```

#### 验证CUDA支持
```python
import torch
print(f"CUDA可用: {torch.cuda.is_available()}")
print(f"CUDA版本: {torch.version.cuda}")
print(f"GPU设备: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else '无'}")
```

### 2. 配置RTSP源

编辑 `config.env` 文件，更新您的RTSP地址：

```bash
# 替换为您的实际RTSP地址
RTSP_URL=rtsp://USER:PASSWORD@CAMERA_HOST:554/STREAM
```

### 3. 启动服务

#### Windows
```cmd
start.bat
```

#### Linux/macOS
```bash
chmod +x start.sh
./start.sh
```

#### 手动启动
```bash
conda activate yolo-detection
python main.py
```

### 4. 访问Web界面

- 打开浏览器访问: http://localhost:8000
- 实时视频流地址: ws://localhost:8000/ws/stream
- 测试客户端: 打开 `client.html`

## 配置说明

### 主要参数 (config.env)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `RTSP_URL` | rtsp://USER:PASSWORD@CAMERA_HOST:554/STREAM | RTSP视频流地址 |
| `TARGET_WIDTH` | 1280 | 视频宽度(720p) |
| `TARGET_HEIGHT` | 720 | 视频高度(720p) |
| `TARGET_FPS` | 25 | 目标帧率 |
| `DETECTION_CONFIDENCE` | 0.4 | 检测置信度阈值 |
| `JPEG_QUALITY` | 85 | JPEG压缩质量 |

### 性能优化参数

| 参数 | 说明 |
|------|------|
| `MAX_QUEUE_SIZE=3` | 限制缓冲队列大小，减少延迟 |
| `PRESET=ultrafast` | x264编码最快预设 |
| `TUNE=zerolatency` | 零延迟调优 |
| `BITRATE=2M` | 2Mbps码率，适合720p@25fps |

## API接口

### RESTful API

- `GET /` - 服务状态
- `GET /health` - 健康检查

### WebSocket接口

- `WS /ws/stream` - 实时视频流

#### WebSocket消息格式
```json
{
  "frame": "base64_encoded_jpeg",
  "detections": [
    {
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.85,
      "class": "person"
    }
  ],
  "timestamp": 1704067200.123,
  "frame_size": 45678
}
```

## 性能监控

### 系统指标
- **FPS**: 实际处理帧率
- **延迟**: 端到端延迟时间
- **检测数量**: 每帧检测到的人数
- **数据大小**: 每帧数据传输大小

### 优化建议

#### 降低延迟
1. 减少 `MAX_QUEUE_SIZE` 值
2. 提高 `JPEG_QUALITY` 可能增加延迟
3. 确保CUDA驱动程序最新

#### 提高质量
1. 增加 `JPEG_QUALITY` 值
2. 调整 `DETECTION_CONFIDENCE` 阈值
3. 升级到更大的YOLOv8模型 (yolov8s.pt, yolov8m.pt)

## 故障排除

### 常见问题

#### 1. CUDA不可用
```
解决方案:
- 安装NVIDIA显卡驱动
- 安装CUDA Toolkit 12.1
- 重新安装PyTorch CUDA版本
```

#### 2. RTSP连接失败
```
解决方案:
- 检查网络连接
- 验证RTSP地址格式
- 确认摄像头认证信息
- 检查防火墙设置
```

#### 3. 内存不足
```
解决方案:
- 减少MAX_QUEUE_SIZE
- 降低JPEG_QUALITY
- 使用更小的YOLOv8模型
```

#### 4. 帧率过低
```
解决方案:
- 启用GPU加速
- 减少检测区域
- 降低视频分辨率
- 关闭不必要的应用程序
```

### 日志分析

系统日志提供详细的性能信息：
```
INFO - 处理FPS: 24.5, 检测到人数: 2
INFO - CUDA设备: NVIDIA GeForce RTX 4060
```

## 扩展开发

### 自定义检测类别
修改 `YOLODetector` 类中的 `person_class_id`：
```python
# COCO数据集类别ID
# 0: person, 1: bicycle, 2: car, 等等
self.person_class_id = [0, 2, 3, 5, 7]  # 多类别检测
```

### 添加后处理
在 `draw_detections` 方法中添加自定义标注：
```python
def draw_detections(self, frame, persons):
    # 自定义绘制逻辑
    # 添加轨迹跟踪
    # 添加告警区域
    # 添加计数统计
    return annotated_frame
```

### 集成其他模型
替换YOLOv8为其他检测模型：
```python
# 示例：集成其他ONNX模型
import onnxruntime as ort

class CustomDetector:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(model_path)
```

## 许可证

项目整体许可证尚未指定；第三方依赖和权重遵循其各自的许可证。

## 技术支持

如需技术支持，请提供以下信息：
- 操作系统版本
- Python和包版本
- CUDA版本
- 错误日志
- 网络配置信息

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 支持YOLOv8人体检测
- 低延迟WebSocket流媒体
- GPU硬件加速
- 720p@25fps视频处理
