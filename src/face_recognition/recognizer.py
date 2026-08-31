#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸识别器
负责加载模型、提取特征、人脸比对与识别
支持 face_recognition 库和 OpenCV 备用方案

功能定位索引（设备端识别核心）：
- 人脸检测：detect_faces()
  - 优先使用 face_recognition.face_locations(model='hog')（缩放后检测再映射回原图）
  - 依赖缺失时回退 Haar 级联
- 特征提取：_get_embedding()
  - face_recognition.face_encodings() 生成 128 维向量（dlib 模式）
  - 备用：OpenCV 灰度分块统计生成 128 维向量（仅兜底）
- 身份比对：recognize()
  - 欧氏距离最小者为候选，distance < threshold 判定为已知成员
- 成员库加载：_load_known_faces() / _rebuild_face_database()
  - 人脸库目录：data/faces/<成员名>/*.jpg
  - 缓存文件：data/models/faces_cache.pkl（启动优先加载，损坏则删除重建）

调用位置：
- main.py 主循环：detect_faces() -> recognize()
"""

import os
import pickle
import numpy as np
import logging
import cv2
from datetime import datetime
from config.settings import FaceRecognitionConfig, Config

logger = logging.getLogger(__name__)


class FaceRecognizer:
    """人脸识别类"""

    def __init__(self, model_path=None, known_faces_dir=None):
        """
        初始化人脸识别器

        Args:
            model_path: 模型文件路径
            known_faces_dir: 已知人脸数据目录
        """
        self.model_path = model_path or FaceRecognitionConfig.FACENET_MODEL_PATH
        self.known_faces_dir = known_faces_dir or Config.FACE_DATA_DIR

        # 根据模式设置阈值
        self.mode = None
        self.has_face_recognition = False
        self._load_model()  # 先确定模式

        # dlib 模式使用欧氏距离，阈值越大越宽松。
        # 0.6 是 face_recognition 的常见经验值，比 0.5 更适合当前现场环境。
        if self.has_face_recognition:
            self.threshold = 0.6
        else:
            self.threshold = getattr(FaceRecognitionConfig, 'HAAR_DISTANCE_THRESHOLD', 0.35)

        self.known_faces = {}  # {name: [embeddings]}

        self._load_known_faces()
        self.initialized = True

    def _load_model(self):
        """加载人脸识别模型"""
        try:
            # 尝试使用 face_recognition 库 (基于 dlib)
            import face_recognition
            self.has_face_recognition = True
            self.mode = 'dlib'
            logger.info("使用 dlib 人脸识别模型")
        except ImportError:
            # 使用 OpenCV 备用方案
            self.has_face_recognition = False
            self.mode = 'haar'
            logger.info("face_recognition 未安装，使用 OpenCV Haar 级联 + 备用编码方案")

        self.initialized = True

    def _load_known_faces(self):
        """加载已知人脸特征"""
        if not os.path.exists(self.known_faces_dir):
            logger.warning(f"人脸数据目录不存在：{self.known_faces_dir}")
            return

        # 尝试加载缓存的特征文件
        cache_file = os.path.join(Config.MODEL_DATA_DIR, 'faces_cache.pkl')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    self.known_faces = pickle.load(f)
                    logger.info(f"从缓存加载 {len(self.known_faces)} 个人脸特征")
                    return
            except Exception as e:
                logger.error(f"加载缓存失败：{e}")
                try:
                    os.remove(cache_file)
                    logger.warning(f"已删除损坏缓存：{cache_file}")
                except Exception as remove_err:
                    logger.warning(f"删除损坏缓存失败：{remove_err}")

        # 从原始图像重建特征
        self._rebuild_face_database()

    def reload_known_faces(self, force_rebuild: bool = False):
        cache_file = os.path.join(Config.MODEL_DATA_DIR, 'faces_cache.pkl')
        if force_rebuild:
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except Exception:
                pass
            self._rebuild_face_database()
        else:
            self._load_known_faces()

    def _rebuild_face_database(self):
        """从人脸图像重建特征数据库"""
        self.known_faces = {}

        if not os.path.exists(self.known_faces_dir):
            return

        for member_name in os.listdir(self.known_faces_dir):
            member_dir = os.path.join(self.known_faces_dir, member_name)
            if not os.path.isdir(member_dir):
                continue
            # 黑名单/可疑人员样本不应进入家庭成员识别库。
            if member_name.strip().lower() in {"suspicious_persons", "blacklist", "blacklist_faces"}:
                logger.info(f"跳过非家庭成员目录：{member_name}")
                continue

            embeddings = []
            for filename in os.listdir(member_dir):
                if filename.endswith(('.jpg', '.png', '.jpeg')):
                    img_path = os.path.join(member_dir, filename)
                    img = cv2.imread(img_path)
                    if img is not None:
                        embedding = self._get_embedding(img)
                        if embedding is not None:
                            embeddings.append(embedding)

            if embeddings:
                self.known_faces[member_name] = embeddings
                logger.info(f"加载 {member_name} 的 {len(embeddings)} 个特征")

        # 保存缓存
        os.makedirs(Config.MODEL_DATA_DIR, exist_ok=True)
        cache_file = os.path.join(Config.MODEL_DATA_DIR, 'faces_cache.pkl')
        if self.known_faces:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.known_faces, f)
            logger.info(f"人脸特征缓存已保存到 {cache_file}")

    def _get_embedding(self, face_img):
        """
        获取人脸特征向量

        Args:
            face_img: RGB 或 BGR 人脸图像

        Returns:
            numpy.ndarray: 128 维特征向量，失败返回 None
        """
        if face_img is None:
            return None

        try:
            if self.has_face_recognition:
                import face_recognition
                # 使用 face_recognition 库
                if len(face_img.shape) == 3:
                    rgb_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                else:
                    rgb_img = face_img

                embeddings = face_recognition.face_encodings(rgb_img)
                if len(embeddings) > 0:
                    return embeddings[0]
                return None
            else:
                # 使用 OpenCV 备用编码方案 (LBPH + 特征降维)
                return self._encode_with_opencv(face_img)

        except Exception as e:
            logger.error(f"获取特征失败：{e}")
            return None

    def _encode_with_opencv(self, face_img):
        """
        使用 OpenCV 进行人脸特征编码（备用方案）

        使用 LBP 特征 + 分块统计，生成 128 维特征向量
        """
        # 转换为灰度图
        if len(face_img.shape) == 3:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_img

        # 调整到固定尺寸
        resized = cv2.resize(gray, (128, 128))

        # 归一化
        normalized = resized.astype(np.float32) / 255.0

        # 提取分块特征
        block_size = 16
        features = []

        for i in range(0, 128, block_size):
            for j in range(0, 128, block_size):
                block = normalized[i:i+block_size, j:j+block_size]
                # 使用均值和标准差作为特征
                features.append(np.mean(block))
                features.append(np.std(block))

        # 转换为 128 维向量
        encoding = np.array(features[:128], dtype=np.float32)

        # 归一化
        norm = np.linalg.norm(encoding)
        if norm > 0:
            encoding = encoding / norm

        return encoding

    def detect_faces(self, image, min_face_size=50):
        """
        检测图像中的人脸

        Args:
            image: BGR 图像
            min_face_size: 最小人脸尺寸（像素），过滤小尺寸误检

        Returns:
            list: 人脸信息列表 [{'box': (x,y,w,h), 'image': crop}, ...]
        """
        if image is None:
            return []

        faces = []

        if self.has_face_recognition:
            import face_recognition

            # 转换为 RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 检测人脸位置
            scale = 0.5
            if rgb.shape[0] >= 720 or rgb.shape[1] >= 720:
                small = cv2.resize(rgb, (0, 0), fx=scale, fy=scale)
            else:
                small = rgb
                scale = 1.0

            locations = face_recognition.face_locations(small, model='hog')

            for (top, right, bottom, left) in locations:
                if scale != 1.0:
                    top = int(top / scale)
                    right = int(right / scale)
                    bottom = int(bottom / scale)
                    left = int(left / scale)

                w = right - left
                h = bottom - top
                if w < min_face_size or h < min_face_size:
                    continue
                face_crop = image[top:bottom, left:right]

                faces.append({
                    'box': (left, top, w, h),
                    'image': face_crop
                })
        else:
            # 使用 Haar 级联检测器
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            if not cascade.empty():
                # 提高 minNeighbors 减少误检，增加 minSize 过滤小区域
                face_rects = cascade.detectMultiScale(
                    gray, scaleFactor=1.2, minNeighbors=8, minSize=(min_face_size, min_face_size)
                )

                # 额外过滤：人脸宽高比接近 1:1
                filtered_rects = []
                for (x, y, w, h) in face_rects:
                    aspect_ratio = w / float(h)
                    # 人脸宽高比通常在 0.8-1.2 之间
                    if 0.7 <= aspect_ratio <= 1.3:
                        filtered_rects.append((x, y, w, h))

                # 非极大值抑制：去除重叠的检测框
                if len(filtered_rects) > 1:
                    filtered_rects = self._non_maxima_suppression(filtered_rects)

                for (x, y, w, h) in filtered_rects:
                    face_crop = image[y:y+h, x:x+w]
                    faces.append({
                        'box': (x, y, w, h),
                        'image': face_crop
                    })

        logger.debug(f"检测到 {len(faces)} 张人脸")
        return faces

    def _non_maxima_suppression(self, boxes, overlap_thresh=0.3):
        """
        非极大值抑制，去除重叠的检测框

        Args:
            boxes: 检测框列表 [(x,y,w,h), ...]
            overlap_thresh: 重叠阈值

        Returns:
            list: 筛选后的检测框
        """
        if len(boxes) <= 1:
            return boxes

        # 按面积排序
        boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        keep = [boxes[0]]

        for box in boxes[1:]:
            # 检查与已保留框的重叠
            overlap_with_all = False
            for kept in keep:
                # 计算 IoU
                x1 = max(box[0], kept[0])
                y1 = max(box[1], kept[1])
                x2 = min(box[0] + box[2], kept[0] + kept[2])
                y2 = min(box[1] + box[3], kept[1] + kept[3])

                if x2 > x1 and y2 > y1:
                    inter_area = (x2 - x1) * (y2 - y1)
                    box_area = box[2] * box[3]
                    kept_area = kept[2] * kept[3]
                    iou = inter_area / float(box_area + kept_area - inter_area)
                    if iou > overlap_thresh:
                        overlap_with_all = True
                        break

            if not overlap_with_all:
                keep.append(box)

        return keep

        logger.debug(f"检测到 {len(faces)} 张人脸")
        return faces

    def recognize(self, image, face_info):
        """
        识别单张人脸

        Args:
            image: 原始 BGR 图像
            face_info: 人脸信息 {'box': ..., 'image': ...}

        Returns:
            dict: {'is_known': bool, 'name': str, 'confidence': float, 'distance': float}
        """
        result = {
            'is_known': False,
            'name': 'Unknown',
            'confidence': 0.0,
            'distance': float('inf')
        }

        face_img = face_info.get('image')
        if face_img is None:
            return result

        # 获取当前人脸特征
        try:
            h, w = face_img.shape[:2]
            max_dim = max(h, w)
            if max_dim > 320:
                ratio = 320.0 / float(max_dim)
                face_img = cv2.resize(face_img, (int(w * ratio), int(h * ratio)))
        except Exception:
            pass

        current_embedding = self._get_embedding(face_img)
        if current_embedding is None:
            return result

        # 与已知人脸比对
        min_distance = float('inf')
        best_match = None

        for name, embeddings in self.known_faces.items():
            for known_embedding in embeddings:
                distance = np.linalg.norm(current_embedding - known_embedding)
                if distance < min_distance:
                    min_distance = distance
                    best_match = name

        result['distance'] = min_distance

        # 判断是否为已知人脸
        if min_distance < self.threshold:
            result['is_known'] = True
            result['name'] = best_match
            result['confidence'] = max(0, 1 - min_distance / self.threshold)
            logger.info(f"识别结果：{best_match} (距离：{min_distance:.3f}, 置信度：{result['confidence']:.2f})")
        else:
            logger.info(f"陌生人脸 (距离：{min_distance:.3f} > 阈值 {self.threshold})")

        return result

    def recognize_batch(self, image, faces):
        """批量识别多张人脸"""
        return [self.recognize(image, face) for face in faces]

    def add_face(self, name, face_img):
        """添加新人脸到数据库"""
        embedding = self._get_embedding(face_img)
        if embedding is None:
            return False

        if name not in self.known_faces:
            self.known_faces[name] = []

        self.known_faces[name].append(embedding)

        # 更新缓存
        cache_file = os.path.join(Config.MODEL_DATA_DIR, 'faces_cache.pkl')
        os.makedirs(Config.MODEL_DATA_DIR, exist_ok=True)
        with open(cache_file, 'wb') as f:
            pickle.dump(self.known_faces, f)

        logger.info(f"添加人脸：{name}")
        return True

    def remove_face(self, name):
        """移除指定成员的所有人脸数据"""
        if name in self.known_faces:
            del self.known_faces[name]
            cache_file = os.path.join(Config.MODEL_DATA_DIR, 'faces_cache.pkl')
            with open(cache_file, 'wb') as f:
                pickle.dump(self.known_faces, f)
            logger.info(f"移除成员：{name}")
            return True
        return False

    def get_members(self):
        """获取所有已注册的成员名单"""
        return list(self.known_faces.keys())

    def get_known_faces(self):
        """获取已知人脸列表"""
        return list(self.known_faces.keys())

    def refresh_database(self):
        """刷新人脸数据库"""
        self._rebuild_face_database()
