#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
触摸屏显示模块
负责 UI 界面显示、欢迎消息、识别结果展示
"""

import os
import cv2
import numpy as np
import logging
from config.settings import Config

logger = logging.getLogger(__name__)


class Display:
    """显示控制类"""

    def __init__(self, width=None, height=None):
        """
        初始化显示器

        Args:
            width: 显示宽度
            height: 显示高度
        """
        self.width = width or Config.DISPLAY_WIDTH
        self.height = height or Config.DISPLAY_HEIGHT

        self.window_name = 'Smart Doorbell'
        self.show_ui = bool(os.environ.get('DISPLAY'))

        if self.show_ui:
            try:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, self.width, self.height)
            except Exception:
                self.show_ui = False

        logger.info(f"Display 初始化：{self.width}x{self.height}")

    def show_frame(self, frame: np.ndarray, overlay_text: str = None):
        """
        显示帧图像

        Args:
            frame: BGR 图像
            overlay_text: 叠加文字
        """
        if frame is None:
            return

        display_frame = frame.copy()

        # 添加文字叠加
        if overlay_text:
            self._draw_text(display_frame, overlay_text)

        if self.show_ui:
            cv2.imshow(self.window_name, display_frame)
            cv2.waitKey(1)

    def _draw_text(self, image: np.ndarray, text: str,
                   position: tuple = (10, 30),
                   font_scale: float = 0.7,
                   color: tuple = (0, 255, 0),
                   thickness: int = 2):
        """在图像上绘制文字"""
        cv2.putText(image, text, position,
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

    def show_welcome(self):
        """显示欢迎界面"""
        welcome_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        welcome_frame[:] = (50, 50, 100)  # 深蓝色背景

        # 绘制欢迎文字
        text = "Smart Doorbell System"
        self._draw_centered_text(welcome_frame, text, (self.height // 2 - 50),
                                 font_scale=1.5, color=(255, 255, 255))

        subtext = "智能门铃系统 - 已启动"
        self._draw_centered_text(welcome_frame, subtext, (self.height // 2 + 20),
                                 font_scale=0.8, color=(200, 200, 200))

        if self.show_ui:
            cv2.imshow(self.window_name, welcome_frame)
            cv2.waitKey(1000)

        logger.info("欢迎界面已显示")

    def _draw_centered_text(self, image: np.ndarray, text: str, y: int,
                            font_scale: float = 1.0, color: tuple = (255, 255, 255),
                            thickness: int = 2):
        """在图像中心绘制文字"""
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

        x = (image.shape[1] - text_width) // 2
        cv2.putText(image, text, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

    def show_idle(self):
        """显示空闲状态"""
        # 在角落显示状态
        pass  # 实时画面已在主循环中显示

    def show_welcome_message(self, name: str):
        """
        显示欢迎消息

        Args:
            name: 欢迎对象姓名
        """
        logger.info(f"显示欢迎消息：{name}")
        # 欢迎消息会叠加在主画面上

    def show_unknown_visitor(self):
        """显示陌生访客提示"""
        logger.info("显示陌生访客提示")
        # 提示会叠加在主画面上

    def show_warning(self, text: str, duration: float = 3.0):
        logger.warning(str(text))
        if not self.show_ui:
            return
        try:
            warning_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            warning_frame[:] = (0, 0, 120)
            self._draw_centered_text(warning_frame, str(text), (self.height // 2),
                                     font_scale=1.0, color=(255, 255, 255))
            cv2.imshow(self.window_name, warning_frame)
            cv2.waitKey(int(max(0.0, float(duration)) * 1000))
        except Exception:
            pass

    def draw_recognition_result(self, frame: np.ndarray, results: list):
        """
        在帧上绘制识别结果

        Args:
            frame: 原始帧
            results: 识别结果列表

        Returns:
            绘制后的帧
        """
        output = frame.copy()

        for result in results:
            x, y, w, h = result.get('box', (0, 0, 0, 0))

            if result.get('is_known', False):
                color = (0, 255, 0)  # 绿色 - 已知成员
                label = f"{result['name']}: {result['confidence']:.1%}"
            else:
                color = (0, 0, 255)  # 红色 - 陌生访客
                label = "Unknown"

            # 绘制边界框
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 4)

            # 绘制标签背景
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 3)
            cv2.rectangle(output, (x, y - label_h - 8), (x + label_w + 4, y), color, -1)

            # 绘制标签
            cv2.putText(output, label, (x + 2, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3)

        return output

    def draw_status_bar(self, frame: np.ndarray, status: dict):
        """
        绘制状态栏

        Args:
            frame: 帧
            status: 状态信息
        """
        h, w = frame.shape[:2]

        # 绘制状态栏背景
        cv2.rectangle(frame, (0, 0), (w, 30), (0, 0, 0), -1)

        # 显示状态
        status_text = f"系统状态：运行中 | 时间：{status.get('time', '')}"
        cv2.putText(frame, status_text, (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def cleanup(self):
        """清理显示资源"""
        if self.show_ui:
            cv2.destroyAllWindows()
            logger.info("显示窗口已关闭")


if __name__ == "__main__":
    # 测试显示
    display = Display()
    display.show_welcome()

    # 创建测试帧
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # 测试绘制
    test_results = [
        {'box': (100, 100, 100, 100), 'is_known': True, 'name': 'Test', 'confidence': 0.95},
        {'box': (300, 200, 100, 100), 'is_known': False, 'name': 'Unknown', 'confidence': 0}
    ]

    result_frame = display.draw_recognition_result(test_frame, test_results)

    print("显示模块测试完成")
