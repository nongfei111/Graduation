#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸识别预览程序
显示摄像头实时画面，并进行人脸检测与识别
显示窗口可通过 VNC 查看

使用方法:
    python src/face_recognition/face_preview.py
"""

import sys
import os
import cv2
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.face_capture.camera import Camera
from src.face_recognition.recognizer import FaceRecognizer
from config.settings import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FacePreview')


class FacePreview:
    """人脸预览类"""

    def __init__(self):
        """初始化预览器"""
        self.camera = None
        self.recognizer = None
        self.running = False
        self.window_name = 'Smart Doorbell - Face Recognition'

    def initialize(self):
        """初始化摄像头和识别器"""
        print("=" * 50)
        print("CLAUDE 智能门铃 - 人脸识别预览")
        print("=" * 50)
        print("\n正在初始化...")

        # 初始化摄像头（优先使用 libcamera-still）
        print("1. 初始化摄像头...")
        try:
            self.camera = Camera(use_libcamera=True)
            print("   摄像头初始化成功 (libcamera-still)")
        except Exception as e:
            print(f"   libcamera-still 失败：{e}")
            try:
                self.camera = Camera(use_libcamera=False)
                print("   摄像头初始化成功 (备用模式)")
            except Exception as e2:
                print(f"   摄像头初始化失败：{e2}")
                return False

        # 初始化识别器
        print("2. 初始化人脸识别器...")
        try:
            self.recognizer = FaceRecognizer()
            print(f"   识别器初始化成功")
            print(f"   识别模式：{self.recognizer.mode}")
            print(f"   已注册成员：{self.recognizer.get_known_faces()}")
        except Exception as e:
            print(f"   识别器初始化失败：{e}")
            return False

        # 创建显示窗口
        print("3. 创建显示窗口...")
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        print("   窗口创建成功")
        print("\n" + "=" * 50)
        print("预览已启动！按 'q' 键退出")
        print("=" * 50)

        return True

    def draw_recognition_result(self, frame, faces, results):
        """在帧上绘制识别结果"""
        output = frame.copy()

        for i, (face, result) in enumerate(zip(faces, results)):
            x, y, w, h = face['box']

            if result.get('is_known', False):
                # 已知成员 - 绿色框
                color = (0, 255, 0)
                label = f"{result['name']}: {result['confidence']:.0%}"
            else:
                # 陌生人脸 - 红色框
                color = (0, 0, 255)
                label = "Unknown"

            # 绘制边界框
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # 绘制标签背景
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(output, (x, y - text_size[1] - 5),
                         (x + text_size[0], y), color, -1)

            # 绘制标签文字
            cv2.putText(output, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # 绘制状态栏
        h, w = output.shape[:2]
        cv2.rectangle(output, (0, 0), (w, 25), (0, 0, 0), -1)
        status_text = f"Faces: {len(faces)} | Members: {self.recognizer.get_known_faces()}"
        cv2.putText(output, status_text, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return output

    def run(self):
        """运行预览"""
        if not self.running:
            self.running = True

        while self.running:
            try:
                # 捕获帧
                frame = self.camera.capture()
                if frame is None:
                    continue

                # 人脸检测
                faces = self.recognizer.detect_faces(frame)

                # 人脸识别
                if len(faces) > 0:
                    results = self.recognizer.recognize_batch(frame, faces)
                    # 绘制识别结果
                    display_frame = self.draw_recognition_result(frame, faces, results)

                    # 打印识别信息
                    for result in results:
                        if result.get('is_known', False):
                            logger.info(f"识别到：{result['name']} ({result['confidence']:.0%})")
                        else:
                            logger.info("陌生人脸")
                else:
                    display_frame = frame

                # 显示画面
                cv2.imshow(self.window_name, display_frame)

                # 检查按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("用户请求退出")
                    break

            except KeyboardInterrupt:
                logger.info("收到中断信号")
                break
            except Exception as e:
                logger.error(f"预览错误：{e}")
                continue

        self.cleanup()

    def cleanup(self):
        """清理资源"""
        print("\n正在关闭...")
        self.running = False
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
        print("已关闭")


def main():
    """主函数"""
    preview = FacePreview()

    if preview.initialize():
        preview.run()
    else:
        print("\n初始化失败，退出")
        sys.exit(1)


if __name__ == "__main__":
    main()
