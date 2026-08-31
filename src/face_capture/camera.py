#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头控制模块
负责摄像头初始化、图像捕获、释放资源
支持 Picamera2、libcamera-still 和 OpenCV

功能定位索引（设备端采集层）：
- 主循环取帧入口：main.py -> Camera.capture_raw() / Camera.preview_from_raw()
- 识别/取证使用：capture_raw() 返回原始 BGR 帧（用于识别、抓拍、活体）
- 屏幕显示使用：preview_from_raw() 将 raw_frame 转成预览帧（只用于显示，避免污染识别链路）

工程约定：
- 优先使用 Picamera2 默认配置（贴近 rpicam-hello 默认效果）
- 异常情况下回退：libcamera-still -> OpenCV VideoCapture
"""

import cv2
import logging
import subprocess
import tempfile
import os
import numpy as np
from config.settings import Config

logger = logging.getLogger(__name__)


class Camera:
    """摄像头控制类"""

    def __init__(self, camera_id=None, width=None, height=None, fps=None, use_libcamera=False):
        """
        初始化摄像头

        Args:
            camera_id: 摄像头 ID，默认为配置文件中的值
            width: 图像宽度
            height: 图像高度
            fps: 帧率
            use_libcamera: 是否使用 libcamera-still 命令
        """
        self.camera_id = camera_id if camera_id is not None else Config.CAMERA_ID
        self.width = width or Config.CAMERA_WIDTH
        self.height = height or Config.CAMERA_HEIGHT
        self.fps = fps or Config.FPS
        self.use_libcamera = use_libcamera

        self.cap = None
        self.picam = None
        self._initialized = False
        self.temp_file = None

        self._initialize()

    def _enhance_frame_for_preview(self, frame):
        """使用摄像头默认画面，不再做额外预览增强。"""
        return frame

    def _initialize(self):
        """初始化摄像头设备"""
        # 方法 1: 使用 libcamera-still 命令
        if self.use_libcamera:
            try:
                # 测试 libcamera-still 是否可用
                result = subprocess.run(
                    ['libcamera-still', '-t', '1', '-o', '/dev/null'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.use_libcamera = True
                    logger.info(f"libcamera-still 可用：{self.width}x{self.height}")
                    self._initialized = True
                    return
            except Exception as e:
                logger.warning(f"libcamera-still 不可用：{e}")
                self.use_libcamera = False

        # 方法 2: 使用 Picamera2
        try:
            from picamera2 import Picamera2

            self.picam = Picamera2()
            # 完全使用 Picamera2 默认 preview 配置，尽量贴近 rpicam-hello 默认画面。
            config = self.picam.create_preview_configuration()
            self.picam.configure(config)
            self.picam.start()

            import time
            time.sleep(1.0)  # 给自动曝光/白平衡一点收敛时间

            logger.info("Picamera2 初始化成功（默认 preview 配置）")
            self._initialized = True
            return

        except Exception as e:
            logger.warning(f"Picamera2 失败：{e}")

        # 方法 3: 使用 OpenCV
        try:
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                raise RuntimeError(f"无法打开摄像头 {self.camera_id}")

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            logger.info(f"OpenCV 摄像头初始化成功：{self.width}x{self.height}")
            self._initialized = True

        except Exception as e:
            logger.error(f"所有摄像头初始化方法都失败：{e}")
            raise RuntimeError(f"无法初始化摄像头：{e}")

    def _capture_raw_frame(self):
        """捕获原始 BGR 帧，不做预览增强。"""
        if not self._initialized:
            logger.error("摄像头未初始化")
            return None

        # 方法 1: libcamera-still
        if self.use_libcamera:
            try:
                self.temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                temp_path = self.temp_file.name
                self.temp_file.close()

                result = subprocess.run(
                    ['libcamera-still', '-t', '100', '-o', temp_path,
                     '--width', str(self.width), '--height', str(self.height)],
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0 and os.path.exists(temp_path):
                    frame = cv2.imread(temp_path)
                    os.unlink(temp_path)
                    return frame
            except Exception as e:
                logger.error(f"libcamera-still 捕获失败：{e}")

        # 方法 2: Picamera2
        if self.picam is not None:
            try:
                frame = self.picam.capture_array("main")
                if frame is None:
                    return None
                # 默认 preview 配置下，常见返回可能是 4 通道或 RGB/BGR 三通道。
                if len(frame.shape) == 3 and frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                elif len(frame.shape) == 3 and frame.shape[2] == 3:
                    # 默认配置通常已可直接用于显示；这里只做最小兼容处理。
                    frame = np.ascontiguousarray(frame)
                return frame
            except Exception as e:
                logger.error(f"Picamera2 捕获失败：{e}")

        # 方法 3: OpenCV
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                return frame

        return None

    def capture_raw(self):
        """
        捕获一帧原始图像。

        Returns:
            numpy.ndarray: BGR 格式的原始图像帧，失败返回 None
        """
        return self._capture_raw_frame()

    def capture_preview(self):
        """
        捕获一帧用于预览的图像。

        Returns:
            numpy.ndarray: 预览增强后的 BGR 图像帧，失败返回 None
        """
        frame = self._capture_raw_frame()
        return self.preview_from_raw(frame)

    def preview_from_raw(self, frame):
        """基于原始帧生成预览帧，避免识别链路复用增强结果。"""
        if frame is None:
            return None
        return self._enhance_frame_for_preview(frame.copy())

    def capture(self):
        """
        兼容旧调用，默认返回预览帧。

        Returns:
            numpy.ndarray: BGR 格式的预览图像帧，失败返回 None
        """
        return self.capture_preview()

    def release(self):
        """释放摄像头资源"""
        if self.picam is not None:
            try:
                self.picam.stop()
                self.picam.close()
                logger.info("Picamera2 已释放")
            except Exception as e:
                logger.error(f"释放 Picamera2 失败：{e}")
            self.picam = None

        if self.cap is not None:
            self.cap.release()
            logger.info("OpenCV 摄像头已释放")

        if self.temp_file and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

        self._initialized = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
