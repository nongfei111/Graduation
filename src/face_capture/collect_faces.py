#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸采集脚本
用于采集家庭成员人脸数据集

使用方法:
    python src/face_capture/collect_faces.py --member <姓名> --count <数量>
"""

import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.face_capture.camera import Camera
from src.face_capture.face_collector import FaceCollector
from config.settings import Config


def main():
    parser = argparse.ArgumentParser(description='采集家庭成员人脸数据集')
    parser.add_argument('--member', type=str, required=True, help='成员姓名')
    parser.add_argument('--count', type=int, default=50, help='采集数量')
    parser.add_argument('--augment', action='store_true', help='是否进行数据增强')
    args = parser.parse_args()

    print(f"\n=== CLAUDE 智能门铃 - 人脸采集系统 ===\n")

    # 初始化摄像头
    with Camera() as camera:
        # 初始化采集器
        collector = FaceCollector()

        # 采集人脸
        collector.collect_faces_for_member(
            camera=camera,
            member_name=args.member,
            count=args.count
        )

        # 数据增强
        if args.augment:
            face_dir = os.path.join(Config.FACE_DATA_DIR, args.member)
            collector.augment_faces(face_dir, augmentation_factor=5)
            print(f"\n数据增强完成!")


if __name__ == "__main__":
    main()
