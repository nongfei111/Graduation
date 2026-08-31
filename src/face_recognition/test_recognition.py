#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸识别测试脚本

使用方法:
    python src/face_recognition/test_recognition.py
"""

import sys
import os
import cv2

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.face_capture.camera import Camera
from src.face_recognition.recognizer import FaceRecognizer
from config.settings import FaceRecognitionConfig


def test_face_recognition():
    """测试人脸识别功能"""
    print("\n=== CLAUDE 智能门铃 - 人脸识别测试 ===\n")

    # 初始化识别器
    print("正在加载人脸识别模型...")
    recognizer = FaceRecognizer()

    # 显示已注册成员
    members = recognizer.get_members()
    if members:
        print(f"\n已注册家庭成员：{members}")
    else:
        print("\n警告：没有已注册的家庭成员！")
        print("请先运行：python src/face_capture/collect_faces.py --member <姓名> --count 50")
        return

    print(f"\n识别阈值：{recognizer.threshold}")
    print("\n按 q 退出测试\n")

    # 打开摄像头进行实时识别测试
    with Camera() as camera:
        while True:
            frame = camera.capture()
            if frame is None:
                continue

            # 检测人脸
            faces = recognizer.detect_faces(frame)

            # 识别每个人脸
            for face in faces:
                result = recognizer.recognize(frame, face)

                # 绘制边界框
                x, y, w, h = face['box']
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # 显示识别结果
                if result['is_known']:
                    label = f"{result['name']}: {result['confidence']:.2f}"
                    color = (0, 255, 0)  # 绿色
                else:
                    label = "Unknown"
                    color = (0, 0, 255)  # 红色

                cv2.putText(frame, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # 显示结果
            cv2.imshow('Face Recognition Test', frame)

            # 检查退出键
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    print("\n测试结束")


if __name__ == "__main__":
    test_face_recognition()
