#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLAUDE 智能门铃系统 - 主程序
基于嵌入式平台的智能门铃系统，集成人脸识别、访客登记、异常预警功能
"""

import sys
import signal
import logging
import os
import time
import base64
import hashlib
import threading
from collections import deque
from datetime import datetime
from typing import Dict

# 添加项目根目录到路径（保证可直接导入 config/src 等本地模块）
sys.path.insert(0, '.')

# 配置与业务模块导入
from config.settings import Config, FaceRecognitionConfig
from src.face_capture.camera import Camera
from src.face_recognition.recognizer import FaceRecognizer#人脸识别
from src.visitor_management.manager import VisitorManager#访客记录
from src.interaction.display import Display#屏幕显示
from src.interaction.alert import AlertSystem#蜂鸣器
from src.sync.data_sync import DataSync#同步
from gpio_control import DoorbellController#硬件控制
from src.sync.cloud_communication import CloudCommunication#云端通信
from src.sync.remote_control import RemoteController#远程命令
from src.security.blacklist_manager import BlacklistManager
from src.security import lockdown
import cv2


class SmartDoorbell:
    """智能门铃主控制器"""

    def __init__(self):
        """初始化系统各模块"""
        self.logger = self._setup_logging()
        self.running = False

        # 初始化各模块
        self.logger.info("正在初始化系统各模块...")
        try:
            # 优先尝试非 libcamera 模式（兼容部分环境）
            self.camera = Camera(use_libcamera=False)
        except Exception:
            # 回退到 libcamera 模式
            self.camera = Camera(use_libcamera=True)
        self.recognizer = FaceRecognizer()
        self.visitor_manager = VisitorManager()
        self.display = Display()
        self.alert_system = AlertSystem()
        self.data_sync = DataSync()
        self.doorbell_controller = DoorbellController()  # 蜂鸣器和步进电机

        # 云端能力/远程能力（根据环境变量开关动态启用）
        self.cloud_comm = None
        self.remote_controller = None
        self.blacklist = None
        self._last_blacklist_sync = 0.0
        self._last_unlock_ts = 0.0
        self._last_unlock_name = None

        # 上传节流（避免同一张脸/同一事件高频上报）
        self._recent_face_upload_ts = {}
        self._same_face_upload_throttle_sec = 10.0
        self._global_upload_throttle_sec = 1.0
        self._last_any_visitor_upload_ts = 0.0

        # 识别节流（降低 CPU 压力，避免每帧都跑识别）
        self._recognition_interval_sec = float(os.environ.get('RECOGNITION_INTERVAL_SEC') or 3.0)
        self._last_recognition_ts = 0.0
        self._frame_idx = 0
        self._latest_frame = None
        self.mqtt_client = None

        # 摄像头容错状态
        self._last_frame_ok_ts = 0.0
        self._none_frame_streak = 0

        # 帧缓冲：用于活体多帧采样/本地反照片检测等
        self._frame_buffer = deque(maxlen=12)
        self._face_crop_buffer = deque(maxlen=12)

        # 活体检测总开关与参数（通过环境变量可快速调参）
        self._liveness_enabled = str(os.environ.get('LIVENESS_ENABLED', '1')).strip() not in ('0', 'false', 'False')
        self._liveness_frame_count = int(os.environ.get('LIVENESS_FRAME_COUNT') or 5)
        self._liveness_min_frames = int(os.environ.get('LIVENESS_MIN_FRAMES') or min(3, self._liveness_frame_count))
        self._liveness_capture_interval_sec = float(os.environ.get('LIVENESS_CAPTURE_INTERVAL_SEC') or 0.25)
        self._liveness_score_threshold = float(os.environ.get('LIVENESS_SCORE_THRESHOLD') or 0.45)
        self._liveness_retry_count = int(os.environ.get('LIVENESS_RETRY_COUNT') or 2)
        self._liveness_retry_gap_sec = float(os.environ.get('LIVENESS_RETRY_GAP_SEC') or 0.6)
        self._liveness_pass_score_strict = float(os.environ.get('LIVENESS_PASS_SCORE_STRICT') or 0.65)
        self._liveness_fail_open = str(os.environ.get('LIVENESS_FAIL_OPEN', '0')).strip() in ('1', 'true', 'True')
        self._local_antispoof_enabled = str(os.environ.get('LOCAL_ANTISPOOF_ENABLED', '1')).strip() not in ('0', 'false', 'False')

        # 黑名单/云同步/远程功能开关
        self._blacklist_enabled = str(os.environ.get('BLACKLIST_ENABLED', '0')).strip() in ('1', 'true', 'True')
        self._cloud_sync_enabled = str(os.environ.get('CLOUD_SYNC_ENABLED', '1')).strip() in ('1', 'true', 'True')
        self._cloud_features_enabled = str(os.environ.get('CLOUD_FEATURES_ENABLED', '0')).strip() in ('1', 'true', 'True')
        self._last_liveness_beep_ts = 0.0
        self._last_liveness_encode_log_ts = 0.0
        self._last_stranger_seen_ts = 0.0

        # 初始化云端能力：成员同步、远程开锁/抓拍、MQTT 命令通道、黑名单同步等
        if self._cloud_sync_enabled:
            self._init_cloud_features(enable_remote=self._cloud_features_enabled)
        else:
            self.logger.info("云端同步与远程功能已停用")

        # 注册退出处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("系统初始化完成")

    def _init_cloud_features(self, enable_remote: bool = False):
        try:
            # 云端地址与设备身份信息优先从环境变量读取，缺省再回落到 config.settings 的 NetworkConfig
            host = os.environ.get('SERVER_HOST') or getattr(__import__('config.settings', fromlist=['NetworkConfig']).NetworkConfig, 'SERVER_HOST')
            port = int(os.environ.get('SERVER_PORT') or getattr(__import__('config.settings', fromlist=['NetworkConfig']).NetworkConfig, 'SERVER_PORT'))
            device_id = os.environ.get('DEVICE_ID')
            username = os.environ.get('DEVICE_USERNAME')
            password = os.environ.get('DEVICE_PASSWORD')
            device_token = os.environ.get('DEVICE_TOKEN')

            self.cloud_comm = CloudCommunication(
                cloud_host=host,
                cloud_port=port,
                device_id=device_id,
                device_token=device_token
            )

            heartbeat_interval = int(os.environ.get('HEARTBEAT_INTERVAL') or 2)
            self.logger.info(f"云端同步已启用，心跳间隔配置：{heartbeat_interval}s")

            # 设备端登录/注册：如果没有 token 但提供了账号密码，则先登录拿 token，再注册设备
            if not device_token and username and password:
                if self.cloud_comm.login(username, password):
                    self.cloud_comm.register_device(device_name=os.environ.get('DEVICE_NAME', '智能门铃'))

            # 给同步调度器注入云通信与识别器：用于成员同步、人脸库更新等
            self.data_sync.cloud_comm = self.cloud_comm
            self.data_sync.recognizer = self.recognizer

            if not enable_remote:
                self.logger.info("远程控制功能已停用，仅保留成员同步")
                return

            # 远程控制适配：RemoteController 期望一个带 unlock/trigger_alarm 的 gpio_controller，这里做一层适配封装
            class _GpioAdapter:
                def __init__(self, ctrl):
                    self.ctrl = ctrl
                def unlock(self, duration: float = 3.0):
                    if lockdown.is_locked():
                        raise RuntimeError('lockdown enabled')
                    self.ctrl.motor.unlock()
                def trigger_alarm(self, duration: float = 5.0):
                    self.ctrl.trigger_alarm(duration)

            # 云端后台任务（心跳/拉命令等）
            if getattr(self.cloud_comm, 'device_token', None):
                self.cloud_comm.start_background_tasks(heartbeat_interval=heartbeat_interval)

            # 启动远程命令执行器：负责处理 unlock/snapshot 等命令，并在设备端执行后回传云端
            self.remote_controller = RemoteController(
                cloud_comm=self.cloud_comm,
                gpio_controller=_GpioAdapter(self.doorbell_controller),
                display=self.display,
                audio_player=None,
                frame_provider=lambda: self._latest_frame
            )
            self.remote_controller.start()

            try:
                from src.sync.mqtt_commands import MqttCommandClient
                device_id_for_mqtt = getattr(self.cloud_comm, 'device_id', None) if self.cloud_comm else None
                if device_id_for_mqtt:
                    # MQTT 通道：比心跳轮询更快，作为远程命令的实时通道
                    self.mqtt_client = MqttCommandClient(device_id_for_mqtt)
                    self.mqtt_client.set_on_command(self.remote_controller._on_cloud_command)
                    self.mqtt_client.start(blocking=False)
                    self.logger.info("MQTT 远程命令通道已启动")
            except Exception as e:
                self.logger.warning(f"MQTT 远程命令通道启动失败：{e}")

            if self._blacklist_enabled:
                # 黑名单：支持从云端同步黑名单人脸特征，并对检测到的人脸做匹配
                self.blacklist = BlacklistManager(self.recognizer, self.cloud_comm, threshold=0.35)
                self.logger.info("黑名单功能已启用")
            else:
                self.logger.info("黑名单功能已停用")
        except Exception as e:
            self.logger.warning(f"云端能力初始化失败：{e}")

    def _setup_logging(self):
        """配置日志系统"""
        try:
            log_dir = os.path.dirname(Config.LOG_FILE)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass
        logging.basicConfig(
            level=getattr(logging, Config.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(Config.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('SmartDoorbell')

    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        self.logger.info("收到退出信号，正在关闭系统...")
        self.running = False

    def _ui_warning(self, text: str, duration: float = 3.0):
        # 尝试用屏幕提示警告（如果 display 实现了 show_warning），否则退化为日志警告
        fn = getattr(self.display, 'show_warning', None)
        if callable(fn):
            try:
                fn(text, duration=duration)
                return
            except Exception:
                pass
        self.logger.warning(str(text))

    def _face_fingerprint(self, face_bgr):
        # 生成“人脸图片指纹”，用于陌生人上报节流：同一张脸短时间内避免重复上传
        if face_bgr is None:
            return None
        try:
            gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY) if len(face_bgr.shape) == 3 else face_bgr
            small = cv2.resize(gray, (16, 16))
            small = cv2.GaussianBlur(small, (3, 3), 0)
            norm = cv2.equalizeHist(small)
            avg = float(norm.mean())
            ahash = (norm > avg).astype('uint8')
            return hashlib.sha256(ahash.tobytes()).hexdigest()[:16]
        except Exception:
            return None

    def _should_upload_face(self, key: str, interval_sec: float) -> bool:
        # 全局节流 + 单 key 节流，避免高频网络请求与重复记录
        now = time.time()
        if now - self._last_any_visitor_upload_ts < float(self._global_upload_throttle_sec):
            return False
        last = self._recent_face_upload_ts.get(key)
        if last is not None and now - float(last) < float(interval_sec):
            return False
        self._recent_face_upload_ts[key] = now
        self._last_any_visitor_upload_ts = now
        if len(self._recent_face_upload_ts) > 512:
            cutoff = now - 120.0
            self._recent_face_upload_ts = {k: v for k, v in self._recent_face_upload_ts.items() if v >= cutoff}
        return True

    def _collect_liveness_frames(self, face_box, face_crop_bgr=None) -> list:
        # 从帧缓冲中收集活体检测所需的多帧图片（base64），优先按 face_box 裁剪
        try:
            import cv2
        except Exception:
            return []

        def _encode(bgr):
            try:
                if bgr is None or getattr(bgr, 'size', 0) == 0:
                    return None
                img = cv2.resize(bgr, (224, 224))
                for ext, params in (
                    ('.jpg', [int(cv2.IMWRITE_JPEG_QUALITY), 80]),
                    ('.png', []),
                ):
                    ok, buf = cv2.imencode(ext, img, params)
                    if ok:
                        return base64.b64encode(buf.tobytes()).decode('utf-8')
                return None
            except Exception as e:
                now = time.time()
                if now - float(self._last_liveness_encode_log_ts) >= 2.0:
                    self._last_liveness_encode_log_ts = now
                    try:
                        shape = getattr(bgr, 'shape', None)
                        dtype = getattr(bgr, 'dtype', None)
                        self.logger.warning(f"活体帧编码异常：shape={shape} dtype={dtype} err={e}")
                    except Exception:
                        pass
                return None

        # 如果没有 face_box，则退化为使用 face_crop_buffer 作为输入
        if not face_box:
            out = []
            crops = list(self._face_crop_buffer)[-max(0, self._liveness_frame_count):]
            if face_crop_bgr is not None:
                crops = (crops + [face_crop_bgr])[-max(0, self._liveness_frame_count):]
            for c in crops:
                s = _encode(c)
                if s:
                    out.append(s)
            if len(out) == 1:
                out.append(out[0])
            return out
        try:
            x, y, w, h = face_box
            x = int(x); y = int(y); w = int(w); h = int(h)
        except Exception:
            return []


        frames = list(self._frame_buffer)[-max(0, self._liveness_frame_count):]
        if self._latest_frame is not None:
            frames = (frames + [self._latest_frame])[-max(0, self._liveness_frame_count):]

        out = []
        for fr in frames:
            if fr is None:
                continue
            try:
                H, W = fr.shape[:2]
                pad = int(max(w, h) * 0.25)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(W, x + w + pad)
                y2 = min(H, y + h + pad)
                crop = fr[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                crop = cv2.resize(crop, (224, 224))
                ok, buf = cv2.imencode('.jpg', crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue
                out.append(base64.b64encode(buf.tobytes()).decode('utf-8'))
            except Exception:
                continue
        if len(out) >= 2:
            return out

        # 如果帧缓冲裁剪不足，再退回使用 face_crop_buffer
        crops = list(self._face_crop_buffer)[-max(0, self._liveness_frame_count):]
        if face_crop_bgr is not None:
            crops = (crops + [face_crop_bgr])[-max(0, self._liveness_frame_count):]
        for c in crops:
            s = _encode(c)
            if s:
                out.append(s)
        if len(out) == 1:
            out.append(out[0])
        return out

    def _local_anti_spoof(self, face_crops_bgr: list) -> Dict:
        # 设备端本地反照片启发式：以两帧差异 + 相位相关对齐后的残差，估计“平面攻击”可能性
        try:
            import numpy as np
        except Exception as e:
            return {'ok': False, 'live': True, 'score': 0.0, 'reason': f'local unavailable: {e}'}

        try:
            import cv2
        except Exception as e:
            return {'ok': False, 'live': True, 'score': 0.0, 'reason': f'local unavailable: {e}'}

        crops = []
        for c in (face_crops_bgr or []):
            if c is None or getattr(c, 'size', 0) == 0:
                continue
            crops.append(c)

        if len(crops) < 2:
            return {'ok': False, 'live': True, 'score': 0.0, 'reason': 'local: crops too few'}

        def _prep(bgr):
            g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if len(bgr.shape) == 3 else bgr
            g = cv2.resize(g, (160, 160))
            g = cv2.GaussianBlur(g, (3, 3), 0)
            return g

        a = _prep(crops[-2])
        b = _prep(crops[-1])
        a32 = np.float32(a)
        b32 = np.float32(b)

        raw = float(np.mean(np.abs(a32 - b32)))
        if raw < 0.8:
            return {
                'ok': True,
                'live': True,
                'score': 0.0,
                'suspicious': True,
                'reason': f'local: motion too small (raw={raw:.2f})'
            }
        try:
            (dx, dy), _ = cv2.phaseCorrelate(a32, b32)
            M = np.float32([[1.0, 0.0, dx], [0.0, 1.0, dy]])
            b_aligned = cv2.warpAffine(
                b32,
                M,
                (b32.shape[1], b32.shape[0]),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_REPLICATE
            )
            residual = float(np.mean(np.abs(a32 - b_aligned)))
        except Exception:
            residual = raw

        ratio = float(residual / (raw + 1e-6))

        strong_spoof = (raw >= 2.0 and residual < 1.2 and ratio < 0.15)
        live = not bool(strong_spoof)
        score = max(0.0, min(1.0, residual / 6.0))
        reason = f"local(raw={raw:.2f}, residual={residual:.2f}, ratio={ratio:.2f})"
        return {
            'ok': True,
            'live': live,
            'score': score,
            'suspicious': not live,
            'reason': reason
        }

    def _collect_liveness_frames_burst(self, face_box, count: int) -> list:
        # 主动抓取多帧用于活体：直接调用 camera.capture_raw，覆盖更长时间窗口
        if not face_box:
            return []
        try:
            x, y, w, h = face_box
            x = int(x); y = int(y); w = int(w); h = int(h)
        except Exception:
            return []

        out = []
        for _ in range(max(0, int(count))):
            try:
                fr = self.camera.capture_raw()
            except Exception:
                fr = None
            if fr is None:
                time.sleep(float(self._liveness_capture_interval_sec))
                continue
            try:
                H, W = fr.shape[:2]
                pad = int(max(w, h) * 0.25)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(W, x + w + pad)
                y2 = min(H, y + h + pad)
                crop = fr[y1:y2, x1:x2]
                if crop is None or crop.size == 0:
                    time.sleep(float(self._liveness_capture_interval_sec))
                    continue
                crop = cv2.resize(crop, (224, 224))
                ok, buf = cv2.imencode('.jpg', crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    out.append(base64.b64encode(buf.tobytes()).decode('utf-8'))
            except Exception:
                pass
            time.sleep(float(self._liveness_capture_interval_sec))

        if len(out) == 1:
            out.append(out[0])
        return out

    def _check_liveness(self, member_name: str, face_box, face_crop_bgr=None) -> bool:
        # 活体检测总入口：本地反照片检测（可选） + 云端 AI 复核（可选） + 二次尝试投票
        if not self._liveness_enabled or not self.cloud_comm:
            return True

        if self._local_antispoof_enabled:
            # 使用最近 2-3 帧 face crop 做本地启发式判定
            local_crops = list(self._face_crop_buffer)[-3:]
            if face_crop_bgr is not None and getattr(face_crop_bgr, 'size', 0) > 0:
                local_crops = (local_crops + [face_crop_bgr])[-3:]
            local = self._local_anti_spoof(local_crops)
            if local.get('ok'):
                self.logger.info(
                    f"本地反照片检测：live={bool(local.get('live'))} score={float(local.get('score') or 0.0):.2f} "
                    f"reason={local.get('reason')}"
                )
                if bool(local.get('suspicious')):
                    self.logger.info(f"本地反照片检测标记可疑，继续交给云端复核：reason={local.get('reason')}")
                if not bool(local.get('live')) and 'motion too small' not in str(local.get('reason') or ''):
                    self.logger.info("活体检测结果：live=False score=1.00 provider=local reason=local anti-spoof")
                    return False

        def _collect_attempt() -> list:
            # 每次尝试优先 burst 主动抓拍，其次用缓冲区兜底
            frames = self._collect_liveness_frames_burst(face_box, count=int(self._liveness_frame_count))
            if len(frames) < int(self._liveness_min_frames):
                frames = self._collect_liveness_frames(face_box, face_crop_bgr=face_crop_bgr)
            return frames

        def _summarize(frames: list) -> str:
            try:
                uniq = len(set(frames))
            except Exception:
                uniq = 0
            return f"frames={len(frames)}/{int(self._liveness_frame_count)} unique={uniq}"

        def _call(frames: list, attempt: int) -> Dict:
            if len(frames) < int(self._liveness_min_frames):
                self.logger.warning(
                    f"活体检测帧不足：attempt={attempt} frames={len(frames)} "
                    f"need={int(self._liveness_min_frames)} buffer={len(self._frame_buffer)} face_crops={len(self._face_crop_buffer)}"
                )
                return {'ok': False, 'reason': 'frames too few'}
            res = self.cloud_comm.check_liveness(frames, member_name=member_name)
            if not res.get('ok'):
                self.logger.warning(f"活体检测失败：attempt={attempt} reason={res.get('reason')}")
            return res

        def _accept(res: Dict) -> bool:
            live = bool(res.get('live'))
            score = float(res.get('score') or 0.0)
            return live and score >= float(self._liveness_score_threshold)

        def _accept_strict(res: Dict) -> bool:
            live = bool(res.get('live'))
            score = float(res.get('score') or 0.0)
            return live and score >= float(self._liveness_pass_score_strict)

        tries = max(1, int(self._liveness_retry_count))
        results = []

        for i in range(tries):
            attempt = i + 1
            if i > 0:
                time.sleep(float(self._liveness_retry_gap_sec))

            frames_b64 = _collect_attempt()
            self.logger.info(f"活体检测取帧：attempt={attempt} {_summarize(frames_b64)}")

            res = _call(frames_b64, attempt=attempt)
            if not res.get('ok'):
                results.append(res)
                if self._liveness_fail_open:
                    return True
                continue

            live = bool(res.get('live'))
            score = float(res.get('score') or 0.0)
            provider = res.get('provider') or ''
            reason = res.get('reason') or ''
            self.logger.info(f"活体检测结果：attempt={attempt} live={live} score={score:.2f} provider={provider} reason={reason}")
            results.append(res)

            if _accept_strict(res):
                return True

        passed = sum(1 for r in results if r.get('ok') and _accept(r))
        return passed >= 1

    def run(self):
        """主运行循环"""
        self.logger.info("系统启动")
        self.running = True
        self.display.show_welcome()

        while self.running:
            try:
                # 1. 捕获帧（raw 用于识别/取证；preview 用于显示）
                raw_frame = self.camera.capture_raw()
                if raw_frame is None:
                    self._none_frame_streak += 1
                    if self._last_frame_ok_ts <= 0:
                        self._last_frame_ok_ts = time.time()
                    if self._none_frame_streak >= 15 and (time.time() - self._last_frame_ok_ts) >= 2.0:
                        try:
                            self.logger.warning("摄像头取帧失败，尝试重置摄像头")
                            try:
                                self.camera.release()
                            except Exception:
                                pass
                            try:
                                self.camera = Camera(use_libcamera=False)
                            except Exception:
                                self.camera = Camera(use_libcamera=True)
                            self._none_frame_streak = 0
                            self._last_frame_ok_ts = time.time()
                        except Exception as e:
                            self.logger.warning(f"摄像头重置失败：{e}")
                    self._frame_idx += 1
                    continue

                # 预览帧：仅用于屏幕展示，不污染识别链路
                preview_frame = self.camera.preview_from_raw(raw_frame)
                self._frame_idx += 1
                self._latest_frame = raw_frame
                try:
                    self._frame_buffer.append(raw_frame.copy())
                except Exception:
                    pass
                self._none_frame_streak = 0
                self._last_frame_ok_ts = time.time()

                # 锁定态：停止识别，只显示“已锁定”，并仍允许成员同步（便于远程恢复/更新）
                if lockdown.is_locked():
                    self.display.show_frame(preview_frame, overlay_text="系统已锁定")
                    time.sleep(1)
                    self.data_sync.sync_members_if_needed(min_interval_sec=60)
                    continue

                self.display.show_frame(preview_frame, overlay_text="运行中")

                # 识别节流：每 3 帧才进入识别，同时按 RECOGNITION_INTERVAL_SEC 限制识别频率
                if self._frame_idx % 3 != 0:
                    self.data_sync.sync_members_if_needed(min_interval_sec=60)
                    continue

                now_ts = time.time()
                if now_ts - self._last_recognition_ts < float(self._recognition_interval_sec):
                    self.data_sync.sync_members_if_needed(min_interval_sec=60)
                    continue
                self._last_recognition_ts = now_ts

                # 2. 人脸检测
                faces = self.recognizer.detect_faces(raw_frame)

                if len(faces) == 0:
                    if self.alert_system:
                        try:
                            self.alert_system.stop_monitoring()
                        except Exception:
                            pass
                    self.data_sync.sync_members_if_needed(min_interval_sec=60)
                    continue

                # 3. 人脸识别（逐脸处理，可能触发：黑名单锁定 / 家庭成员开锁 / 陌生访客抓拍与预警）
                results_for_draw = []
                locked_now = False
                for face in faces:
                    try:
                        c = face.get('image')
                        if c is not None and getattr(c, 'size', 0) > 0:
                            self._face_crop_buffer.append(c.copy())
                    except Exception:
                        pass
                    result = self.recognizer.recognize(raw_frame, face)
                    result['box'] = face.get('box')
                    results_for_draw.append(result)

                    blacklist_hit = None
                    if self.blacklist:
                        now = time.time()
                        if now - self._last_blacklist_sync > 60:
                            try:
                                self.blacklist.sync()
                            finally:
                                self._last_blacklist_sync = now
                        blacklist_hit = self.blacklist.match(face.get('image'))

                    # 3.1 黑名单：命中则蜂鸣器报警 + 系统锁定 + 取证 + 上报云端
                    if blacklist_hit and blacklist_hit.get('hit'):
                        name = blacklist_hit.get('name') or '黑名单'
                        lockdown.lock(f"blacklist:{blacklist_hit.get('id')}:{name}")
                        self._ui_warning(f"黑名单警报：{name}", duration=10)
                        self.doorbell_controller.trigger_alarm(duration=1.0)
                        photo_path, video_path = self._collect_evidence(raw_frame)
                        if self.cloud_comm:
                            self.cloud_comm.report_blacklist_event(
                                blacklist_id=blacklist_hit.get('id'),
                                confidence=float(blacklist_hit.get('confidence') or 0.0),
                                photo_path=photo_path,
                                video_path=video_path,
                                location=os.environ.get('DEVICE_LOCATION')
                            )
                        locked_now = True
                        break

                    if result['is_known']:
                        # 3.2 家庭成员：活体通过后才允许开锁；并记录访问日志与云端访客记录
                        self.logger.info(f"识别到家庭成员：{result['name']}")
                        if self.alert_system:
                            try:
                                self.alert_system.stop_monitoring()
                            except Exception:
                                pass
                        now = time.time()
                        should_unlock = (self._last_unlock_name != result['name']) or (now - self._last_unlock_ts >= 5.0)
                        if should_unlock:
                            if not self._check_liveness(result['name'], face.get('box'), face_crop_bgr=face.get('image')):
                                self._ui_warning("活体检测未通过", duration=0.2)
                                self.logger.warning("活体检测未通过，已阻止开锁")
                                try:
                                    now2 = time.time()
                                    if now2 - float(self._last_liveness_beep_ts) >= 2.0:
                                        self._last_liveness_beep_ts = now2
                                        threading.Thread(
                                            target=self.doorbell_controller.buzzer.beep,
                                            args=(1.0,),
                                            daemon=True
                                        ).start()
                                except Exception:
                                    pass
                                continue
                            self.display.show_welcome_message(f"欢迎回家，{result['name']}!")
                            self.visitor_manager.log_access(result['name'], is_family=True)
                            if self.cloud_comm:
                                try:
                                    key = f"family:{result.get('name')}"
                                    if self._should_upload_face(key, self._same_face_upload_throttle_sec):
                                        vid = self.cloud_comm.upload_visitor(
                                            visitor_type='family',
                                            member_name=result.get('name'),
                                            confidence=float(result.get('confidence') or 0.0),
                                            face_bgr_image=face.get('image')
                                        )
                                        if not vid:
                                            self.logger.warning("访客记录上报失败")
                                except Exception:
                                    self.logger.warning("访客记录上报异常", exc_info=True)
                            self._last_unlock_name = result['name']
                            self._last_unlock_ts = now
                            self.doorbell_controller.on_member_recognized(result['name'])
                        else:
                            self.display.show_welcome_message(f"欢迎回家，{result['name']}!")
                    else:
                        # 3.3 陌生访客：抓拍落盘 + 本地记录 + 云端上传（节流）+ 触发预警监控
                        self._last_stranger_seen_ts = time.time()
                        self.logger.warning("检测到陌生访客")
                        self.display.show_unknown_visitor()
                        try:
                            fp = self._face_fingerprint(face.get('image'))
                            key = f"stranger:{fp}" if fp else "stranger:unknown"
                            if self._should_upload_face(key, self._same_face_upload_throttle_sec):
                                photo_dir = os.path.join(Config.DATA_DIR, 'unknown_faces')
                                os.makedirs(photo_dir, exist_ok=True)
                                ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
                                photo_path = os.path.join(photo_dir, f'unknown_{ts}.jpg')
                                cv2.imwrite(photo_path, face.get('image'))
                                self.visitor_manager.log_unknown_visitor(photo_path)
                                if self.cloud_comm:
                                    try:
                                        vid = self.cloud_comm.upload_visitor(
                                            visitor_type='stranger',
                                            member_name=None,
                                            confidence=float(result.get('confidence') or 0.0),
                                            face_bgr_image=face.get('image')
                                        )
                                        if not vid:
                                            self.logger.warning("访客记录上报失败")
                                    except Exception:
                                        self.logger.warning("访客记录上报异常", exc_info=True)
                        except Exception:
                            pass
                        self.alert_system.start_monitoring()

                if locked_now:
                    self.display.show_frame(preview_frame, overlay_text="系统已锁定")
                    continue

                # 识别结果叠加绘制：用于屏幕展示（不影响识别 raw_frame）
                try:
                    display_frame = self.display.draw_recognition_result(preview_frame, results_for_draw)
                except Exception:
                    display_frame = preview_frame
                self.display.show_frame(display_frame)

                # 4. 检查预警状态：陌生人离开后自动取消；满足条件则触发报警
                if self.alert_system and (time.time() - float(self._last_stranger_seen_ts) > 2.0):
                    try:
                        self.alert_system.stop_monitoring()
                    except Exception:
                        pass
                if self.alert_system.check_warning_condition():
                    self.alert_system.trigger_warning()

                # 5. 数据同步：访客/访问日志/成员同步等按策略上传/缓存
                self.data_sync.sync_if_needed()

            except Exception as e:
                self.logger.error(f"主循环错误：{e}", exc_info=True)

        self.shutdown()

    def shutdown(self):
        """关闭系统"""
        self.logger.info("正在关闭各模块...")
        # 释放摄像头、UI、预警与硬件资源
        self.camera.release()
        self.display.cleanup()
        self.alert_system.cleanup()
        self.doorbell_controller.cleanup()  # 清理蜂鸣器和电机
        if self.cloud_comm:
            try:
                # 停止云端后台任务（心跳/轮询等）
                self.cloud_comm.stop_background_tasks()
            except Exception:
                pass
        if self.mqtt_client:
            try:
                # 停止 MQTT 命令通道
                self.mqtt_client.stop()
            except Exception:
                pass
        self.logger.info("系统已关闭")

    def _collect_evidence(self, frame):
        # 黑名单取证：保存照片 + 录制短视频（用于后续追溯）
        os.makedirs(os.path.join(Config.DATA_DIR, 'evidence'), exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
        photo_path = os.path.join(Config.DATA_DIR, 'evidence', f'blacklist_{ts}.jpg')
        try:
            cv2.imwrite(photo_path, frame)
        except Exception:
            photo_path = None

        video_path = os.path.join(Config.DATA_DIR, 'evidence', f'blacklist_{ts}.mp4')
        try:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'mp4v'), 10.0, (w, h))
            start = time.time()
            while time.time() - start < 5:
                f = self.camera.capture_raw()
                if f is None:
                    break
                writer.write(f)
                time.sleep(0.1)
            writer.release()
        except Exception:
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except Exception:
                pass
            video_path = None

        return photo_path, video_path


def main():
    """主函数"""
    doorbell = SmartDoorbell()
    doorbell.run()


if __name__ == "__main__":
    main()
