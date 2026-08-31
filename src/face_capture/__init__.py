# 人脸采集模块
"""
负责摄像头调用、人脸检测、图像采集与预处理
"""

from .camera import Camera
from .face_collector import FaceCollector

__all__ = ['Camera', 'FaceCollector']
