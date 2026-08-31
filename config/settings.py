# 系统配置
import os

class Config:
    """系统基础配置"""
    # 硬件配置
    CAMERA_ID = 0  # 摄像头设备 ID，USB 摄像头通常为 0，树莓派摄像头可能需要调整
    CAMERA_WIDTH = 1280
    CAMERA_HEIGHT = 720
    FPS = 30

    # 显示屏配置
    DISPLAY_WIDTH = 800
    DISPLAY_HEIGHT = 480

    # GPIO 引脚配置 (树莓派)
    BUZZER_PIN = 17
    DOOR_LOCK_PIN = 27
    BUTTON_PIN = 22

    # 人脸检测配置
    FACE_DETECTION_THRESHOLD = 0.5
    FACE_RECOGNITION_THRESHOLD = 0.6

    # 预警配置
    UNKNOWN_VISITOR_WARNING_TIME = 30  # 陌生访客停留超过 30 秒触发预警
    WARNING_INTERVAL = 5  # 预警间隔 (秒)

    # 数据存储路径
    DATA_DIR = "data"
    FACE_DATA_DIR = "data/faces"
    VISITOR_DATA_DIR = "data/visitors"
    MODEL_DATA_DIR = "data/models"

    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/doorbell.log"


class FaceRecognitionConfig:
    """人脸识别模型配置"""
    # 模型选择：'facenet', 'arcface', 'dlib'
    MODEL_TYPE = "facenet"

    # FaceNet 配置
    FACENET_INPUT_SIZE = (160, 160)
    FACENET_MODEL_PATH = "data/models/facenet.h5"

    # 特征向量维度
    EMBEDDING_SIZE = 128

    # 比对距离阈值 (欧氏距离)
    # dlib/face_recognition 模式：0.8
    # OpenCV Haar 备用模式：0.35 (更严格，减少误识别)
    DISTANCE_THRESHOLD = 0.35

    # 备用模式阈值（OpenCV Haar + LBP）
    # 0.5 是平衡识别率和拒绝率的折中值
    HAAR_DISTANCE_THRESHOLD = 0.5


class DatabaseConfig:
    """数据库配置"""
    FAMILY_MEMBERS_DB = "data/family_members.json"
    VISITORS_DB = "data/visitors.json"
    ACCESS_LOGS_DB = "data/access_logs.json"


class NetworkConfig:
    """网络同步配置"""
    # 服务器地址（默认阿里云，本地测试可修改）
    SERVER_HOST = os.environ.get("SERVER_HOST", "192.168.1.100")
    SERVER_PORT = int(os.environ.get("SERVER_PORT", 5000))

    # 同步间隔 (秒)
    SYNC_INTERVAL = 60

    # API 端点
    API_UPLOAD_VISITOR = "/api/device/upload/visitor"
    API_DOWNLOAD_LOGS = "/api/visitor/list"
    API_HEARTBEAT = "/api/device/heartbeat"
    API_LOGIN = "/api/auth/login"

    # 心跳配置
    HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
    COMMAND_POLL_INTERVAL = 5  # 命令轮询间隔（秒）

    # 设备配置
    DEVICE_TYPE = "raspberry_pi_4b"
    FIRMWARE_VERSION = "1.0.0"
