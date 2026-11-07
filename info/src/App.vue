<script setup>
import { ref, onMounted, onUnmounted, nextTick } from "vue";
import * as echarts from "echarts";
import EZUIKit from "ezuikit-js";
import ezvizConfig from "../ezviz-config.json";
import refreshSvg from "./assets/svg/刷新.svg";

// 硬件设备状态数据
const isAlarmActive = ref(false);
const isMildFallActive = ref(false);
const isBodyMovementActive = ref(false);
const isNetworkDisconnected = ref(false);
const isNoDataMode = ref(true); // 新增：无数据模式，默认为true
const fallDetectionRadar = ref({
  deviceType: "跌倒检测雷达",
  location: "客厅",
  status: "正常",
  standingState: "站立", // 站立/跌倒
  motionState: "静止", // 静止/移动
  distance: "1.2m",
  position: { x: 0.5, y: 0.3 },
});


const breathHeartRadar = ref({
  deviceType: "呼吸心率监测雷达",
  location: "客厅",
  status: "正常",
  heartRate: 78,
  breathRate: 16,
  heartRateHistory: [],
  breathHistory: [],
});

const antifalVest = ref({
  deviceType: "防摔马甲",
  location: "客厅",
  status: "正常",
  airbagStatus: "未充气", // 未充气/已充气
  acceleration: { x: 0.1, y: 0.2, z: 9.8 },
  gyroscope: { pitch: 0, roll: 0, yaw: 0 },
});

const surveillanceCamera = ref({
  deviceType: "监控摄像头",
  location: "客厅",
  status: "在线",
  isRecording: true,
  streamUrl: "",
});

// 设备选择下拉框的显示状态
const dropdownVisible = ref({
  fallDetection: false,
  antifal: false,
  camera: false,
  breathHeart: false,
});

// 可选的房间位置
const roomOptions = ["卧室", "客厅", "厨房", "书房", "阳台"];

// 切换下拉框显示状态
const toggleDropdown = deviceKey => {
  dropdownVisible.value[deviceKey] = !dropdownVisible.value[deviceKey];
  // 关闭其他下拉框
  Object.keys(dropdownVisible.value).forEach(key => {
    if (key !== deviceKey) {
      dropdownVisible.value[key] = false;
    }
  });
};

// 选择房间
const selectRoom = (deviceKey, room) => {
  if (deviceKey === "fallDetection") {
    fallDetectionRadar.value.location = room;
  } else if (deviceKey === "antifal") {
    antifalVest.value.location = room;
  } else if (deviceKey === "camera") {
    surveillanceCamera.value.location = room;
  } else if (deviceKey === "breathHeart") {
    breathHeartRadar.value.location = room;
  }
  dropdownVisible.value[deviceKey] = false;
};

// echarts实例
let heartRateChart = null;
let breathingChart = null;

// 已彻底移除雷达圈功能函数

// 萤石云播放器相关
const videoPlayer = ref(null);
let ezPlayer = null;
const isVideoLoading = ref(false);
const isVideoPlaying = ref(false);
const videoError = ref("");
let resizeHandlerRegistered = false;

// YOLOv11-pose视频流相关
const yoloVideoPlayer = ref(null);
const yoloWebSocket = ref(null);
const isYoloConnected = ref(false);
const isYoloLoading = ref(false);
const yoloError = ref("");
const yoloFrameData = ref("");
const yoloDetections = ref([]);
const yoloStats = ref({
  isMoving: false,
  latency: 0,
  detectedPersons: 0
});

// 视频源切换
const currentVideoSource = ref("yolo"); // "yolo" 或 "ezviz"

  // 事件日志
  const eventLogs = ref([]);
  const addEventLog = (message, type = 'info') => {
    const t = new Date();
    const ts = `${t.toLocaleDateString()} ${t.toLocaleTimeString()}`;
    eventLogs.value.unshift({ ts, message, type });
    if (eventLogs.value.length > 100) eventLogs.value.pop();
  };






































  // PTZ 云台控制（键盘控制）
  let ptzActiveDirection = null; // 0上 1下 2左 3右
  const getEzBase = () => {
    // 你的配置中 apiUrl 是 https://open.ys7.com/api/lapp/v2，但 PTZ 在 v1 路径
    // 统一降级为 /api/lapp 以避免 404
    const raw = ezvizSettings.apiUrl || 'https://open.ys7.com/api/lapp';
    const normalized = raw.replace(/\/$/, '');
    return normalized.replace(/\/v\d+$/, '');
  };
  const postForm = async (path, payload) => {
    const url = `${getEzBase()}${path.startsWith('/') ? path : '/' + path}`;
    const params = new URLSearchParams();
    Object.entries(payload).forEach(([k, v]) => params.set(k, String(v)));
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    });
    return res.ok ? res.json().catch(() => ({})) : Promise.reject(new Error('PTZ请求失败'));
  };
  const ptzStart = async (direction) => {
    try {
      await postForm('/device/ptz/start', {
        accessToken: ezvizSettings.accessToken,
        deviceSerial: ezvizSettings.deviceSerial,
        channelNo: ezvizSettings.cameraNo || 1,
        direction,
        speed: 1,
      });
      addEventLog(`云台开始移动 direction=${direction}`);
    } catch (e) {
      addEventLog('云台开始移动失败');
    }
  };
  const ptzStop = async () => {
    try {
      await postForm('/device/ptz/stop', {
        accessToken: ezvizSettings.accessToken,
        deviceSerial: ezvizSettings.deviceSerial,
        channelNo: ezvizSettings.cameraNo || 1,
      });
      addEventLog('云台停止移动');
    } catch (e) {
      addEventLog('云台停止移动失败');
    }
  };

// 萤石云配置
const ezvizSettings = ref({
  ...ezvizConfig.ezviz
});

// 设置弹窗相关状态
const showEzvizSettings = ref(false);
const tempAccessToken = ref('');
const tempAccessUrl = ref('');
const isTestingConnection = ref(false);
const testResult = ref(null);

// 模拟实时数据更新（根据是否报警生成不同数据）
let heartRateCurrent = 78;
let breathRateCurrent = 16;
const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

const applyModeSnapshot = () => {
  if (isNoDataMode.value) {
    // 无数据模式：所有设备显示无数据状态
    fallDetectionRadar.value.standingState = "--";
    fallDetectionRadar.value.motionState = "--";
    breathHeartRadar.value.status = "离线";
    antifalVest.value.airbagStatus = "--";
    antifalVest.value.status = "离线";
    surveillanceCamera.value.status = "离线";
  } else if (isAlarmActive.value) {
    // 严重跌倒模式：第一个圈显示静止/体动，第二个圈显示跌倒
    fallDetectionRadar.value.motionState = isBodyMovementActive.value ? "体动" : "静止"; // 第一个圈：静止/体动
    fallDetectionRadar.value.standingState = "跌倒"; // 第二个圈：跌倒
    breathHeartRadar.value.status = "正常";
    antifalVest.value.airbagStatus = "已充气";
    antifalVest.value.status = "正常";
    surveillanceCamera.value.status = "在线";
  } else if (isMildFallActive.value) {
    // 轻度跌倒模式：第一个圈显示静止/体动，第二个圈显示跌倒
    fallDetectionRadar.value.motionState = isBodyMovementActive.value ? "体动" : "静止"; // 第一个圈：静止/体动
    fallDetectionRadar.value.standingState = "跌倒"; // 第二个圈：跌倒
    breathHeartRadar.value.status = "正常";
    antifalVest.value.airbagStatus = "未充气"; // 轻度跌倒时马甲不充气
    antifalVest.value.status = "正常";
    surveillanceCamera.value.status = "在线";
  } else {
    // 正常模式即时状态
    fallDetectionRadar.value.standingState = "站立";
    fallDetectionRadar.value.motionState = isBodyMovementActive.value ? "体动" : "静止";
    breathHeartRadar.value.status = "正常";
    antifalVest.value.airbagStatus = "未充气";
    antifalVest.value.status = "正常";
    surveillanceCamera.value.status = "在线";
  }
};

const updateRealTimeData = () => {
  // 无数据模式下不更新数据
  if (isNoDataMode.value) {
    return;
  }
  
  const currentTime = new Date().toLocaleTimeString();

  // 根据模式调整目标范围与波动
  if (isAlarmActive.value) {
    // 严重跌倒：心率快速且不稳定 100-125（更克制）
    heartRateCurrent += (Math.random() - 0.5) * 8;
    heartRateCurrent += 1.5;
    heartRateCurrent = clamp(heartRateCurrent, 100, 125);

    // 呼吸急促 24-34
    breathRateCurrent += (Math.random() - 0.5) * 5;
    breathRateCurrent = clamp(breathRateCurrent, 24, 34);
  } else if (isMildFallActive.value) {
    // 轻度跌倒：心率稍微增高 85-100
    heartRateCurrent += (Math.random() - 0.5) * 6;
    heartRateCurrent += 1.0;
    heartRateCurrent = clamp(heartRateCurrent, 85, 100);

    // 呼吸稍微急促 20-26
    breathRateCurrent += (Math.random() - 0.5) * 3;
    breathRateCurrent = clamp(breathRateCurrent, 20, 26);

    // 传感器适度波动（但不改变静止含义）
    antifalVest.value.acceleration = {
      x: (Math.random() - 0.5) * 1.2,
      y: (Math.random() - 0.5) * 1.2,
      z: 9.8 + (Math.random() - 0.5) * 0.6,
    };
    antifalVest.value.gyroscope = {
      pitch: (Math.random() - 0.5) * 8,
      roll: (Math.random() - 0.5) * 8,
      yaw: (Math.random() - 0.5) * 8,
    };
  } else {
    // 正常状态：心率 65-85，平滑波动
    const targetHr = 75 + Math.sin(Date.now() / 4000) * 5;
    heartRateCurrent +=
      (targetHr - heartRateCurrent) * 0.15 + (Math.random() - 0.5) * 1.5;
    heartRateCurrent = clamp(heartRateCurrent, 65, 85);

    // 呼吸 14-20，较为稳定
    const targetBr = 16 + Math.sin(Date.now() / 5000) * 2;
    breathRateCurrent +=
      (targetBr - breathRateCurrent) * 0.2 + (Math.random() - 0.5) * 0.8;
    breathRateCurrent = clamp(breathRateCurrent, 14, 20);

    // 传感器接近静止
    antifalVest.value.acceleration = {
      x: (Math.random() - 0.5) * 0.4,
      y: (Math.random() - 0.5) * 0.4,
      z: 9.8 + (Math.random() - 0.5) * 0.2,
    };
    antifalVest.value.gyroscope = {
      pitch: (Math.random() - 0.5) * 3,
      roll: (Math.random() - 0.5) * 3,
      yaw: (Math.random() - 0.5) * 3,
    };
  }

  breathHeartRadar.value.heartRate = Math.round(heartRateCurrent);
  breathHeartRadar.value.breathRate = Math.round(breathRateCurrent);
  
  // 保存历史数据（最多保留20条）
  breathHeartRadar.value.heartRateHistory.push({
    time: currentTime,
    value: Math.round(heartRateCurrent),
  });
  breathHeartRadar.value.breathHistory.push({
    time: currentTime,
    value: Math.round(breathRateCurrent),
  });
  if (breathHeartRadar.value.heartRateHistory.length > 20) {
    breathHeartRadar.value.heartRateHistory.shift();
    breathHeartRadar.value.breathHistory.shift();
  }
  
  // 更新YOLO统计数据（确保体动模式正常工作）
  if (isBodyMovementActive.value) {
    yoloStats.value.isMoving = "体动";
  } else {
    // 非体动模式时保持当前状态，不进行随机更新
    // 状态切换只通过V键控制
  }
  
  // 更新图表
  updateCharts();
};

// 延迟应用数据变化的函数
const applyDataChangeWithDelay = (callback) => {
  setTimeout(() => {
    callback();
    applyModeSnapshot();
  }, 2000); // 延迟2秒
};

// 键盘切换模式：按下"N"进入正常模式，"A"和"P"切换数据模式
  const handleKeydown = e => {
    // 按N进入正常模式并连接监控（延迟2秒）
    if (e.key === "n" || e.key === "N") {
      if (isNoDataMode.value) {
        applyDataChangeWithDelay(() => {
          isNoDataMode.value = false;
          // 连接监控视频
          if (currentVideoSource.value === 'yolo') {
            connectYoloWebSocket();
          } else {
            if (!isVideoPlaying.value) {
              initEzPlayer();
            }
          }
        });
      }
      return;
    }
    
    // 如果在无数据模式下，除了N键外其他键不响应
    if (isNoDataMode.value) {
      return;
    }
    
    // 严重跌倒模式切换（红色预警）
    if (e.key === "d" || e.key === "D") {
      applyDataChangeWithDelay(() => {
        isAlarmActive.value = !isAlarmActive.value;
        isMildFallActive.value = false; // 严重跌倒时关闭轻度跌倒
      });
      return;
    }
    
    // 轻度跌倒模式切换（黄色预警）
    if (e.key === "a" || e.key === "A") {
      applyDataChangeWithDelay(() => {
        isMildFallActive.value = !isMildFallActive.value;
        isAlarmActive.value = false; // 轻度跌倒时关闭严重跌倒
      });
      return;
    }
    
    // 体动模式切换
    if (e.key === "v" || e.key === "V") {
      isBodyMovementActive.value = !isBodyMovementActive.value;
      // 立即更新相关状态
      if (isBodyMovementActive.value) {
        yoloStats.value.isMoving = "体动";
        fallDetectionRadar.value.motionState = "体动";
      } else {
        yoloStats.value.isMoving = false; // 明确设置为静止状态
        fallDetectionRadar.value.motionState = "静止"; // motionState只显示静止或体动，不显示跌倒
      }
      return;
    }

    // 模拟网络断开（改为其他键，比如M键）
    if (e.key === "m" || e.key === "M") {
      isNetworkDisconnected.value = !isNetworkDisconnected.value;
      if (isNetworkDisconnected.value) {
        // 断开WebSocket连接
        disconnectYoloWebSocket();
        // 清空图表数据
        if (heartRateChart) {
          heartRateChart.setOption({
            series: [{ data: [] }]
          });
        }
        if (breathingChart) {
          breathingChart.setOption({
            series: [{ data: [] }]
          });
        }
      } else {
        // 重新连接WebSocket
        if (currentVideoSource.value === 'yolo') {
          connectYoloWebSocket();
        }
        // 重新初始化图表
        initCharts();
      }
      return;
    }

    // 云台方向（数字小键盘）
    let direction = null; // 0上 1下 2左 3右
    if (e.code === 'Numpad8' || e.key === '8') direction = 0;
    else if (e.code === 'Numpad2' || e.key === '2') direction = 1;
    else if (e.code === 'Numpad4' || e.key === '4') direction = 2;
    else if (e.code === 'Numpad6' || e.key === '6') direction = 3;

    if (direction !== null) {
      if (ptzActiveDirection === null) {
        ptzActiveDirection = direction;
        ptzStart(direction);
      }
    }
  };

  const handleKeyup = e => {
    if (ptzActiveDirection !== null) {
      const releaseKeys = ['Numpad8','Numpad2','Numpad4','Numpad6','8','2','4','6'];
      if (releaseKeys.includes(e.code) || releaseKeys.includes(e.key)) {
        ptzActiveDirection = null;
        ptzStop();
      }
    }
  };

// 初始化图表
const initCharts = () => {
  const heartRateEl = document.getElementById("heartRateChart");
  const breathingEl = document.getElementById("breathingChart");
  
  if (heartRateEl && breathingEl) {
    heartRateChart = echarts.init(heartRateEl);
    breathingChart = echarts.init(breathingEl);
    
    const commonOption = {
      grid: {
        top: 20,
        left: 40,
        right: 20,
        bottom: 20,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: [],
        axisLabel: {
          color: "#ffffff",
          fontSize: 10,
        },
        axisLine: {
          lineStyle: { color: "#ffffff" },
        },
        splitLine: {
          show: false,
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#ffffff",
          fontSize: 10,
          // 确保初始化时也显示整数
          formatter: function(value) {
            return Math.round(value);
          }
        },
        axisLine: {
          lineStyle: { color: "#ffffff" },
        },
        splitLine: {
          lineStyle: { color: "rgba(64, 254, 255, 0.2)" },
        },
        // 设置显示5个刻度点
        splitNumber: 4, // 显示5个刻度（包括上下边界）需要设置为4
      },
      series: [
        {
          type: "line",
        smooth: true,
        data: [],
        lineStyle: {
            color: "#FF8C56",
            width: 1,
        },
        itemStyle: {
            color: "#02FCFD",
            borderWidth: 0,
        },
        symbol: 'circle',
        symbolSize: 6,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(251,177,117,0.69)" },
              { offset: 1, color: "rgba(255,162,118,0.00)" },
            ]),
          },
        },
      ],
    };
    
    heartRateChart.setOption({
      ...commonOption,
      yAxis: {
        ...commonOption.yAxis,
        // 让y轴自动调整范围，保持一定的缓冲空间
        scale: true,
        minInterval: 10,
        boundaryGap: [0.1, 0.1], // 上下各留10%的空间
      },
    });
    
    breathingChart.setOption({
      ...commonOption,
      yAxis: {
        ...commonOption.yAxis,
        // 让y轴自动调整范围，保持一定的缓冲空间
        scale: true,
        minInterval: 2,
        boundaryGap: [0.1, 0.1], // 上下各留10%的空间
      },

    });
      }
};

// 更新图表数据
const updateCharts = () => {
  if (heartRateChart && breathingChart) {
    const heartRateTimes = breathHeartRadar.value.heartRateHistory.map(
      item => item.time
    );
    const heartRateValues = breathHeartRadar.value.heartRateHistory.map(
      item => item.value
    );

    const breathingTimes = breathHeartRadar.value.breathHistory.map(
      item => item.time
    );
    const breathingValues = breathHeartRadar.value.breathHistory.map(
      item => item.value
    );
    
    // 计算心率数据的范围，确保最小跨度和适当缓冲
    const heartRateMin = heartRateValues.length > 0 ? Math.min(...heartRateValues) : 60;
    const heartRateMax = heartRateValues.length > 0 ? Math.max(...heartRateValues) : 100;
    const heartRateRange = heartRateMax - heartRateMin;
    
    // 设置最小跨度为10，确保数据稳定时也有足够的细节
    const minHeartRateSpan = 10;
    let adjustedHeartRateMin, adjustedHeartRateMax;
    
    if (heartRateRange < minHeartRateSpan) {
      // 当数据范围小于最小跨度时，以中值为中心扩展
      const heartRateCenter = (heartRateMin + heartRateMax) / 2;
      adjustedHeartRateMin = Math.max(30, heartRateCenter - minHeartRateSpan / 2);
      adjustedHeartRateMax = adjustedHeartRateMin + minHeartRateSpan;
    } else {
      // 正常情况下添加10%缓冲
      const heartRateBuffer = heartRateRange * 0.1;
      adjustedHeartRateMin = Math.max(30, heartRateMin - heartRateBuffer);
      adjustedHeartRateMax = heartRateMax + heartRateBuffer;
    }
    
    // 计算呼吸数据的范围，确保最小跨度和适当缓冲
    const breathingMin = breathingValues.length > 0 ? Math.min(...breathingValues) : 12;
    const breathingMax = breathingValues.length > 0 ? Math.max(...breathingValues) : 20;
    const breathingRange = breathingMax - breathingMin;
    
    // 设置最小跨度为6，适合呼吸频率的细节显示
    const minBreathingSpan = 6;
    let adjustedBreathingMin, adjustedBreathingMax;
    
    if (breathingRange < minBreathingSpan) {
      // 当数据范围小于最小跨度时，以中值为中心扩展
      const breathingCenter = (breathingMin + breathingMax) / 2;
      adjustedBreathingMin = Math.max(5, breathingCenter - minBreathingSpan / 2);
      adjustedBreathingMax = adjustedBreathingMin + minBreathingSpan;
    } else {
      // 正常情况下添加10%缓冲
      const breathingBuffer = breathingRange * 0.1;
      adjustedBreathingMin = Math.max(5, breathingMin - breathingBuffer);
      adjustedBreathingMax = breathingMax + breathingBuffer;
    }
    
    heartRateChart.setOption({
      xAxis: { data: heartRateTimes },
      yAxis: {
        min: Math.floor(adjustedHeartRateMin),
        max: Math.ceil(adjustedHeartRateMax),
        splitNumber: 4, // 显示5个刻度（包括上下边界）
        interval: (Math.ceil(adjustedHeartRateMax) - Math.floor(adjustedHeartRateMin)) / 4,
        axisLabel: {
          color: "#8FFFF8",
          fontSize: 10,
          formatter: function(value) {
            return Math.round(value); // 确保心率显示整数
          }
        }
      },
      series: [{ data: heartRateValues }],
    });
    
    breathingChart.setOption({
      xAxis: { data: breathingTimes },
      yAxis: {
        min: Math.floor(adjustedBreathingMin),
        max: Math.ceil(adjustedBreathingMax),
        splitNumber: 4, // 显示5个刻度（包括上下边界）
        interval: (Math.ceil(adjustedBreathingMax) - Math.floor(adjustedBreathingMin)) / 4,
        axisLabel: {
          color: "#8FFFF8",
          fontSize: 10,
          formatter: function(value) {
            return Math.round(value); // 确保呼吸显示整数
          }
        }
      },
      series: [{ data: breathingValues }],
    });
  }
};

// 简单的防抖函数，避免频繁重建播放器
let resizeTimer = null;
const debounce = (fn, delay = 200) => {
  return (...args) => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => fn(...args), delay);
  };
};

// 根据容器宽度计算并设置16:9的高度，确保初始化时容器有明确像素尺寸
const setPlayerContainerSize = () => {
  const playerElement = document.getElementById("ez-video-player");
  if (!playerElement) return { width: 0, height: 0 };
  const parent = playerElement.parentElement;
  if (!parent) return { width: 0, height: 0 };
  const rect = parent.getBoundingClientRect();
  const width = Math.max(0, Math.floor(rect.width));
  const height = Math.max(0, Math.floor((rect.width * 9) / 16));
  playerElement.style.width = width + "px";
  playerElement.style.height = height + "px";
  return { width, height };
};

// 萤石云播放器方法
const initEzPlayer = async () => {
  try {
    isVideoLoading.value = true;
    videoError.value = "";
    
    // 销毁现有播放器
    if (ezPlayer) {
      destroyEzPlayer();
    }
    
    // 等待DOM元素准备就绪
    await nextTick();
    
    const playerElement = document.getElementById("ez-video-player");
    if (!playerElement) {
      throw new Error("找不到视频播放器容器");
    }
    
    // 清空容器并设置明确像素尺寸（16:9，高度由宽度计算），避免初始化时测量到0高
    playerElement.innerHTML = "";
    const { width, height } = setPlayerContainerSize();
    
            // 创建萤石云播放器
        ezPlayer = new EZUIKit.EZUIKitPlayer({
      id: "ez-video-player",
          accessToken: ezvizSettings.accessToken,
          url: ezvizSettings.accessUrl,
      header: ["capturePicture", "save", "zoom"],
      footer: ["fullScreen"],
          autoplay: true,
          audio: 1,
      template: "simple",
          // 使用明确像素，避免初始化时内部计算错误
      width: width || "100%",
      height: height || "100%",
          // 保持16:9
      aspectRatio: "16:9",
          handleSuccess: () => {
        console.log("萤石云视频加载成功");
        isVideoPlaying.value = true;
        isVideoLoading.value = false;
        videoError.value = "";
        
        // 强制调整播放器尺寸
        setTimeout(() => {
          const playerElement = document.getElementById("ez-video-player");
          if (playerElement) {
            // 特别处理ez-video-player-wrap
            const wrapElement = playerElement.querySelector(
              ".ez-video-player-wrap"
            );
            if (wrapElement) {
              wrapElement.style.width = "100%";
              wrapElement.style.height = "100%";
              wrapElement.style.position = "absolute";
              wrapElement.style.top = "0";
              wrapElement.style.left = "0";
              wrapElement.style.right = "0";
              wrapElement.style.bottom = "0";
            }
            
            // 强制重新设置所有子元素的尺寸
            const allElements = playerElement.querySelectorAll("*");
            allElements.forEach(el => {
              if (el.style) {
                el.style.width = "100%";
                el.style.height = "100%";
                el.style.maxWidth = "none";
                el.style.maxHeight = "none";
                el.style.minWidth = "100%";
                el.style.minHeight = "100%";
              }
            });
          }
        }, 500);
        
        // 额外的延迟调整，确保播放器完全加载
        setTimeout(() => {
          const playerElement = document.getElementById("ez-video-player");
          if (playerElement) {
            const parentRect =
              playerElement.parentElement.getBoundingClientRect();
            const wrapElement = playerElement.querySelector(
              ".ez-video-player-wrap"
            );
            if (wrapElement && parentRect) {
              wrapElement.style.width = parentRect.width + "px";
              wrapElement.style.height = parentRect.height + "px";
            }
          }
        }, 1000);
      },
      handleError: error => {
        console.error("萤石云播放器错误:", error);
        const errorMsg = error?.errorMsg || error?.message || "视频加载失败";
        videoError.value = errorMsg;
        isVideoLoading.value = false;
        isVideoPlaying.value = false;
      },
    });

    console.log("萤石云播放器初始化成功");
    
    // 创建MutationObserver监听DOM变化
    const observer = new MutationObserver(() => {
      const playerElement = document.getElementById("ez-video-player");
      if (playerElement) {
        const wrapElement = playerElement.querySelector(
          ".ez-video-player-wrap"
        );
        if (wrapElement) {
          // 确保wrap元素始终填充容器
          const computedStyle = window.getComputedStyle(wrapElement);
          if (
            computedStyle.width !== "100%" ||
            computedStyle.height !== "100%"
          ) {
            wrapElement.style.width = "100%";
            wrapElement.style.height = "100%";
            wrapElement.style.position = "absolute";
            wrapElement.style.top = "0";
            wrapElement.style.left = "0";
          }
        }
      }
    });
    
    // 开始观察
    const playerElementRoot = document.getElementById("ez-video-player");
    if (playerElementRoot) {
      observer.observe(playerElementRoot, { 
        childList: true, 
        subtree: true, 
        attributes: true,
        attributeFilter: ["style", "class"],
      });
    }

    // 监听窗口尺寸变化，重新计算容器尺寸并刷新播放器
    if (!resizeHandlerRegistered) {
      const onResize = debounce(() => {
        setPlayerContainerSize();
        // 一些情况下需要重建才能生效
        refreshEzPlayer();
      }, 250);
      window.addEventListener("resize", onResize);
      resizeHandlerRegistered = true;
    }
  } catch (error) {
    console.error("初始化萤石云播放器失败:", error);
    videoError.value = error.message || "播放器初始化失败";
    isVideoLoading.value = false;
  }
};

const stopEzPlayer = () => {
  if (ezPlayer && isVideoPlaying.value) {
    try {
      ezPlayer.stop();
      isVideoPlaying.value = false;
      console.log("萤石云视频已停止");
    } catch (error) {
      console.error("停止萤石云视频失败:", error);
    }
  }
};

const destroyEzPlayer = () => {
  if (ezPlayer) {
    try {
      ezPlayer.stop();
      ezPlayer = null;
      isVideoPlaying.value = false;
      console.log("萤石云播放器已销毁");
    } catch (error) {
      console.error("销毁萤石云播放器出错:", error);
    }
  }
};

const refreshEzPlayer = () => {
  initEzPlayer();
};

// 萤石云设置相关方法
const openEzvizSettings = () => {
  tempAccessToken.value = ezvizSettings.value.accessToken || '';
  tempAccessUrl.value = ezvizSettings.value.accessUrl || '';
  testResult.value = null;
  showEzvizSettings.value = true;
};

const closeEzvizSettings = () => {
  showEzvizSettings.value = false;
  tempAccessToken.value = '';
  tempAccessUrl.value = '';
  testResult.value = null;
  isTestingConnection.value = false;
};

const testEzvizConnection = async () => {
  if (!tempAccessToken.value.trim()) {
    testResult.value = {
      type: 'error',
      message: '请输入Access Token'
    };
    return;
  }
  
  if (!tempAccessUrl.value.trim()) {
    testResult.value = {
      type: 'error',
      message: '请输入Access URL'
    };
    return;
  }
  
  isTestingConnection.value = true;
  testResult.value = null;
  
  try {
    // 创建临时播放器测试连接
    const testPlayer = new EZUIKit.EZUIKitPlayer({
      id: 'test-player-temp',
      accessToken: tempAccessToken.value.trim(),
      url: tempAccessUrl.value.trim(),
      autoplay: false,
      template: 'simple',
      width: 1,
      height: 1,
      handleSuccess: () => {
        testResult.value = {
          type: 'success',
          message: '连接测试成功！配置有效'
        };
        isTestingConnection.value = false;
        // 清理测试播放器
        if (testPlayer) {
          try {
            testPlayer.stop();
          } catch (e) {
            console.log('清理测试播放器:', e);
          }
        }
      },
      handleError: (error) => {
        console.error('萤石云连接测试失败:', error);
        testResult.value = {
          type: 'error',
          message: '连接测试失败：' + (error?.errorMsg || error?.message || '配置无效或网络错误')
        };
        isTestingConnection.value = false;
      }
    });
    
    // 设置超时
    setTimeout(() => {
      if (isTestingConnection.value) {
        testResult.value = {
          type: 'error',
          message: '连接测试超时，请检查网络或配置信息'
        };
        isTestingConnection.value = false;
        if (testPlayer) {
          try {
            testPlayer.stop();
          } catch (e) {
            console.log('清理超时测试播放器:', e);
          }
        }
      }
    }, 10000);
    
  } catch (error) {
    console.error('测试连接时发生错误:', error);
    testResult.value = {
      type: 'error',
      message: '测试失败：' + (error.message || '未知错误')
    };
    isTestingConnection.value = false;
  }
};

const saveEzvizSettings = () => {
  if (!tempAccessToken.value.trim()) {
    testResult.value = {
      type: 'error',
      message: '请输入Access Token'
    };
    return;
  }
  
  if (!tempAccessUrl.value.trim()) {
    testResult.value = {
      type: 'error',
      message: '请输入Access URL'
    };
    return;
  }
  
  // 更新配置
  ezvizSettings.value.accessToken = tempAccessToken.value.trim();
  ezvizSettings.value.accessUrl = tempAccessUrl.value.trim();
  
  // 如果当前正在使用萤石云，重新初始化播放器
  if (currentVideoSource.value === 'ezviz') {
    refreshEzPlayer();
  }
  
  // 关闭弹窗
  closeEzvizSettings();
  
  // 显示保存成功提示
  addEventLog('萤石云配置已更新', 'success');
};

// YOLOv11-pose WebSocket连接功能
const connectYoloWebSocket = () => {
  if (yoloWebSocket.value && yoloWebSocket.value.readyState === WebSocket.OPEN) {
    return;
  }
  
  isYoloLoading.value = true;
  yoloError.value = "";
  
  try {
    const wsUrl = 'ws://127.0.0.1:8000/ws/stream';
    yoloWebSocket.value = new WebSocket(wsUrl);
    
    yoloWebSocket.value.onopen = () => {
      console.log('YOLOv11-pose WebSocket连接已建立');
      isYoloConnected.value = true;
      isYoloLoading.value = false;
      addEventLog('YOLOv11-pose视频流连接成功', 'success');
    };
    
    yoloWebSocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // 更新视频帧
        if (data.frame) {
          yoloFrameData.value = 'data:image/jpeg;base64,' + data.frame;
        }
        
        // 更新检测结果
        if (data.detections) {
          yoloDetections.value = data.detections;
          yoloStats.value.detectedPersons = data.detections.length;
        }
        
        // 更新统计信息
        if (data.timestamp) {
          const latency = Date.now() - (data.timestamp * 1000);
          yoloStats.value.latency = Math.abs(latency);
        }
        
        // 模拟移动检测（假数据，体动模式时显示体动）
        if (isBodyMovementActive.value) {
          yoloStats.value.isMoving = "体动";
        } else {
          yoloStats.value.isMoving = false; // 默认静止状态
        }
        
      } catch (error) {
        console.error('YOLOv11-pose数据解析错误:', error);
        yoloError.value = '数据解析错误';
      }
    };
    
    yoloWebSocket.value.onerror = (error) => {
      console.error('YOLOv11-pose WebSocket错误:', error);
      yoloError.value = 'WebSocket连接错误，请确保YOLOv11-pose服务正在运行';
      isYoloConnected.value = false;
      isYoloLoading.value = false;
      addEventLog('YOLOv11-pose连接失败', 'error');
    };
    
    yoloWebSocket.value.onclose = () => {
      console.log('YOLOv11-pose WebSocket连接已关闭');
      isYoloConnected.value = false;
      isYoloLoading.value = false;
      addEventLog('YOLOv11-pose连接已断开', 'info');
      
      // 5秒后自动重连
      setTimeout(() => {
        if (!isYoloConnected.value && currentVideoSource.value === 'yolo') {
          connectYoloWebSocket();
        }
      }, 5000);
    };
    
  } catch (error) {
    console.error('YOLOv11-pose WebSocket初始化失败:', error);
    yoloError.value = 'WebSocket初始化失败';
    isYoloLoading.value = false;
    addEventLog('YOLOv11-pose初始化失败', 'error');
  }
};

const disconnectYoloWebSocket = () => {
  if (yoloWebSocket.value) {
    yoloWebSocket.value.close();
    yoloWebSocket.value = null;
    isYoloConnected.value = false;
    yoloFrameData.value = "";
    yoloDetections.value = [];
  }
};

const refreshYoloConnection = () => {
  disconnectYoloWebSocket();
  setTimeout(() => {
    connectYoloWebSocket();
  }, 500);
};

// 视频源切换功能
const switchVideoSource = (source) => {
  if (currentVideoSource.value === source) return;
  
  currentVideoSource.value = source;
  addEventLog(`切换到${source === 'yolo' ? 'YOLOv11-pose检测' : '萤石云'}视频源`, 'info');
  
  if (source === 'yolo') {
    // 切换到YOLOv11-pose，连接WebSocket
    connectYoloWebSocket();
  } else {
    // 切换到萤石云，断开YOLO WebSocket以节省资源
    disconnectYoloWebSocket();
    // 确保萤石云播放器运行
    if (!isVideoPlaying.value) {
      refreshEzPlayer();
    }
  }
};

let chartResizeObserver;

onMounted(() => {
  // 初始化数据
  updateRealTimeData();
  
  // 等待DOM渲染完成后初始化图表
  nextTick(() => {
    initCharts();
    chartResizeObserver = new ResizeObserver(() => {
      heartRateChart?.resize();
      breathingChart?.resize();
    });
    document.querySelectorAll('.vital-chart').forEach(el => chartResizeObserver.observe(el));
    
    // 默认无数据模式，不连接监控视频
    // 只有按N键进入正常模式时才连接
    
    // 每1秒更新一次实时数据
    setInterval(updateRealTimeData, 1000);
    
    // 监听键盘事件
    window.addEventListener("keydown", handleKeydown);
    window.addEventListener("keyup", handleKeyup);
    
    // 初始应用一次无数据模式快照
    applyModeSnapshot();
  });
});

onUnmounted(() => {
  // 组件卸载时清理资源
  chartResizeObserver?.disconnect();
  heartRateChart?.dispose();
  breathingChart?.dispose();
  destroyEzPlayer();
  disconnectYoloWebSocket();
    window.removeEventListener("keydown", handleKeydown);
    window.removeEventListener("keyup", handleKeyup);
});
</script>

<template>
  <div class="app-container" :class="{ 'alarm-active': isAlarmActive, 'mild-fall-active': isMildFallActive }">

      
      <!-- 头部标题 -->
      <div class="header-title">
      <h1>多模态融合数据可视化大屏</h1>
      </div>
      
    <div class="main-body">
      <!-- 三列布局主体 -->
      <div class="content-wrapper">
        <!-- 左侧内容 -->
        <div class="left-content">
          <!-- 跌倒检测雷达 -->
          <div class="section-box">
            <div class="section-header">
              <div class="section-title">
                {{ fallDetectionRadar.deviceType }}
              </div>
              <div
                class="device-selector"
                @click="toggleDropdown('fallDetection')"
              >
                <span class="device-location">{{  
                  isNoDataMode || isNetworkDisconnected ? '--' : fallDetectionRadar.location
                }}</span>
                <span class="dropdown-arrow">▼</span>
                <div v-if="dropdownVisible.fallDetection" class="dropdown-menu">
                  <div 
                    v-for="room in roomOptions" 
                    :key="room" 
                    class="dropdown-item"
                    @click.stop="selectRoom('fallDetection', room)"
                  >
                    {{ room }}
                  </div>
                </div>
              </div>
            </div>
            <div class="section-content">
              <div class="radar-circles-container">
                <div class="radar-circle green">
                  <div class="circle-content">
                    <div class="circle-label large-text">
                      {{ isNoDataMode || isNetworkDisconnected ? '--' : fallDetectionRadar.motionState }}
                    </div>
              </div>
              </div>
                <div class="radar-circle blue">
                  <div class="circle-content">
                    <div
                      class="circle-label large-text"
                      :class="{
                        'danger-text':
                          (isAlarmActive || isMildFallActive) &&
                          fallDetectionRadar.standingState === '跌倒',
                      }"
                    >
                      {{ isNoDataMode || isNetworkDisconnected ? '--' : fallDetectionRadar.standingState }}
                    </div>
              </div>
                </div>

                <div class="radar-circle cyan">
                  <div class="circle-content">
                    <div class="circle-label">距离</div>
                    <div class="circle-value">
                      {{ isNoDataMode || isNetworkDisconnected ? '--' : fallDetectionRadar.distance }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 防摔马甲 -->
          <div class="section-box">
            <div class="section-header">
              <div class="section-title">{{ antifalVest.deviceType }}</div>
              <div class="device-selector" @click="toggleDropdown('antifal')">
                <span class="device-location">{{ isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.location }}</span>
                <span class="dropdown-arrow">▼</span>
                <div v-if="dropdownVisible.antifal" class="dropdown-menu">
                  <div 
                    v-for="room in roomOptions" 
                    :key="room" 
                    class="dropdown-item"
                    @click.stop="selectRoom('antifal', room)"
                  >
                    {{ room }}
                  </div>
                </div>
              </div>
            </div>
            <div class="section-content">
              <div class="status-item">
                <span class="label">气囊状态：</span>
                <span
                  class="value"
                  :class="{
                    'danger-text':
                      isAlarmActive && antifalVest.airbagStatus === '已充气',
                  }"
                  >{{ isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.airbagStatus }}</span
                >
              </div>
              <div class="sensor-data">
                <div class="sensor-group">
                  <div class="sensor-title">三轴加速度计</div>
                  <div class="sensor-grid">
                    <div class="sensor-item">
                      <span class="axis-label">X</span>
                      <span class="axis-value">{{
                        isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.acceleration.x.toFixed(2)
                      }}</span>
                      <span class="axis-unit">m/s²</span>
                    </div>
                    <div class="sensor-item">
                      <span class="axis-label">Y</span>
                      <span class="axis-value">{{
                        isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.acceleration.y.toFixed(2)
                      }}</span>
                      <span class="axis-unit">m/s²</span>
                    </div>
                    <div class="sensor-item">
                      <span class="axis-label">Z</span>
                      <span class="axis-value">{{
                        isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.acceleration.z.toFixed(2)
                      }}</span>
                      <span class="axis-unit">m/s²</span>
                    </div>
                  </div>
                </div>
                <div class="sensor-group">
                  <div class="sensor-title">陀螺仪传感器</div>
                  <div class="sensor-grid">
                    <div class="sensor-item">
                      <span class="axis-label">俯仰</span>
                      <div class="axis-value-unit">
                        <span class="axis-value">{{
                          isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.gyroscope.pitch.toFixed(1)
                        }}</span>
                        <span class="axis-unit">°</span>
                      </div>
                  </div>
                    <div class="sensor-item">
                      <span class="axis-label">翻滚</span>
                      <div class="axis-value-unit">
                        <span class="axis-value">{{
                          isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.gyroscope.roll.toFixed(1)
                        }}</span>
                        <span class="axis-unit">°</span>
                      </div>
                    </div>
                    <div class="sensor-item">
                      <span class="axis-label">偏航</span>
                      <div class="axis-value-unit">
                        <span class="axis-value">{{
                          isNoDataMode || isNetworkDisconnected ? '--' : antifalVest.gyroscope.yaw.toFixed(1)
                        }}</span>
                        <span class="axis-unit">°</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 中间内容 -->
        <div class="center-content">
          <!-- 监控画面 -->
          <div class="monitor-section">
            <div class="section-header">
              <div class="section-title">
                {{ surveillanceCamera.deviceType }}
                <!-- 萤石云设置按钮 -->
                <button class="ezviz-settings-btn" @click="openEzvizSettings" title="萤石云设置">
                  <svg width="16" height="16" viewBox="0 0 1084 1024" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1072.147851 406.226367c-6.331285-33.456782-26.762037-55.073399-52.047135-55.073399-0.323417 0-0.651455 0.003081-0.830105 0.009241l-4.655674 0c-73.124722 0-132.618162-59.491899-132.618162-132.618162 0-23.731152 11.447443-50.336101 11.546009-50.565574 13.104573-29.498767 3.023185-65.672257-23.427755-84.127081l-1.601687-1.127342-134.400039-74.661726-1.700252-0.745401c-8.753836-3.805547-18.334698-5.735272-28.479231-5.735272-20.789593 0-41.235746 8.344174-54.683758 22.306575-14.741683 15.216028-65.622973 58.649474-104.721083 58.649474-39.450789 0-90.633935-44.286652-105.438762-59.784516-13.518857-14.247316-34.128258-22.753199-55.127302-22.753199-9.945862 0-19.354234 1.861961-27.958682 5.531982l-1.746455 0.74078-139.141957 76.431283-1.643269 1.139662c-26.537186 18.437884-36.675557 54.579032-23.584845 84.062398 0.115506 0.264895 11.579891 26.725075 11.579891 50.634877 0 73.126262-59.491899 132.618162-132.618162 132.618162l-4.581749 0c-0.318797-0.00616-0.636055-0.01078-0.951772-0.01078-25.260456 0-45.672728 21.618157-52.002472 55.0811-0.462025 2.453354-11.313456 60.622322-11.313456 106.117939 0 45.494078 10.85143 103.659965 11.314996 106.119479 6.334365 33.458322 26.758957 55.076479 52.036353 55.076479 0.320337 0 0.651455-0.00616 0.842426-0.012321l4.655674 0c73.126262 0 132.618162 59.491899 132.618162 132.616622 0 23.760413-11.444363 50.333021-11.546009 50.565574-13.093793 29.474125-3.041666 65.646075 23.395414 84.151722l1.569346 1.093459 131.838879 73.726895 1.675611 0.7377c8.750757 3.84251 18.305437 5.790715 28.397607 5.790715 21.082208 0 41.676209-8.706094 55.0888-23.290689 18.724339-20.347588 69.527086-62.362616 107.04815-62.362616 40.625872 0 92.72537 47.100385 107.759669 63.583903 13.441852 14.831008 34.176001 23.689571 55.470741 23.695731l0.00616 0c9.895039 0 19.27877-1.883523 27.893999-5.598205l1.711034-0.73924 136.659342-75.531873 1.617088-1.128882c26.492523-18.456365 36.601633-54.600594 23.538642-84.016195-0.115506-0.267974-11.595291-27.082374-11.595291-50.67646 0-73.124722 59.49344-132.616622 132.618162-132.616622l4.517066-0.00154c0.300316 0.00616 0.599092 0.009241 0.899409 0.009241 25.331299-0.00154 45.785153-21.619697 52.107197-55.054918 0.112426-0.589852 11.325776-59.507301 11.325776-106.14104C1083.464388 466.640776 1072.609877 408.67356 1072.147851 406.226367zM377.486862 945.656142l-115.32764-64.487932c5.082277-13.052211 15.437801-43.51815 15.437801-75.017486 0-109.382917-84.176364-199.816642-192.587488-208.134635-2.647404-15.427021-8.873963-54.967133-8.873963-85.667166 0-30.65691 6.223479-70.232445 8.869343-85.671786 108.415744-8.311832 192.592108-98.745557 192.592108-208.134635 0-31.416171-10.300081-61.797405-15.371577-74.854236l122.721583-67.40331c0.003081 0 0.00462 0.00154 0.007701 0.00154 4.423121 4.518606 22.121764 22.080182 46.558275 39.493911 39.929754 28.46229 77.952885 42.894416 113.014434 42.894416 34.716571 0 72.437845-14.151831 112.115025-42.06431 24.282503-17.07953 41.896442-34.302288 46.308782-38.74543 0.009241-0.00154 0.018481-0.00462 0.026182-0.00616l118.301542 65.726159c-5.077657 13.055291-15.416239 43.499669-15.416239 74.958962 0 109.389077 84.174824 199.822802 192.590568 208.134635 2.645865 15.462442 8.872423 55.107281 8.872423 85.671786 0 30.687711-6.223479 70.241685-8.869343 85.673326C890.042174 606.334084 805.86427 696.767809 805.86427 806.158426c0 31.450053 10.317022 61.851309 15.393138 74.903519l-119.783103 66.198965c-5.168521-5.490399-22.603811-23.363073-46.740005-41.288109-40.701336-30.224145-79.662378-45.549521-115.800446-45.549521-35.79155 0-74.458435 15.038919-114.927219 44.694774C400.22004 922.554885 382.666163 940.255068 377.486862 945.656142zM731.271848 511.646647c0-105.803762-86.081448-191.88059-191.888289-191.88059-105.803762 0-191.88059 86.076827-191.88059 191.88059 0 105.803762 86.076827 191.882129 191.88059 191.882129C645.19194 703.528777 731.271848 617.450409 731.271848 511.646647zM539.383558 395.903184c63.825696 0 115.751164 51.922387 115.751164 115.743463 0 63.825696-51.925468 115.751164-115.751164 115.751164-63.821076 0-115.743463-51.925468-115.743463-115.751164C423.640095 447.824031 475.562482 395.903184 539.383558 395.903184z" fill="currentColor"/>
                  </svg>
                </button>
              </div>
              <div class="monitor-controls">
              <div class="device-selector" @click="toggleDropdown('camera')">
                <span class="device-location">{{
                  isNoDataMode || isNetworkDisconnected ? '--' : surveillanceCamera.location
                }}</span>
                <span class="dropdown-arrow">▼</span>
                <div v-if="dropdownVisible.camera" class="dropdown-menu">
                  <div 
                    v-for="room in roomOptions" 
                    :key="room" 
                    class="dropdown-item"
                    @click.stop="selectRoom('camera', room)"
                  >
                    {{ room }}
                </div>
              </div>
            </div>
          </div>
              </div>
            <div class="monitor-frame">
              <!-- YOLOv11-pose视频显示 -->
              <div 
                v-if="currentVideoSource === 'yolo'" 
                class="yolo-video-container"
                ref="yoloVideoPlayer"
              >
                <img 
                  v-if="yoloFrameData && isYoloConnected" 
                  :src="yoloFrameData" 
                  class="yolo-video-frame"
                  alt="YOLOv11-pose实时检测"
                />

              </div>
              
              <!-- 萤石云视频播放器 -->
              <div 
                v-if="currentVideoSource === 'ezviz'" 
                id="ez-video-player" 
                ref="videoPlayer"
              ></div>
              

              
              <!-- YOLOv11-pose加载状态 -->
              <div v-if="currentVideoSource === 'yolo' && isYoloLoading" class="video-loading-overlay">
                <div class="loading-spinner"></div>
                <span>YOLOv11-pose连接中...</span>
              </div>
              
              <!-- YOLOv11-pose错误状态 -->
              <div
                v-if="currentVideoSource === 'yolo' && yoloError && !isYoloLoading"
                class="video-error-overlay"
              >
                <div class="error-icon">⚠️</div>
                <div class="error-text">{{ yoloError }}</div>
                <button class="retry-btn" @click="refreshYoloConnection">重新连接</button>
              </div>
              
              <!-- 萤石云加载状态 -->
              <div v-if="currentVideoSource === 'ezviz' && isVideoLoading" class="video-loading-overlay">
                <div class="loading-spinner"></div>
                <span>萤石云加载中...</span>
              </div>
              
              <!-- 萤石云错误状态 -->
              <div
                v-if="currentVideoSource === 'ezviz' && videoError && !isVideoLoading"
                class="video-error-overlay"
              >
                <div class="error-icon">⚠️</div>
                <div class="error-text">{{ videoError }}</div>
                <button class="retry-btn" @click="refreshEzPlayer">重试</button>
            </div>
            
            </div>
            
            <!-- 监控下方操作栏 -->
            <div class="monitor-actions">
              <button class="action-btn" @click="refreshYoloConnection" :disabled="isYoloLoading" title="刷新">
                <img :src="refreshSvg" alt="刷新" class="icon" />
                <span>刷新</span>
                </button>
              <button class="action-btn" title="导出当前数据">
                导出当前数据
                </button>
              <button class="action-btn" title="监控截图">
                监控截图
                </button>
              <button class="action-btn" title="全屏查看">
                全屏查看
              </button>
              </div>
              
            <!-- AI检测统计信息区域 -->
            <div class="detection-stats-panel">
              <div class="stats-row">
                <div class="stat-item">
                  <div class="stat-label">检测人数</div>
                  <div class="stat-value">{{ isNoDataMode || isNetworkDisconnected ? '--' : yoloStats.detectedPersons }}</div>
            </div>
                <div class="stat-item">
                  <div class="stat-label">是否移动</div>
                  <div class="stat-value" :class="{ 'moving-text': yoloStats.isMoving }">
                    {{ isNoDataMode || isNetworkDisconnected ? '--' : (yoloStats.isMoving === '体动' ? '体动' : yoloStats.isMoving ? '体动' : '静止') }}
                  </div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">是否有人</div>
                  <div class="stat-value" :class="{ 'has-person': yoloStats.detectedPersons > 0 }">
                    {{ isNoDataMode || isNetworkDisconnected ? '--' : (yoloStats.detectedPersons > 0 ? '有人' : '无人') }}
                  </div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">人体状态</div>
                  <div class="stat-value" :class="{ 'danger-text': isAlarmActive || isMildFallActive }">
                    {{ isNoDataMode || isNetworkDisconnected ? '--' : ((isAlarmActive || isMildFallActive) ? "跌倒" : "正常") }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 右侧内容 -->
        <div class="right-content">
          <!-- 呼吸心率监测雷达 -->
          <div class="section-box">
            <div class="section-header">
              <div class="section-title">呼吸心率监测雷达</div>
              <div
                class="device-selector"
                @click="toggleDropdown('breathHeart')"
              >
                <span class="device-location">{{
                  isNoDataMode || isNetworkDisconnected ? '--' : breathHeartRadar.location
                }}</span>
                <span class="dropdown-arrow">▼</span>
                <div v-if="dropdownVisible.breathHeart" class="dropdown-menu">
                  <div 
                    v-for="room in roomOptions" 
                    :key="room" 
                    class="dropdown-item"
                    @click.stop="selectRoom('breathHeart', room)"
                  >
                    {{ room }}
                  </div>
                </div>
              </div>
            </div>
            <!-- 心率和呼吸监测图表 -->
            <div class="vital-signs-wrapper vertical">
              <div class="vital-sign-box">
                <div class="vital-head">
                  <div class="section-title">心率监测</div>
                  <div class="vital-display">
                    <div class="vital-value">
                      {{ isNoDataMode || isNetworkDisconnected ? '--' : breathHeartRadar.heartRate }}
                    </div>
                    <div class="vital-unit">BPM</div>
                  </div>
                </div>
                <div class="vital-chart">
                  <div
                    id="heartRateChart"
                    style="width: 100%; height: 100%"
                  ></div>
                </div>
              </div>
              
              <div class="vital-sign-box">
                <div class="vital-head">
                  <div class="section-title">呼吸监测</div>
                  <div class="vital-display">
                    <div class="vital-value">
                      {{ isNoDataMode || isNetworkDisconnected ? '--' : breathHeartRadar.breathRate }}
                    </div>
                    <div class="vital-unit">次/分</div>
                  </div>
                </div>
                <div class="vital-chart">
                  <div
                    id="breathingChart"
                    style="width: 100%; height: 100%"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
    
    <!-- 萤石云设置弹窗 -->
    <!-- eslint-disable-next-line vue/valid-template-root -->
    <div v-if="showEzvizSettings" class="settings-overlay" @click="closeEzvizSettings">
      <div class="settings-modal" @click.stop>
        <div class="settings-header">
          <h3>萤石云设置</h3>
          <button class="close-btn" @click="closeEzvizSettings">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
        <div class="settings-content">
           <div class="form-group">
             <label for="accessToken">Access Token:</label>
             <textarea 
               id="accessToken"
               v-model="tempAccessToken" 
               placeholder="请输入萤石云Access Token"
               class="settings-input settings-textarea"
               rows="3"
             ></textarea>
           </div>
           <div class="form-group">
             <label for="accessUrl">Access URL:</label>
             <input 
               id="accessUrl"
               v-model="tempAccessUrl" 
               type="text" 
               placeholder="请输入萤石云Access URL (如: ezopen://open.ys7.com/设备序列号/通道号.hd.live)"
               class="settings-input"
             />
           </div>
           <div class="settings-actions">
             <button class="test-btn" @click="testEzvizConnection" :disabled="isTestingConnection">
               <span v-if="isTestingConnection">测试中...</span>
               <span v-else>测试连接</span>
             </button>
             <button class="confirm-btn" @click="saveEzvizSettings" :disabled="isTestingConnection">
               确定
             </button>
           </div>
           <div v-if="testResult" class="test-result" :class="testResult.type">
             {{ testResult.message }}
           </div>
         </div>
      </div>
    </div>
</template>

<style scoped>
.app-container {
  width: 100vw;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  background: url("/src/assets/img/bg.png") no-repeat center center fixed;
  background-size: cover;
  position: relative;
  box-sizing: border-box;
}

/* 报警效果（更克制的工业风）：边缘细线+玻璃警戒遮罩+顶部灯条闪烁 */
.app-container.alarm-active::after {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(
      180deg,
      rgba(255, 60, 60, 0.1) 0%,
      rgba(255, 60, 60, 0) 35%,
      rgba(255, 60, 60, 0) 65%,
      rgba(255, 60, 60, 0.1) 100%
    ),
    radial-gradient(
      60% 80% at 50% -10%,
      rgba(255, 90, 90, 0.18),
      transparent 60%
    ),
    radial-gradient(
      60% 80% at 50% 110%,
      rgba(255, 90, 90, 0.18),
      transparent 60%
    );
  border: 2px solid rgba(255, 90, 90, 0.55);
  box-shadow: 0 0 12px rgba(255, 90, 90, 0.35) inset;
  animation: alarmGlow 1.6s ease-in-out infinite;
  z-index: 9999;
}

.app-container.alarm-active::before {
  content: "";
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  height: 6px;
  background: linear-gradient(
    90deg,
    rgba(255, 70, 70, 0),
    rgba(255, 70, 70, 0.55),
    rgba(255, 70, 70, 0)
  );
  filter: blur(0.6px);
  animation: scanner 1.4s linear infinite;
  z-index: 10000;
}

@keyframes alarmGlow {
  0%,
  100% {
    box-shadow: 0 0 8px rgba(255, 90, 90, 0.3) inset;
    opacity: 0.9;
  }
  50% {
    box-shadow: 0 0 18px rgba(255, 90, 90, 0.45) inset;
    opacity: 1;
  }
}

@keyframes scanner {
  0% {
    transform: translateY(0);
    opacity: 0.85;
  }
  50% {
    transform: translateY(6px);
    opacity: 0.9;
  }
  100% {
    transform: translateY(0);
    opacity: 0.85;
  }
}

/* 字体警示：标题与关键数值在报警时红色发光闪烁 */
/* 仅关键数值参与警示，标题不改色 */
/* 严重跌倒时红色样式 */
div.app-container.alarm-active .vital-value {
  color: #ff6b6b !important;
  text-shadow: 0 0 10px rgba(255, 107, 107, 0.5) !important;
  animation: textPulse 1.6s ease-in-out infinite !important;
}

/* 轻微跌倒时黄色样式 */
div.app-container.mild-fall-active .vital-value {
  color: #ffaa00 !important;
  text-shadow: 0 0 10px rgba(255, 170, 0, 0.8) !important;
  animation: textPulse 1.6s ease-in-out infinite !important;
}

/* 跌倒检测雷达的跌倒文字在报警时也变红 */
div.app-container.alarm-active .danger-text {
  color: #ff6b6b !important;
  text-shadow: 0 0 10px rgba(255, 107, 107, 0.5) !important;
  animation: textPulse 1.6s ease-in-out infinite !important;
}

/* 轻微跌倒时跌倒文字也变红 */
div.app-container.mild-fall-active .danger-text {
  color: #ff6b6b !important;
  text-shadow: 0 0 10px rgba(255, 107, 107, 0.5) !important;
  animation: textPulse 1.6s ease-in-out infinite !important;
}

@keyframes textPulse {
  0%,
  100% {
    filter: drop-shadow(0 0 2px rgba(255, 90, 90, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 6px rgba(255, 90, 90, 0.8));
  }
}

/* 隐藏滚动条 */
.app-container::-webkit-scrollbar,
.left-content::-webkit-scrollbar,
.right-content::-webkit-scrollbar,
.center-content::-webkit-scrollbar {
  display: none;
}

.app-container,
.left-content,
.right-content,
.center-content {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.app-container::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(
      circle at 20% 30%,
      rgba(64, 254, 255, 0.1) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 80% 70%,
      rgba(115, 241, 249, 0.1) 0%,
      transparent 50%
    );
  pointer-events: none;
}

.main-body {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: calc(100vh - 88px);
  padding: 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.header-title {
  text-align: center;
  margin: 0;
  background: url("/src/assets/img/top-title.png") no-repeat center center;
  background-size: 100% 100%;
  padding: 0;
  height: 88px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: translateY(-5px);
}

.header-title::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 43, 58, 0.3);
  z-index: 1;
}

.header-title h1 {
  position: relative;
  z-index: 2;
  font-size: 2.25rem;
  font-weight: bold;
  background: linear-gradient(180deg, #ffffff 0%, rgb(116, 214, 247) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
}

.subtitle {
  font-size: 1rem;
  color: #ffffff !important;
  margin-top: 8px;
  opacity: 0.9;
}

.content-wrapper {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
  height: calc(100vh - 128px);
  align-items: stretch;
  /* 确保所有子元素高度一致 */
  box-sizing: border-box;
}

.left-content,
.right-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
  max-height: 100%;
  overflow-y: auto;
  /* 添加圆角边框 */
  border-radius: 12px;
  padding: 10px;
  background: rgba(0, 43, 58, 0.1);
  border: 1px solid rgba(64, 254, 255, 0.2);
  /* 确保高度一致，缩减68px，增加5px */
  min-height: calc(100vh - 211px);
  box-sizing: border-box;
}

.center-content {
  flex: 1.5;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
  max-height: calc(100vh - 128px);
  overflow-y: auto;
  /* 添加圆角边框 */
  border-radius: 12px;
  padding: 10px;
  background: rgba(0, 43, 58, 0.1);
  border: 1px solid rgba(64, 254, 255, 0.2);
  /* 确保高度一致 */
  min-height: calc(100vh - 148px);
  box-sizing: border-box;
}

.section-box {
  background: linear-gradient(135deg, rgba(0, 43, 58, 0.5) 0%, rgba(0, 43, 58, 0.3) 100%);
  border-radius: 8px;
  padding: 20px;
  position: relative;
  /* 修改overflow设置，允许header区域的dropdown显示 */
  overflow: visible;
  background-clip: padding-box;
  flex: 1;
  min-height: 0;
  /* 设置基础z-index，创建新的stacking context */
  z-index: 1;
  /* 为背景设置0.92透明度 */
  opacity: 0.92;
  
  /* 静态内向阴影，距离更短，颜色更深 */
  box-shadow: inset 0 0 10px rgba(0, 43, 58, 0.8), inset 0 0 20px rgba(0, 43, 58, 0.6),
    inset 0 0 30px rgba(0, 43, 58, 0.4);
  
  backdrop-filter: blur(12px);
}

.section-box::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  right: -1px;
  bottom: -1px;
  border-radius: 8px;
  padding: 1px;
  background: linear-gradient(
      180deg,
      rgba(0, 0, 255, 0.05) 0%,
      rgba(0, 96, 232, 0.1) 30%,
      rgba(0, 117, 245, 0.2) 50%,
      rgba(0, 142, 252, 0.3) 70%,
      rgba(0, 158, 254, 0.4) 90%,
      rgba(2, 225, 237, 0.9) 100%
    );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: exclude;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  z-index: -1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  position: relative;
  width: 100%;
  /* 为了让dropdown能够正常显示，设置较高的z-index */
  z-index: 10;
}

/* 当dropdown展开时，为对应的容器设置更高的z-index */
.left-content .section-box:first-child {
  /* 跌倒检测雷达 - 最高优先级 */
  z-index: 100;
  /* 确保两个section-box等高分布，调整以匹配right-content */
  flex: 1;
  min-height: calc(50% - 20px);
  max-height: calc(50% - 20px);
  /* 跌倒检测雷达专用样式，使用#0fa4b7颜色 */
  border: 3px solid #0fa4b7;
  box-shadow: inset 0 0 10px rgba(15, 164, 183, 0.8), inset 0 0 20px rgba(15, 164, 183, 0.6),
    inset 0 0 30px rgba(15, 164, 183, 0.4);
}

.left-content .section-box:nth-child(2) {
  /* 防摔马甲 - 第二优先级 */
  z-index: 99;
  /* 确保两个section-box等高分布，调整以匹配right-content */
  flex: 1;
  min-height: calc(50% - 20px);
  max-height: calc(50% - 20px);
  /* 防摔马甲专用样式，使用#0fa4b7颜色 */
  border: 3px solid #0fa4b7;
  box-shadow: inset 0 0 10px rgba(15, 164, 183, 0.8), inset 0 0 20px rgba(15, 164, 183, 0.6),
    inset 0 0 30px rgba(15, 164, 183, 0.4);
}

.center-content .monitor-section {
  /* 监控摄像头 - 第三优先级 */
  z-index: 98;
  /* 监控摄像头专用样式，使用#0fa4b7颜色 */
  border: 3px solid #0fa4b7;
  box-shadow: inset 0 0 10px rgba(15, 164, 183, 0.8), inset 0 0 20px rgba(15, 164, 183, 0.6),
    inset 0 0 30px rgba(15, 164, 183, 0.4);
}

.right-content .section-box {
  /* 呼吸心率监测雷达 - 第四优先级 */
  z-index: 97;
  /* 确保右侧单个section-box填满整个高度，与左侧保持一致 */
  height: calc(100% - 20px);
  display: flex;
  flex-direction: column;
  /* 补偿高度差异，与左侧保持一致 */
  margin-top: 10px;
  margin-bottom: 10px;
  /* 静态右侧盒子样式，使用#0fa4b7颜色，但保持原背景 */
  background: linear-gradient(135deg, rgba(0, 43, 58, 0.5) 0%, rgba(0, 43, 58, 0.3) 100%);
  border: 3px solid #0fa4b7;
  box-shadow: inset 0 0 10px rgba(15, 164, 183, 0.8), inset 0 0 20px rgba(15, 164, 183, 0.6),
    inset 0 0 30px rgba(15, 164, 183, 0.4);
}

.section-title {
  font-size: 1.1rem;
  font-weight: bold;
  background: linear-gradient(180deg, #73f1f9 0%, #428bde 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  position: relative;
}

.section-title::after {
  content: "";
  position: absolute;
  bottom: -5px;
  left: 0;
  width: 30px;
  height: 2px;
  background: linear-gradient(90deg, #40feff, transparent);
}

.device-selector {
  position: relative;
  cursor: pointer;
  user-select: none;
  /* 确保dropdown可以显示在section-box之外 */
  z-index: 15;
}

.device-location {
  color: #ffffff !important;
  font-size: 0.9rem;
  margin-right: 5px;
}

.dropdown-arrow {
  color: #ffffff !important;
  font-size: 0.8rem;
  transition: transform 0.3s;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  background-color: rgba(0, 43, 58, 0.9);
  border-radius: 6px;
  background-clip: padding-box;
  box-shadow: 0 0 4px rgba(0, 240, 255, 0.6), 0 0 8px rgba(0, 240, 255, 0.3),
    0 4px 20px rgba(0, 0, 0, 0.5), inset 0 0 0 1px rgba(175, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  /* 设置非常高的z-index以确保显示在最顶层 */
  z-index: 1000;
  min-width: 80px;
  overflow: hidden;
  /* 添加边距防止贴边 */
  margin-top: 2px;
}

.dropdown-item {
  padding: 8px 12px;
  color: #ffffff !important;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.dropdown-item:hover {
  background: rgba(64, 254, 255, 0.2);
  color: #ffffff !important;
}

.dropdown-item:first-child {
  border-radius: 6px 6px 0 0;
}

.dropdown-item:last-child {
  border-radius: 0 0 6px 6px;
}

.section-content {
  color: #e6fbff;
  /* 为内容区域设置overflow hidden，保持内容不溢出 */
  overflow: hidden;
  border-radius: 8px;
  padding: 15px;
  /* 实色背景 */
  background-color: rgba(0, 43, 58, 0.8);
  position: relative;
  /* 加粗的静态#00869b边框 */
  border: 3px solid #00b3d4;
  /* 内向渐变阴影，从边框色向背景色渐变 */
  box-shadow: inset 0 0 20px rgba(0, 179, 212, 0.8), inset 0 0 40px rgba(0, 179, 212, 0.6), inset 0 0 60px rgba(0, 43, 58, 0.9);
}



.status-item,
.env-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(64, 254, 255, 0.1);
}

.label {
  color: #ffffff !important;
  font-size: 0.9rem;
}

.value {
  color: #8ffff8;
  font-weight: 500;
}

.status-normal {
  color: #ffffff !important;
  text-shadow: 0 0 8px rgba(64, 254, 255, 0.5);
}

.status-online {
  color: #40feff;
  text-shadow: 0 0 8px rgba(64, 254, 255, 0.5);
}

.sensor-data {
  margin-top: 15px;
}

.sensor-group {
  margin-bottom: 15px;
}

.sensor-title {
  color: #ffffff !important;
  font-size: 0.9rem;
  margin-bottom: 8px;
  font-weight: 500;
}

.sensor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}

.sensor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 6px;
  background: rgba(64, 254, 255, 0.1);
  border-radius: 6px;
  border: 1px solid rgba(64, 254, 255, 0.3);
  text-align: center;
}

.axis-label {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.axis-value {
  color: #ffffff !important;
  font-size: 1.4rem;
  font-weight: 700;
  line-height: 1;
}

.axis-unit {
  font-size: 0.9rem;
  margin-top: 2px;
}

.axis-value-unit {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

/* 三轴加速度计的渐变色 */
.sensor-group:first-child .axis-label,
.sensor-group:first-child .axis-unit {
  background: linear-gradient(135deg, #1E72BF 0%, #27E0C4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 陀螺仪传感器的渐变色 */
.sensor-group:last-child .axis-label,
.sensor-group:last-child .axis-unit {
  background: linear-gradient(135deg, #FF6200 0%, rgba(255, 223, 11, 0.7) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.monitor-section {
  background: linear-gradient(135deg, rgba(0, 43, 58, 0.8) 0%, rgba(15, 164, 183, 0.6) 50%, rgba(0, 134, 156, 0.8) 100%);
  border-radius: 8px;
  padding: 20px;
  position: relative;
  /* 修改overflow设置，允许header区域的dropdown显示 */
  overflow: visible;
  background-clip: padding-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  flex: 1;
  min-height: 0;
  /* 设置基础z-index，创建新的stacking context */
  z-index: 1;
  
  /* 外发光效果 */
  box-shadow: inset 0 0 15px rgba(0, 134, 156, 0.8), inset 0 0 30px rgba(0, 134, 156, 0.6),
    inset 0 0 45px rgba(0, 134, 156, 0.4), inset 0 0 0 1px rgba(0, 134, 156, 0.8);
  
  backdrop-filter: blur(10px);
}

.monitor-section::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  right: -1px;
  bottom: -1px;
  border-radius: 8px;
  padding: 1px;
  background: linear-gradient(
      180deg,
      rgba(0, 0, 255, 0.05) 0%,
      rgba(0, 96, 232, 0.1) 30%,
      rgba(0, 117, 245, 0.2) 50%,
      rgba(0, 142, 252, 0.3) 70%,
      rgba(0, 158, 254, 0.4) 90%,
      rgba(2, 225, 237, 0.9) 100%
    );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: exclude;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  z-index: -1;
}

.monitor-frame {
  width: 100%;
  aspect-ratio: 16/9;
  background: #000;
  border-radius: 8px;
  position: relative;
  border: 2px solid rgba(64, 254, 255, 0.3);
  /* 保持视频内容不溢出 */
  overflow: hidden;
}

.monitor-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 5;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #16ff6b;
  background: transparent;
}

.monitor-badge.danger {
  color: #ff4d4f;
  animation: none;
}



/* 事件日志样式 */
.data-item.success-log .stream-type {
  color: #00FF7F;
}

.data-item.error-log .stream-type {
  color: #FF6B6B;
}

@keyframes badgeBlink {
  0%,
  100% {
    text-shadow: 0 0 2px rgba(255, 77, 79, 0.5);
  }
  50% {
    text-shadow: 0 0 8px rgba(255, 77, 79, 1);
  }
}

/* 萤石云播放器容器 */
#ez-video-player {
  width: 100% !important;
  height: 100% !important;
  background: transparent;
  border-radius: 6px;
  overflow: hidden;
}

/* 萤石云播放器包装容器 */
#ez-video-player .ez-video-player-wrap,
#ez-video-player > div {
  width: 100% !important;
  height: 100% !important;
  position: relative !important;
}

/* 修复萤石云播放器的样式 */
#ez-video-player > iframe,
#ez-video-player iframe {
  width: 100% !important;
  height: 100% !important;
  border: none;
}

#ez-video-player .video-js {
  box-shadow: none !important;
  border: none !important;
  background: transparent !important;
  width: 100% !important;
  height: 100% !important;
}

#ez-video-player .video-js .vjs-control-bar {
  background-color: rgba(0, 0, 0, 0.7);
}

/* 强制萤石云播放器所有子元素填充容器 */
#ez-video-player * {
  max-width: 100% !important;
  max-height: 100% !important;
}

/* 萤石云播放器内部容器样式调整 */
#ez-video-player .ez-video-player-wrap .video-container,
#ez-video-player .video-container {
  width: 100% !important;
  height: 100% !important;
  position: relative !important;
}

/* 萤石云播放器video元素 */
#ez-video-player video {
  width: 100% !important;
  height: 100% !important;
  object-fit: fill !important;
}

/* 更强制性的样式，确保萤石云播放器填充整个容器 */
#ez-video-player [class*="ez-video-player"],
#ez-video-player [class*="video-"],
#ez-video-player [class*="player-"] {
  width: 100% !important;
  height: 100% !important;
}

/* YOLOv11-pose视频流样式 */
.yolo-video-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: #000;
  border-radius: 6px;
  overflow: hidden;
}

.yolo-video-frame {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.yolo-stats-overlay {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.8);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  gap: 15px;
  font-size: 0.8rem;
  color: #8ffff8;
  backdrop-filter: blur(10px);
}

.stats-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.stats-value {
  color: #40feff;
  font-weight: bold;
}

/* 监控控制区域 */
.monitor-controls {
  display: flex;
  align-items: center;
  gap: 15px;
}

/* 连接状态指示器 */
.connection-indicator {
  font-size: 0.8rem;
  padding: 4px 8px;
  border-radius: 12px;
  background: rgba(255, 0, 0, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(255, 0, 0, 0.3);
  transition: all 0.3s ease;
}

.connection-indicator.connected {
  background: rgba(0, 255, 0, 0.2);
  color: #00ff7f;
  border-color: rgba(0, 255, 0, 0.3);
}

/* 检测统计信息面板 */
.detection-stats-panel {
  margin-top: 20px;
  background: rgba(0, 43, 58, 0.9);
  border-radius: 8px;
  padding: 20px;
  border: 1px solid rgba(64, 254, 255, 0.3);
  box-shadow: inset 0 0 15px rgba(0, 134, 156, 0.8), inset 0 0 30px rgba(0, 134, 156, 0.6),
    inset 0 0 45px rgba(0, 134, 156, 0.4), inset 0 0 0 1px rgba(0, 134, 156, 0.8);
  backdrop-filter: blur(10px);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 15px;
  background: rgba(64, 254, 255, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(64, 254, 255, 0.2);
  transition: all 0.3s ease;
}

.stat-item:hover {
  background: rgba(64, 254, 255, 0.15);
  box-shadow: 0 0 10px rgba(64, 254, 255, 0.3);
}

.stat-label {
  color: #ffffff !important;
  font-size: 0.9rem;
  margin-bottom: 8px;
  font-weight: 700;
  text-shadow: 0 0 3px rgba(255, 255, 255, 0.5);
}

.stat-value {
  color: #ffffff;
  font-size: 1.8rem;
  font-weight: bold;
  text-shadow: 0 0 5px rgba(255, 255, 255, 0.6);
  line-height: 1;
}

.stat-value.has-person {
  color: #00ff7f;
  text-shadow: 0 0 10px rgba(0, 255, 127, 0.5);
}

.stat-value.danger-text {
  color: #ff6b6b;
  text-shadow: 0 0 10px rgba(255, 107, 107, 0.5);
  animation: textPulse 1.6s ease-in-out infinite;
}

/* 响应式适配 */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
  }
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  
  .stat-value {
    font-size: 1.5rem;
  }
}

/* 特别针对ez-video-player-wrap */
#ez-video-player .ez-video-player-wrap {
  width: 100% !important;
  height: 100% !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
}

/* 针对可能的固定尺寸进行覆盖 */
#ez-video-player [style*="width"],
#ez-video-player [style*="height"] {
  width: 100% !important;
  height: 100% !important;
}

/* 确保播放器初始化后重新调整尺寸 */
.monitor-frame #ez-video-player {
  position: absolute;
  top: 0;
  left: 0;
  width: 100% !important;
  height: 100% !important;
  z-index: 1;
}

/* 使用更具体的选择器覆盖萤石云默认样式 */
.monitor-frame #ez-video-player > div,
.monitor-frame #ez-video-player > div > div,
.monitor-frame #ez-video-player .ez-video-player-wrap,
.monitor-frame #ez-video-player .video-container {
  width: 100% !important;
  height: 100% !important;
  max-width: none !important;
  max-height: none !important;
  min-width: 100% !important;
  min-height: 100% !important;
  position: relative !important;
}

/* 强制覆盖任何可能的固定尺寸 */
#ez-video-player * {
  box-sizing: border-box !important;
}

/* 特殊处理可能存在的内联样式 */
#ez-video-player [style] {
  width: 100% !important;
  height: 100% !important;
}

/* 最终的强制规则 - 使用更高优先级 */
.monitor-frame #ez-video-player .ez-video-player-wrap {
  width: 100% !important;
  height: 100% !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  transform: none !important;
}

/* 萤石云播放器可能使用的固定尺寸类名 */
#ez-video-player .ez-video-player-wrap[style*="width"],
#ez-video-player .ez-video-player-wrap[style*="height"] {
  width: 100% !important;
  height: 100% !important;
}

/* 最高优先级的CSS变量重写 */
#ez-video-player .ez-video-player-wrap {
  width: var(--ez-player-width, 100%) !important;
  height: var(--ez-player-height, 100%) !important;
  --ez-player-width: 100% !important;
  --ez-player-height: 100% !important;
}

/* 视频加载状态 */
.video-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 43, 58, 0.9);
  color: #8ffff8;
  gap: 15px;
  z-index: 10;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(64, 254, 255, 0.3);
  border-top: 3px solid #40feff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* 视频错误状态 */
.video-error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 43, 58, 0.9);
  color: #f56c6c;
  gap: 15px;
  z-index: 10;
}

.error-icon {
  font-size: 2rem;
}

.error-text {
  color: #8ffff8;
  text-align: center;
  font-size: 0.9rem;
  max-width: 80%;
  line-height: 1.4;
}

.retry-btn {
  background: #40feff;
  color: #002b3a;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.3s ease;
}

.retry-btn:hover {
  background: #73f1f9;
  transform: translateY(-1px);
}

/* 视频控制按钮 */
.video-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.6);
  padding: 5px 10px;
  border-radius: 20px;
  z-index: 5;
}

.control-btn {
  background: transparent;
  border: none;
  color: #8ffff8;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  font-size: 1.2rem;
  transition: all 0.3s ease;
}

.control-btn:hover {
  background: rgba(64, 254, 255, 0.2);
  color: #40feff;
}

.device-info {
  color: #8ffff8;
  font-size: 0.8rem;
  white-space: nowrap;
}

.camera-placeholder {
  text-align: center;
  color: #8ffff8;
}

.camera-icon {
  font-size: 3rem;
  margin-bottom: 10px;
  filter: drop-shadow(0 0 10px rgba(64, 254, 255, 0.5));
}

.camera-text {
  font-size: 1.2rem;
  margin-bottom: 10px;
}

.camera-status {
  font-size: 0.9rem;
  color: #d6ebff;
}

.vital-signs-wrapper {
  display: flex;
  gap: 20px;
}

.vital-signs-wrapper.vertical {
  flex-direction: column;
  gap: 11px;
}

.vital-sign-box {
  flex: 1;
  background-color: rgba(0, 43, 58, 0.8);
  border: 3px solid #00b3d4;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  position: relative;
  overflow: hidden;
  background-clip: padding-box;
  
  /* 内向渐变阴影，从边框色向背景色渐变 */
  box-shadow: inset 0 0 20px rgba(0, 179, 212, 0.8), inset 0 0 40px rgba(0, 179, 212, 0.6), inset 0 0 60px rgba(0, 43, 58, 0.9);
  
  backdrop-filter: blur(10px);
}

.vital-sign-box::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  right: -1px;
  bottom: -1px;
  border-radius: 8px;
  padding: 1px;
  background: linear-gradient(
      0deg,
      rgba(175, 255, 255, 0.3) 0%,
      rgba(175, 255, 255, 0.8) 50%,
      rgba(175, 255, 255, 0.3) 100%
    ),
    linear-gradient(
      90deg,
      rgba(175, 255, 255, 0.3) 0%,
      rgba(175, 255, 255, 0.8) 50%,
      rgba(175, 255, 255, 0.3) 100%
    );
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: exclude;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  z-index: -1;
}

.vital-display {
  margin: 20px 0;
}

.vital-value {
  font-size: 2.5rem;
  font-weight: bold;
  color: white;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
  line-height: 1;
}

.vital-unit {
  color: #8ffff8;
  font-size: 0.9rem;
  margin-top: 5px;
}

.vital-chart {
  height: 160px;
  background: rgba(0, 43, 58, 0.4);
  border-radius: 6px;
  border: 1px solid rgba(64, 254, 255, 0.3);
  overflow: hidden;
  display: block;
  position: relative;
}

.vertical .vital-chart {
  height: 140px;
}

/* 心率/呼吸头部同行布局 */
.vital-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

/* 垂直布局下的紧凑头部与数值样式 */
.vertical .vital-sign-box {
  padding: 27.5px;
  background-color: rgba(0, 43, 58, 0.9) !important;
}
.vertical .vital-head {
  margin-bottom: 4px;
}
.vertical .vital-display {
  margin: 6px 0 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.vertical .vital-value {
  font-size: 2rem;
}
.vertical .vital-unit {
  font-size: 0.9rem;
  margin-top: 5px;
}
.vertical .vital-sign-box .section-title {
  font-size: 1rem;
  margin: 0 0 10px;
}

/* 撤回对 ECharts 容器的强制限制，恢复到两步前 */

.vertical .vital-sign-box {
  margin-bottom: 8px;
  background-color: rgba(0, 43, 58, 0.9) !important;
}

.vertical .vital-sign-box .section-title {
  font-size: 1rem;
  margin-bottom: 10px;
  text-align: center;
}

.vertical .vital-display {
  margin: 15px 0;
}

.vertical .vital-value {
  font-size: 2rem;
  color: #ffffff !important;
}

/* 跌倒监测雷达圆形样式 */
.radar-circles-container {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.radar-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: rgba(0, 43, 58, 0.6);
  backdrop-filter: blur(10px);
}



.radar-circle.green {
  border: 2px solid #00ffb3;
  box-shadow: 0 0 8px rgba(0, 255, 179, 0.4),
    inset 0 0 20px rgba(0, 255, 179, 0.1);
  background: linear-gradient(to bottom, rgba(0, 255, 179, 0.1), rgba(0, 255, 179, 0.8));
}

.radar-circle.blue {
  border: 2px solid #00a8ff;
  box-shadow: 0 0 8px rgba(0, 168, 255, 0.4),
    inset 0 0 20px rgba(0, 168, 255, 0.1);
  background: linear-gradient(to bottom, rgba(0, 168, 255, 0.1), rgba(0, 168, 255, 0.8));
}

.radar-circle.orange {
  border: 2px solid #ffa500;
  box-shadow: 0 0 8px rgba(255, 165, 0, 0.4),
    inset 0 0 20px rgba(255, 165, 0, 0.1);
  background: linear-gradient(to bottom, rgba(255, 165, 0, 0.1), rgba(255, 165, 0, 0.8));
}

.radar-circle.cyan {
  border: 2px solid #e4b249;
  box-shadow: 0 0 8px rgba(228, 178, 73, 0.4),
    inset 0 0 20px rgba(228, 178, 73, 0.1);
  background: linear-gradient(to bottom, rgba(228, 178, 73, 0.1), rgba(228, 178, 73, 0.8));
}

.circle-content {
  text-align: center;
  color: #ffffff !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.circle-value {
  font-size: 0.9rem;
  font-weight: 500;
  color: #ffffff !important;
  margin-top: 2px;
}

.circle-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: #ffffff !important;
  white-space: nowrap;
  line-height: 1.2;
}

.circle-label.large-text {
  font-size: 1.8rem;
  font-weight: 700;
  color: #ffffff !important;
}

/* 通用危险文本（更柔和的警示红） */
.danger-text {
  color: #ff6b6b !important;
}

.chart-placeholder {
  color: #8ffff8;
  font-size: 0.8rem;
  opacity: 0.9;
}

.device-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.device-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: rgba(64, 254, 255, 0.05);
  border-radius: 6px;
  border-left: 3px solid #40feff;
}

.device-name {
  color: #d6ebff;
  font-size: 0.9rem;
}

.device-status {
  font-weight: 500;
  font-size: 0.85rem;
}

.data-stream {
  max-height: 200px;
  overflow-y: auto;
}

.stream-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  margin-bottom: 6px;
  background: rgba(64, 254, 255, 0.05);
  border-radius: 4px;
  font-size: 0.8rem;
}

.stream-time {
  color: #8ffff8;
  font-family: monospace;
}

.stream-type {
  color: #d6ebff;
}

.stream-value {
  color: #40feff;
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .header-title h1 {
    font-size: 2.2rem;
  }
  
  .content-wrapper {
    gap: 15px;
  }
}

@media (max-width: 1200px) {
  .content-wrapper {
    flex-direction: column;
    gap: 15px;
  }
  
  .vital-signs-wrapper {
    flex-direction: column;
    gap: 15px;
  }
  
  .header-title h1 {
    font-size: 2rem;
  }
  
  .main-body {
    padding: 15px;
  }
}

@media (max-width: 768px) {
  .header-title h1 {
    font-size: 1.8rem;
  }
  
  .main-body {
    padding: 10px;
  }
  
  .section-box {
    padding: 15px;
  }
  
  .vital-value {
    font-size: 2rem;
  }
}

/* 滚动条样式 */
.data-stream::-webkit-scrollbar {
  width: 4px;
}

.data-stream::-webkit-scrollbar-track {
  background: rgba(64, 254, 255, 0.1);
  border-radius: 2px;
}

.data-stream::-webkit-scrollbar-thumb {
  background: #40feff;
  border-radius: 2px;
}



/* 动画效果 */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.9;
  }
}

.status-normal,
.status-online {
  animation: pulse 2s infinite;
}

/* 静态样式 - 移除动画效果 */
.section-box {
  /* 静态边框和阴影，颜色更深，距离更短 */
  border: 3px solid rgba(0, 43, 58, 0.9);
  box-shadow: inset 0 0 10px rgba(0, 43, 58, 0.8), inset 0 0 20px rgba(0, 43, 58, 0.6),
    inset 0 0 30px rgba(0, 43, 58, 0.4);
  background: linear-gradient(135deg, rgba(0, 43, 58, 0.4) 0%, rgba(0, 43, 58, 0.3) 100%);
}

.monitor-section {
  /* 静态边框和阴影，颜色更深，距离更短 */
  border: 3px solid rgba(0, 43, 58, 0.9);
  box-shadow: inset 0 0 10px rgba(0, 43, 58, 0.8), inset 0 0 20px rgba(0, 43, 58, 0.6),
    inset 0 0 30px rgba(0, 43, 58, 0.4);
  background: linear-gradient(135deg, rgba(0, 43, 58, 0.4) 0%, rgba(0, 43, 58, 0.3) 100%);
}



.vital-sign-box {
  transition: all 0.3s ease;
}



/* 操作栏 */
.monitor-actions {
  margin-top: 16px;
  margin-bottom: 18px; /* 与统计面板的间距 */
  display: flex;
  gap: 12px;
  align-self: stretch;
  width: 100%; /* 修复溢出 */
  margin-left: 0;
  margin-right: 0;
  justify-content: space-evenly; /* 居中且均匀分布 */
  align-items: center;
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(0, 43, 58, 0.9);
  color: #ffffff !important;
  font-weight: 700;
  text-shadow: 0 0 3px rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(64, 254, 255, 0.3);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 120px; /* 统一按钮宽度，分布更均匀 */
  justify-content: center;
}

.action-btn:hover {
  background: rgba(64, 254, 255, 0.1);
  color: #40feff;
}

.action-btn .icon {
  width: 16px;
  height: 16px;
  display: block;
}

/* 检测统计信息面板（更紧凑且修复宽度溢出） */
.detection-stats-panel {
  margin-top: 0; /* 与上方间距由monitor-actions控制 */
  padding: 12px;
  align-self: stretch;
  width: 100%; /* 修复溢出 */
  margin-left: 0;
  margin-right: 0;
  box-sizing: border-box;
}

.stats-row {
  gap: 14px; /* 稍微增大内部间距以适配更宽区域 */
}

.stat-label {
  font-size: 0.75rem;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 1.15rem; /* 紧凑 */
}

@media (max-width: 768px) {
  .stat-value {
    font-size: 1rem;
  }
}

/* 移动状态样式 */
.moving-text {
  color: #40feff !important;
  text-shadow: 0 0 6px rgba(64, 254, 255, 0.5);
  animation: movingPulse 1.5s ease-in-out infinite;
}

@keyframes movingPulse {
  0%, 100% {
    filter: drop-shadow(0 0 2px rgba(64, 254, 255, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 6px rgba(64, 254, 255, 0.8));
  }
}

/* 网络断开覆盖层样式 */
.network-disconnected-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(5px);
}

.disconnect-message {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  border: 2px solid #ff6b6b;
  border-radius: 15px;
  padding: 40px;
  text-align: center;
  color: white;
  box-shadow: 0 10px 30px rgba(255, 107, 107, 0.3);
}

.disconnect-icon {
  font-size: 4rem;
  margin-bottom: 20px;
  animation: pulse 2s infinite;
}

.disconnect-message h2 {
  color: #ff6b6b;
  margin: 0 0 15px 0;
  font-size: 1.8rem;
}

.disconnect-message p {
  margin: 0 0 25px 0;
  color: #ccc;
  font-size: 1.1rem;
}

.loading-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.loading-dots span {
  width: 12px;
  height: 12px;
  background: #ff6b6b;
  border-radius: 50%;
  animation: loadingDots 1.5s infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.3s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.6s;
}

@keyframes loadingDots {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

/* 萤石云设置按钮样式 */
.ezviz-settings-btn {
  background: none;
  border: none;
  padding: 4px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 8px;
  border-radius: 4px;
}

.ezviz-settings-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.section-title {
  display: flex;
  align-items: center;
}

/* 设置弹窗样式 */
.settings-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.settings-modal {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 0;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  color: white;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.settings-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: white;
}

.close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.settings-content {
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: white;
}

.settings-input {
  width: 100%;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: 14px;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.settings-textarea {
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
  line-height: 1.4;
}

.settings-input:focus {
  outline: none;
  border-color: #4CAF50;
  background: rgba(255, 255, 255, 0.08);
}

.settings-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.settings-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.test-btn, .confirm-btn {
  flex: 1;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.test-btn {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.test-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
}

.confirm-btn {
  background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
  color: white;
}

.confirm-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #45a049 0%, #3d8b40 100%);
}

.test-btn:disabled, .confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-result {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-top: 8px;
}

.test-result.success {
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid rgba(76, 175, 80, 0.3);
  color: #81C784;
}

.test-result.error {
  background: rgba(244, 67, 54, 0.2);
  border: 1px solid rgba(244, 67, 54, 0.3);
  color: #EF5350;
}

/* 桌面大屏：三列共享可用高度，内容随面板伸缩。 */
@media (min-width: 1201px) {
  .main-body { height: calc(100vh - 88px); min-height: 720px; }
  .content-wrapper { height: 100%; min-height: 0; }
  .left-content, .center-content, .right-content {
    min-width: 0; min-height: 0; max-height: none; overflow: visible;
  }
  .left-content .section-box:first-child,
  .left-content .section-box:nth-child(2) {
    display: flex; flex-direction: column; min-height: 0; max-height: none;
    box-sizing: border-box;
  }
  .left-content .section-box:first-child { flex: 0.78; }
  .left-content .section-box:nth-child(2) { flex: 1.22; }
  .left-content .section-content { flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; }
  .sensor-data { display: flex; flex-direction: column; justify-content: space-evenly; flex: 1; min-height: 0; }
  .sensor-group:last-child { margin-bottom: 0; }
  .center-content .monitor-section { box-sizing: border-box; }
  .monitor-frame { flex: 1 1 auto; min-height: 0; aspect-ratio: auto; box-sizing: border-box; }
  .monitor-actions, .detection-stats-panel, .monitor-section > .section-header { flex-shrink: 0; }
  .right-content .section-box { height: auto; min-height: 0; margin: 0; box-sizing: border-box; }
  .vital-signs-wrapper.vertical { flex: 1; min-height: 0; }
  .vertical .vital-sign-box { display: flex; flex-direction: column; min-height: 0; box-sizing: border-box; margin: 0; }
  .vertical .vital-chart { flex: 1; min-height: 0; height: auto; }
}
@media (min-width: 1201px) and (max-height: 950px) {
  .left-content .section-box:first-child { flex: 0.65; }
  .left-content .section-box:nth-child(2) { flex: 1.35; }
  .left-content .section-box { padding: 14px; }
  .left-content .section-header { margin-bottom: 10px; }
  .left-content .section-content { padding: 10px; }
  .sensor-data { margin-top: 4px; }
  .sensor-group { margin-bottom: 5px; }
  .sensor-title { margin-bottom: 3px; }
  .sensor-grid { margin-top: 3px; }
  .sensor-item { padding: 5px; }
  .status-item { margin-bottom: 4px; padding: 4px 0; }
}
@media (max-width: 1200px) {
  .main-body { height: auto; min-height: 0; }
  .content-wrapper { height: auto; }
  .left-content, .center-content, .right-content { height: auto; min-height: 0; max-height: none; overflow: visible; }
  .left-content .section-box:first-child, .left-content .section-box:nth-child(2) { min-height: 0; max-height: none; }
  .right-content .section-box { height: auto; margin: 0; }
}

</style>
