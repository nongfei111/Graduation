#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸采集器
负责人脸检测、图像预处理、人脸数据集构建
"""

import cv2
import numpy as np
import os
import logging
from datetime import datetime
from config.settings import Config

logger = logging.getLogger(__name__)


class FaceCollector:
    """人脸采集类"""

    def __init__(self, face_cascade_path=None):
        """
        初始化人脸采集器

        Args:
            face_cascade_path: Haar 级联分类器路径，默认使用 OpenCV 内置模型
        """
        # 加载人脸检测模型
        if face_cascade_path:
            self.face_cascade = cv2.CascadeClassifier(face_cascade_path)
        else:
            # 使用 OpenCV 内置的 Haar 级联分类器
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

        # 也可以使用 HOG + Dlib 或 MTCNN（在 recognizer 中实现）
        logger.info("FaceCollector 初始化完成")

    def detect_faces(self, image, min_size=(50, 50), scale_factor=1.1, min_neighbors=5):
        """
        检测图像中的人脸

        Args:
            image: BGR 图像 (numpy.ndarray)
            min_size: 最小人脸尺寸
            scale_factor: 图像缩放比例
            min_neighbors: 最少邻居数

        Returns:
            list: 人脸边界框列表 [(x, y, w, h), ...]
        """
        if image is None:
            return []

        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 人脸检测
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=min_size
        )

        face_boxes = [(x, y, w, h) for (x, y, w, h) in faces]
        logger.debug(f"检测到 {len(face_boxes)} 张人脸")

        return face_boxes

    def extract_face(self, image, face_box, padding=10):
        """
        从图像中提取人脸区域

        Args:
            image: BGR 图像
            face_box: 人脸边界框 (x, y, w, h)
            padding: 边距

        Returns:
            numpy.ndarray: 人脸图像，失败返回 None
        """
        x, y, w, h = face_box
        h_img, w_img = image.shape[:2]

        # 添加边距并确保不越界
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w_img, x + w + padding)
        y2 = min(h_img, y + h + padding)

        face_img = image[y1:y2, x1:x2]

        if face_img.size == 0:
            return None

        return face_img

    def preprocess_face(self, face_img, target_size=(160, 160)):
        """
        人脸图像预处理

        Args:
            face_img: 人脸图像
            target_size: 目标尺寸

        Returns:
            numpy.ndarray: 预处理后的人脸图像
        """
        if face_img is None:
            return None

        # 1. 调整尺寸
        resized = cv2.resize(face_img, target_size)

        # 2. 直方图均衡化 (可选，提升光照鲁棒性)
        if len(resized.shape) == 3:
            # 彩色图像 - 转换到 YUV 后对 Y 通道均衡化
            yuv = cv2.cvtColor(resized, cv2.COLOR_BGR2YUV)
            yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
            processed = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        else:
            # 灰度图像
            processed = cv2.equalizeHist(resized)

        # 3. 去噪
        processed = cv2.GaussianBlur(processed, (3, 3), 0)

        return processed

    def collect_faces_for_member(self, camera, member_name, count=50, save_dir=None):
        """
        为指定成员采集人脸数据集

        Args:
            camera: Camera 实例
            member_name: 成员名称
            count: 采集数量
            save_dir: 保存目录

        Returns:
            list: 保存的人脸图像路径
        """
        if save_dir is None:
            save_dir = os.path.join(Config.FACE_DATA_DIR, member_name)

        # 创建保存目录
        os.makedirs(save_dir, exist_ok=True)

        saved_paths = []
        captured_count = 0
        last_face = None

        logger.info(f"开始为 {member_name} 采集人脸，目标数量：{count}")
        print(f"\n=== 正在为 {member_name} 采集人脸数据 ===")
        print(f"请面对摄像头，缓慢转动头部以采集不同角度")
        print(f"已采集：0/{count}\n")

        import time
        start_time = time.time()

        while captured_count < count:
            # 捕获帧
            frame = camera.capture()
            if frame is None:
                continue

            # 检测人脸
            faces = self.detect_faces(frame)

            if len(faces) == 0:
                continue

            if len(faces) > 1:
                print("检测到多张人脸，请确保只有一人在画面中")
                continue

            # 提取并保存人脸
            face_box = faces[0]
            face_img = self.extract_face(frame, face_box)

            if face_img is None:
                continue

            # 检查与上一张的相似度，避免重复
            if last_face is not None:
                similarity = self._calculate_similarity(last_face, face_img)
                if similarity > 0.95:  # 太相似则跳过
                    continue

            # 保存人脸
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = os.path.join(save_dir, f"{member_name}_{timestamp}.jpg")
            cv2.imwrite(save_path, face_img)
            saved_paths.append(save_path)
            captured_count += 1

            last_face = face_img

            # 进度显示
            print(f"\r已采集：{captured_count}/{count}", end="")

            # 短暂延迟
            time.sleep(0.3)

        elapsed = time.time() - start_time
        logger.info(f"完成采集，共 {captured_count} 张，耗时 {elapsed:.1f}秒")
        print(f"\n\n采集完成！共保存 {captured_count} 张人脸图像到：{save_dir}")

        return saved_paths

    def _calculate_similarity(self, img1, img2):
        """计算两张图像的简单相似度"""
        img1_resized = cv2.resize(img1, (50, 50))
        img2_resized = cv2.resize(img2, (50, 50))

        img1_gray = cv2.cvtColor(img1_resized, cv2.COLOR_BGR2GRAY) if len(img1_resized.shape) == 3 else img1_resized
        img2_gray = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2GRAY) if len(img2_resized.shape) == 3 else img2_resized

        # 归一化后计算相关性
        img1_norm = img1_gray.astype(float) / 255.0
        img2_norm = img2_gray.astype(float) / 255.0

        correlation = np.corrcoef(img1_norm.flatten(), img2_norm.flatten())[0, 1]
        return max(0, correlation)  # 确保非负

    def augment_faces(self, face_dir, augmentation_factor=5):
        """
        对人脸数据集进行数据增强

        Args:
            face_dir: 人脸数据集目录
            augmentation_factor: 增强倍数

        Returns:
            list: 增强后的图像保存路径
        """
        augmented_paths = []

        # 获取所有人脸图像
        face_images = []
        for filename in os.listdir(face_dir):
            if filename.endswith(('.jpg', '.png', '.jpeg')):
                path = os.path.join(face_dir, filename)
                img = cv2.imread(path)
                if img is not None:
                    face_images.append((path, img))

        logger.info(f"找到 {len(face_images)} 张人脸图像进行增强")

        for path, img in face_images:
            # 1. 水平翻转
            flipped = cv2.flip(img, 1)
            flip_path = path.replace('.jpg', '_flip.jpg')
            cv2.imwrite(flip_path, flipped)
            augmented_paths.append(flip_path)

            # 2. 亮度调整
            for i, alpha in enumerate([0.8, 1.2]):
                adjusted = cv2.convertScaleAbs(img, alpha=alpha, beta=0)
                adj_path = path.replace('.jpg', f'_bright{i}.jpg')
                cv2.imwrite(adj_path, adjusted)
                augmented_paths.append(adj_path)

            # 3. 轻微旋转
            h, w = img.shape[:2]
            for angle in [-10, 10]:
                M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                rotated = cv2.warpAffine(img, M, (w, h))
                rot_path = path.replace('.jpg', f'_rot{angle}.jpg')
                cv2.imwrite(rot_path, rotated)
                augmented_paths.append(rot_path)

        logger.info(f"数据增强完成，共生成 {len(augmented_paths)} 张增强图像")
        return augmented_paths
