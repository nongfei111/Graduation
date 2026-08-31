# 人脸识别模块
"""
负责轻量级人脸识别模型集成、特征提取与比对
"""

from .recognizer import FaceRecognizer
from .model_loader import ModelLoader

__all__ = ['FaceRecognizer', 'ModelLoader']
