"""
CLAUDE 智能门铃系统 - 摄像头控制模块
适配树莓派 5 官方摄像头 (CSI 接口)
"""

import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from datetime import datetime
import os
import time


class Camera:
    """树莓派 5 官方摄像头控制类"""

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30):
        """
        初始化摄像头

        Args:
            width: 图像宽度
            height: 图像高度
            fps: 帧率
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.picam2 = None
        self.is_running = False

    def initialize(self):
        """初始化摄像头设备"""
        try:
            self.picam2 = Picamera2()

            # 配置摄像头
            config = self.picam2.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": self.fps}
            )
            self.picam2.configure(config)
            self.picam2.start()
            self.is_running = True

            # 等待摄像头启动
            time.sleep(1)

            print("摄像头初始化成功")
            return True

        except Exception as e:
            print(f"摄像头初始化失败：{e}")
            return False

    def capture(self) -> np.ndarray:
        """
        捕获一帧图像

        Returns:
            numpy array: RGB 格式的图像
        """
        if not self.is_running:
            raise RuntimeError("摄像头未启动")

        try:
            # 捕获当前帧
            frame = self.picam2.capture_array()
            return frame

        except Exception as e:
            print(f"捕获图像失败：{e}")
            raise

    def capture_and_save(self, output_dir: str = "data/logs") -> str:
        """
        捕获图像并保存

        Args:
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        os.makedirs(output_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"visitor_{timestamp}.jpg"
        filepath = os.path.join(output_dir, filename)

        # 捕获并保存
        frame = self.capture()

        # 使用 PIL 保存高质量图像
        from PIL import Image
        img = Image.fromarray(frame)
        img.save(filepath, "JPEG", quality=95)

        return filepath

    def release(self):
        """释放摄像头资源"""
        if self.picam2 and self.is_running:
            self.picam2.stop()
            self.is_running = False
            print("摄像头已释放")

    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


class CameraSimulator:
    """
    摄像头模拟器（用于开发测试，无需真实摄像头）
    使用本地图片文件模拟摄像头输入
    """

    def __init__(self, image_dir: str = "assets/images"):
        """
        初始化模拟器

        Args:
            image_dir: 测试图片目录
        """
        self.image_dir = image_dir
        self.image_files = []
        self.current_index = 0
        self._load_images()

    def _load_images(self):
        """加载测试图片"""
        if os.path.exists(self.image_dir):
            self.image_files = [
                f for f in os.listdir(self.image_dir)
                if f.endswith(('.jpg', '.jpeg', '.png'))
            ]
        print(f"模拟器加载了 {len(self.image_files)} 张测试图片")

    def initialize(self) -> bool:
        """初始化模拟器"""
        return True

    def capture(self) -> np.ndarray:
        """捕获模拟图像"""
        if not self.image_files:
            # 返回空白图像
            return np.zeros((720, 1280, 3), dtype=np.uint8)

        # 循环读取图片
        image_path = os.path.join(self.image_dir, self.image_files[self.current_index])
        self.current_index = (self.current_index + 1) % len(self.image_files)

        from PIL import Image
        img = Image.open(image_path)
        img = img.convert('RGB')
        return np.array(img)

    def release(self):
        """释放资源（无操作）"""
        pass
