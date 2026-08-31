"""
CLAUDE 智能门铃系统 - 人脸识别模块
使用 MobileFaceNet 轻量级识别模型
"""

import numpy as np
import cv2
import onnxruntime as ort
from typing import List, Tuple, Optional, Dict
import os
from scipy import spatial


class FaceRecognizer:
    """
    基于 MobileFaceNet 的人脸识别器
    轻量级模型，128 维特征向量，适合树莓派 5 部署
    """

    def __init__(self, model_path: str = "assets/models/mobilefacenet.onnx",
                 threshold: float = 0.6):
        """
        初始化人脸识别器

        Args:
            model_path: ONNX 模型路径
            threshold: 识别阈值（余弦相似度）
        """
        self.model_path = model_path
        self.threshold = threshold
        self.session = None
        self.input_size = (112, 112)  # MobileFaceNet 标准输入尺寸

        if os.path.exists(model_path):
            self._load_model()
        else:
            print(f"警告：模型文件不存在 {model_path}")
            print("请先下载 MobileFaceNet 模型文件")

    def _load_model(self):
        """加载 ONNX 模型"""
        try:
            providers = ['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            print(f"人脸识别模型加载成功：{self.model_path}")
        except Exception as e:
            print(f"加载模型失败：{e}")
            raise

    def extract_feature(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """
        提取人脸特征向量

        Args:
            face_image: 人脸图像（已裁剪）

        Returns:
            128 维特征向量，失败返回 None
        """
        if self.session is None:
            return None

        # 预处理
        resized = cv2.resize(face_image, self.input_size)

        # 归一化
        if len(resized.shape) == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)

        # 转换为 float32 并归一化到 [0, 1]
        input_image = resized.astype(np.float32) / 255.0

        # 标准化（MobileFaceNet 预处理）
        mean = np.array([0.5, 0.5, 0.5])
        std = np.array([0.5, 0.5, 0.5])
        input_image = (input_image - mean) / std

        # 转换为 NCHW 格式
        input_image = input_image.transpose(2, 0, 1)
        input_image = np.expand_dims(input_image, axis=0)

        # 推理
        outputs = self.session.run(None, {self.input_name: input_image})
        embedding = outputs[0].flatten()

        # L2 归一化
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    def compare(self, embedding1: np.ndarray, embedding2: np.ndarray) -> Tuple[float, bool]:
        """
        比较两个人脸特征向量

        Args:
            embedding1: 特征向量 1
            embedding2: 特征向量 2

        Returns:
            (相似度，是否匹配)
        """
        # 计算余弦相似度
        similarity = 1 - spatial.distance.cosine(embedding1, embedding2)

        # 判断是否匹配
        is_match = similarity >= self.threshold

        return similarity, is_match

    def recognize(self, face_image: np.ndarray,
                  known_embeddings: Dict[int, np.ndarray]) -> Tuple[Optional[int], float, str]:
        """
        识别人脸身份

        Args:
            face_image: 人脸图像
            known_embeddings: 已知人脸特征字典 {member_id: embedding}

        Returns:
            (member_id, confidence, status)
            status: "match" / "unknown" / "error"
        """
        # 提取特征
        embedding = self.extract_feature(face_image)

        if embedding is None:
            return None, 0.0, "error"

        best_id = None
        best_confidence = 0.0

        # 与已知人脸比对
        for member_id, known_emb in known_embeddings.items():
            similarity, is_match = self.compare(embedding, known_emb)

            if is_match and similarity > best_confidence:
                best_confidence = similarity
                best_id = member_id

        if best_id is not None:
            return best_id, best_confidence, "match"
        else:
            return None, best_confidence, "unknown"

    def verify(self, face_image: np.ndarray, known_embedding: np.ndarray) -> Tuple[float, bool]:
        """
        验证人脸是否为指定人员

        Args:
            face_image: 人脸图像
            known_embedding: 已知特征向量

        Returns:
            (相似度，是否匹配)
        """
        embedding = self.extract_feature(face_image)

        if embedding is None:
            return 0.0, False

        return self.compare(embedding, known_embedding)


class FaceRecognizerSimple:
    """
    简化版人脸识别器（使用 OpenCV 内置模型，无需额外下载）
    精度较低，但可用于开发测试
    """

    def __init__(self):
        """初始化简化版识别器"""
        # 使用 OpenCV 的 LBPH 识别器作为备选
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.is_trained = False

    def train(self, faces: List[np.ndarray], labels: List[int]):
        """训练识别器"""
        if len(faces) > 0 and len(faces) == len(labels):
            self.recognizer.train(faces, np.array(labels))
            self.is_trained = True

    def recognize(self, face_image: np.ndarray) -> Tuple[int, float]:
        """识别人脸"""
        if not self.is_trained:
            return -1, 0.0

        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        label, confidence = self.recognizer.predict(gray)
        return label, confidence


def download_models():
    """
    下载预训练模型
    模型下载地址（需要手动下载或运行此脚本）
    """
    import urllib.request

    models_dir = "assets/models"
    os.makedirs(models_dir, exist_ok=True)

    # UltraFace 模型
    ultraface_url = "https://github.com/HongBinZheng/UltraFace-Lite-NCNN/raw/master/model/UltraFace_models__version2_RFB-320.onnx"
    ultraface_path = os.path.join(models_dir, "ultraface.onnx")

    # MobileFaceNet 模型
    mobilefacenet_url = "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/mobile_face_net/model/mobile_face_net.onnx"
    mobilefacenet_path = os.path.join(models_dir, "mobilefacenet.onnx")

    print("正在下载模型文件...")
    print("如果下载失败，请手动下载模型到 assets/models/目录")

    try:
        print(f"下载 UltraFace 模型...")
        urllib.request.urlretrieve(ultraface_url, ultraface_path)
        print(f"UltraFace 模型已保存至 {ultraface_path}")
    except Exception as e:
        print(f"UltraFace 下载失败：{e}")

    try:
        print(f"下载 MobileFaceNet 模型...")
        urllib.request.urlretrieve(mobilefacenet_url, mobilefacenet_path)
        print(f"MobileFaceNet 模型已保存至 {mobilefacenet_path}")
    except Exception as e:
        print(f"MobileFaceNet 下载失败：{e}")


if __name__ == "__main__":
    # 测试模型下载
    download_models()
