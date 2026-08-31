"""
CLAUDE 智能门铃系统 - 辅助工具模块
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Tuple, Optional
import os


class ImageHelper:
    """图像处理辅助工具"""

    @staticmethod
    def resize_keep_aspect(image: np.ndarray, max_width: int,
                           max_height: int) -> np.ndarray:
        """
        保持宽高比缩放图像

        Args:
            image: 输入图像
            max_width: 最大宽度
            max_height: 最大高度

        Returns:
            缩放后的图像
        """
        height, width = image.shape[:2]

        # 计算缩放比例
        scale = min(max_width / width, max_height / height)

        if scale < 1.0:
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

        return image

    @staticmethod
    def pad_to_square(image: np.ndarray,
                      target_size: int = 112) -> np.ndarray:
        """
        填充图像为正方形

        Args:
            image: 输入图像
            target_size: 目标尺寸

        Returns:
            正方形图像
        """
        height, width = image.shape[:2]

        # 创建正方形画布
        square = np.zeros((target_size, target_size, 3), dtype=np.uint8)

        # 计算居中位置
        x_offset = (target_size - width) // 2
        y_offset = (target_size - height) // 2

        # 确保偏移量非负
        x_offset = max(0, x_offset)
        y_offset = max(0, y_offset)

        # 调整图像尺寸以适应
        if width != target_size or height != target_size:
            resized = cv2.resize(image, (min(width, target_size),
                                         min(height, target_size)))
            square[y_offset:y_offset + resized.shape[0],
                   x_offset:x_offset + resized.shape[1]] = resized
        else:
            square = image

        return square

    @staticmethod
    def adjust_brightness(image: np.ndarray,
                         alpha: float = 1.0,
                         beta: float = 0) -> np.ndarray:
        """
        调整图像亮度

        Args:
            image: 输入图像
            alpha: 对比度增益 (1.0 为不变)
            beta: 亮度偏移 (0 为不变)

        Returns:
            调整后的图像
        """
        return np.clip(image * alpha + beta, 0, 255).astype(np.uint8)

    @staticmethod
    def auto_adjust_brightness(image: np.ndarray) -> np.ndarray:
        """
        自动调整图像亮度（直方图均衡化）

        Args:
            image: 输入图像

        Returns:
            调整后的图像
        """
        if len(image.shape) == 3:
            # 转换到 YUV 空间
            yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
            # 对 Y 通道进行 CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            yuv[:, :, 0] = clahe.apply(yuv[:, :, 0])
            # 转回 BGR
            return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        else:
            # 灰度图像直接处理
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)

    @staticmethod
    def draw_info(image: np.ndarray, text: str,
                  position: Tuple[int, int] = (10, 30),
                  color: Tuple[int, int, int] = (0, 255, 0),
                  font_scale: float = 1.0,
                  thickness: int = 2) -> np.ndarray:
        """
        在图像上绘制信息文本

        Args:
            image: 输入图像
            text: 文本内容
            position: 文本位置
            color: 文本颜色 (BGR)
            font_scale: 字体大小
            thickness: 字体粗细

        Returns:
            绘制后的图像
        """
        result = image.copy()
        cv2.putText(result, text, position,
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        return result

    @staticmethod
    def overlay_status(image: np.ndarray, status: str,
                       name: str = None) -> np.ndarray:
        """
        叠加状态信息到图像

        Args:
            image: 输入图像
            status: 状态文本
            name: 姓名称

        Returns:
            叠加后的图像
        """
        result = image.copy()

        # 根据状态选择颜色
        if status == "match":
            color = (0, 255, 0)  # 绿色
            status_text = "欢迎回家"
        elif status == "unknown":
            color = (0, 165, 255)  # 橙色
            status_text = "未知人员"
        else:
            color = (0, 0, 255)  # 红色
            status_text = status

        # 绘制背景条
        bar_height = 50
        cv2.rectangle(result, (0, 0), (image.shape[1], bar_height),
                     (0, 0, 0), -1)

        # 绘制文本
        if name:
            cv2.putText(result, f"{name} - {status_text}", (10, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        else:
            cv2.putText(result, status_text, (10, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        return result


class TimeHelper:
    """时间辅助工具"""

    @staticmethod
    def now_str(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        获取当前时间的字符串

        Args:
            format: 时间格式

        Returns:
            时间字符串
        """
        return datetime.now().strftime(format)

    @staticmethod
    def timestamp_to_str(timestamp: float,
                        format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        时间戳转字符串

        Args:
            timestamp: 时间戳
            format: 时间格式

        Returns:
            时间字符串
        """
        return datetime.fromtimestamp(timestamp).strftime(format)

    @staticmethod
    def str_to_timestamp(time_str: str,
                        format: str = "%Y-%m-%d %H:%M:%S") -> float:
        """
        字符串转时间戳

        Args:
            time_str: 时间字符串
            format: 时间格式

        Returns:
            时间戳
        """
        return datetime.strptime(time_str, format).timestamp()

    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        格式化时长

        Args:
            seconds: 秒数

        Returns:
            格式化字符串，如 "1 小时 30 分钟"
        """
        if seconds < 60:
            return f"{seconds}秒"

        minutes = seconds // 60
        remaining_seconds = seconds % 60

        if minutes < 60:
            if remaining_seconds > 0:
                return f"{minutes}分钟{remaining_seconds}秒"
            return f"{minutes}分钟"

        hours = minutes // 60
        remaining_minutes = minutes % 60

        result = f"{hours}小时"
        if remaining_minutes > 0:
            result += f"{remaining_minutes}分钟"

        return result

    @staticmethod
    def is_today(dt: datetime) -> bool:
        """判断是否为今天"""
        return dt.date() == datetime.now().date()

    @staticmethod
    def is_yesterday(dt: datetime) -> bool:
        """判断是否为昨天"""
        yesterday = datetime.now().date() - __import__('datetime').timedelta(days=1)
        return dt.date() == yesterday


def generate_filename(prefix: str = "image",
                     extension: str = "jpg",
                     include_random: bool = True) -> str:
    """
    生成带时间戳的文件名

    Args:
        prefix: 文件名前缀
        extension: 文件扩展名
        include_random: 是否包含随机数

    Returns:
        文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if include_random:
        import random
        return f"{prefix}_{timestamp}_{random.randint(1000, 9999)}.{extension}"
    else:
        return f"{prefix}_{timestamp}.{extension}"


if __name__ == "__main__":
    # 测试代码
    print("辅助工具模块测试")
