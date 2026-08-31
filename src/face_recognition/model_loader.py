#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型加载器
负责加载和管理深度学习模型
"""

import os
import logging
import urllib.request
from config.settings import FaceRecognitionConfig, Config

logger = logging.getLogger(__name__)


class ModelLoader:
    """模型加载类"""

    def __init__(self):
        self.model_dir = Config.MODEL_DATA_DIR
        os.makedirs(self.model_dir, exist_ok=True)

    def download_model(self, url, save_path):
        """下载模型文件"""
        if os.path.exists(save_path):
            logger.info(f"模型已存在：{save_path}")
            return

        logger.info(f"正在下载模型：{url}")
        try:
            urllib.request.urlretrieve(url, save_path)
            logger.info(f"模型下载完成：{save_path}")
        except Exception as e:
            logger.error(f"模型下载失败：{e}")
            raise

    def load_facenet(self, model_path=None):
        """
        加载 FaceNet 模型

        Returns:
            tf.keras.Model 或 None
        """
        model_path = model_path or FaceRecognitionConfig.FACENET_MODEL_PATH

        if not os.path.exists(model_path):
            logger.warning(f"FaceNet 模型不存在：{model_path}")
            logger.info("请从以下地址下载模型:")
            logger.info("https://github.com/nyoki-mtl/keras-facenet")
            return None

        try:
            import tensorflow as tf
            model = tf.keras.models.load_model(model_path)
            logger.info("FaceNet 模型加载成功")
            return model
        except Exception as e:
            logger.error(f"加载 FaceNet 模型失败：{e}")
            return None

    def load_dlib_model(self):
        """
        加载 dlib 模型

        Returns:
            dlib 模型对象或 None
        """
        try:
            import dlib
            # dlib 会自动管理模型路径
            logger.info("dlib 模型加载成功")
            return dlib
        except ImportError:
            logger.error("dlib 未安装")
            return None

    def get_available_models(self):
        """获取可用的模型列表"""
        available = []

        # 检查 dlib
        try:
            import dlib
            available.append('dlib')
        except ImportError:
            pass

        # 检查 face_recognition
        try:
            import face_recognition
            available.append('face_recognition')
        except ImportError:
            pass

        # 检查 TensorFlow
        try:
            import tensorflow as tf
            available.append('tensorflow')
        except ImportError:
            pass

        # 检查 OpenCV DNN
        import cv2
        if hasattr(cv2, 'dnn'):
            available.append('opencv_dnn')

        return available
