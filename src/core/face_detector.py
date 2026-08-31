"""
CLAUDE 智能门铃系统 - 人脸检测模块
使用 UltraFace 轻量级人脸检测模型
"""

import numpy as np
import cv2
import onnxruntime as ort
from typing import List, Tuple, Optional
import os


class FaceDetector:
    """
    基于 UltraFace 的人脸检测器
    轻量级模型，适合树莓派 5 部署
    """

    def __init__(self, model_path: str = "assets/models/ultraface.onnx",
                 confidence_threshold: float = 0.7,
                 input_size: Tuple[int, int] = (320, 240)):
        """
        初始化人脸检测器

        Args:
            model_path: ONNX 模型路径
            confidence_threshold: 置信度阈值
            input_size: 模型输入尺寸 (宽，高)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.input_size = input_size
        self.session = None

        if os.path.exists(model_path):
            self._load_model()
        else:
            print(f"警告：模型文件不存在 {model_path}")
            print("请先下载 UltraFace 模型文件")

    def _load_model(self):
        """加载 ONNX 模型"""
        try:
            # 使用 CPU 执行提供者（树莓派 5）
            providers = ['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, providers=providers)

            # 获取模型输入输出信息
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [self.session.get_outputs()[i].name
                                for i in range(len(self.session.get_outputs()))]

            print(f"人脸检测模型加载成功：{self.model_path}")

        except Exception as e:
            print(f"加载模型失败：{e}")
            raise

    def detect(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[float]]:
        """
        检测图像中的人脸

        Args:
            image: 输入图像 (BGR 或 RGB 格式)

        Returns:
            (boxes, scores): 人脸框列表和置信度列表
        """
        if self.session is None:
            return [], []

        # 保存原始尺寸
        original_height, original_width = image.shape[:2]

        # 预处理
        resized = cv2.resize(image, self.input_size)
        input_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        input_image = input_image.transpose(2, 0, 1).astype(np.float32)
        input_image = np.expand_dims(input_image, axis=0)
        input_image /= 255.0

        # 推理
        outputs = self.session.run(
            self.output_names,
            {self.input_name: input_image}
        )

        # 解析输出
        boxes, scores = self._parse_outputs(outputs, original_width, original_height)

        return boxes, scores

    def _parse_outputs(self, outputs: List[np.ndarray],
                       img_width: int, img_height: int) -> Tuple[List[np.ndarray], List[float]]:
        """
        解析模型输出

        Args:
            outputs: 模型原始输出
            img_width: 原始图像宽度
            img_height: 原始图像高度

        Returns:
            (boxes, scores): 人脸框和置信度
        """
        boxes = []
        scores = []

        # UltraFace 输出格式解析
        # 不同版本可能有所不同，这里以常见版本为例
        if len(outputs) >= 2:
            boxes_data = outputs[0][0]  # 边界框
            scores_data = outputs[1][0]  # 置信度

            for i in range(len(boxes_data)):
                score = scores_data[i][1] if len(scores_data[i]) > 1 else scores_data[i]

                if score >= self.confidence_threshold:
                    box = boxes_data[i][:4]
                    # 转换为原始图像坐标
                    box = box * [img_width, img_height, img_width, img_height]
                    # 转换为 [x1, y1, x2, y2] 格式
                    x1, y1, w, h = box
                    box = np.array([x1, y1, x1 + w, y1 + h])
                    boxes.append(box)
                    scores.append(float(score))

        return boxes, scores

    def detect_and_crop(self, image: np.ndarray) -> List[Tuple[np.ndarray, float]]:
        """
        检测人脸并裁剪

        Args:
            image: 输入图像

        Returns:
            [(人脸图像，置信度), ...]
        """
        boxes, scores = self.detect(image)
        cropped_faces = []

        for box, score in zip(boxes, scores):
            x1, y1, x2, y2 = box.astype(int)

            # 边界检查
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)

            # 裁剪人脸
            face = image[y1:y2, x1:x2]
            if face.size > 0:
                cropped_faces.append((face, score))

        return cropped_faces

    @staticmethod
    def draw_boxes(image: np.ndarray, boxes: List[np.ndarray],
                   scores: List[float] = None) -> np.ndarray:
        """
        在图像上绘制人脸框

        Args:
            image: 原始图像
            boxes: 人脸框列表
            scores: 置信度列表（可选）

        Returns:
            绘制后的图像
        """
        result = image.copy()

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box.astype(int)

            # 绘制矩形框
            color = (0, 255, 0)  # 绿色
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

            # 绘制置信度
            if scores:
                label = f"{scores[i]:.2f}"
                cv2.putText(result, label, (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return result


class FaceDetectorOpenCV:
    """
    基于 OpenCV 的 Haar 级联人脸检测器（备用方案）
    无需深度学习模型，但精度较低
    """

    def __init__(self, confidence_threshold: float = 0.5):
        """初始化 OpenCV 人脸检测器"""
        self.confidence_threshold = confidence_threshold

        # 加载 Haar 级联分类器
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.classifier = cv2.CascadeClassifier(cascade_path)

    def detect(self, image: np.ndarray) -> Tuple[List[np.ndarray], List[float]]:
        """检测人脸"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        faces = self.classifier.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        boxes = []
        scores = []

        for (x, y, w, h) in faces:
            box = np.array([x, y, x + w, y + h])
            boxes.append(box)
            scores.append(0.8)  # Haar 检测器不提供置信度

        return boxes, scores

    def detect_and_crop(self, image: np.ndarray) -> List[Tuple[np.ndarray, float]]:
        """检测并裁剪人脸"""
        boxes, scores = self.detect(image)
        cropped_faces = []

        for box, score in zip(boxes, scores):
            x1, y1, x2, y2 = box.astype(int)
            face = image[y1:y2, x1:x2]
            if face.size > 0:
                cropped_faces.append((face, score))

        return cropped_faces
