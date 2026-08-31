#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 faces 文件夹注册人脸照片
用法：python3 register_faces.py
"""

import sys
import os
import cv2

sys.path.insert(0, '/home/aaa/graduation')

from src.face_recognition.recognizer import FaceRecognizer
from config.settings import Config

def register_from_folder():
    """从 faces 文件夹注册所有照片"""

    faces_dir = '/home/aaa/graduation/faces'

    if not os.path.exists(faces_dir):
        print(f"文件夹不存在：{faces_dir}")
        return

    # 获取所有照片
    photos = [f for f in os.listdir(faces_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]

    if not photos:
        print("faces 文件夹中没有照片")
        return

    print(f"发现 {len(photos)} 张照片:")
    for photo in photos:
        print(f"  - {photo}")

    recognizer = FaceRecognizer()

    # 为每张照片创建一个成员（使用文件名作为姓名）
    for photo in photos:
        photo_path = os.path.join(faces_dir, photo)

        # 读取照片
        img = cv2.imread(photo_path)
        if img is None:
            print(f"无法读取照片：{photo}")
            continue

        # 使用文件名（不含扩展名）作为姓名
        name = os.path.splitext(photo)[0]

        # 注册人脸
        print(f"\n正在注册：{name} ...")
        if recognizer.add_face(name, img):
            print(f"  成功注册：{name}")
        else:
            print(f"  注册失败：{name}")

    print(f"\n注册完成！当前已知人脸：{recognizer.get_members()}")

if __name__ == "__main__":
    register_from_folder()
