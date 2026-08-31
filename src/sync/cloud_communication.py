#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备端与云服务器的通信模块
支持 API 调用、WebSocket 实时通信、断点续传

功能定位索引（设备端“上云/下发命令/活体复核”入口）：
- 登录/注册设备：login() / register_device() -> 云端 /api/auth/login, /api/device/register
- 心跳与命令拉取兜底：start_background_tasks() -> 云端 /api/device/heartbeat
- 远程命令执行回执：execute_command_result() -> 云端 /api/command/result
- 访客记录上报：upload_visitor() -> 云端 /api/visitor/upload
- 活体检测云端复核：check_liveness() -> 云端 /api/liveness/check
- 成员同步：get_device_members() -> 云端 /api/device/members（DataSync 会调用）

安全与可靠性：
- 设备鉴权：_device_headers() 生成 X-Device-* 签名头（nonce + timestamp + body_hash）
- 防并发拥塞：访客上传与活体复核使用锁做串行化（避免同时多请求导致超时）
"""

import os
import json
import time
import logging
import requests
import base64
import threading
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Dict, Optional, Callable, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudCommunication:
    """云端通信类"""

    def __init__(
        self,
        cloud_host: str,
        cloud_port: int = 5000,
        device_id: str = None,
        user_token: str = None,
        device_token: str = None
    ):
        """
        初始化云端通信

        Args:
            cloud_host: 云服务器地址
            cloud_port: 云服务器端口
            device_id: 设备唯一 ID
            user_token: 用户认证 Token (JWT)
        """
        self.cloud_host = cloud_host
        self.cloud_port = cloud_port
        self.base_url = f"http://{cloud_host}:{cloud_port}"
        self.device_id = device_id or self._generate_device_id()
        self.user_token = user_token
        self.device_token = device_token
        self.session = requests.Session()
        self.user_id: Optional[int] = None

        # 通信状态
        self.is_connected = False
        self.last_heartbeat = None
        self.pending_commands: List[Dict] = []

        # 回调函数
        self.on_command_received: Optional[Callable] = None
        self.on_connection_lost: Optional[Callable] = None

        # 后台线程
        self._heartbeat_thread = None
        self._command_poll_thread = None
        self._stop_flag = False
        self._visitor_upload_lock = threading.Lock()
        self._last_visitor_upload_ts = 0.0
        self._visitor_upload_global_interval_sec = 1.0
        self._same_visitor_interval_sec = 10.0
        self._last_visitor_by_key: Dict[str, float] = {}
        self._liveness_lock = threading.Lock()
        self._liveness_timeout_sec = float(os.environ.get('LIVENESS_TIMEOUT_SEC') or 10.0)

        logger.info(f"CloudCommunication 初始化完成 (服务器：{self.base_url}, 设备：{self.device_id})")

    def _generate_device_id(self) -> str:
        """生成设备唯一 ID"""
        import uuid
        # 使用 MAC 地址 + UUID 生成唯一设备 ID
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0, 2 * 6, 2)][::-1])
        return f"doorbell_{mac.replace(':', '')}"

    def set_token(self, token: str):
        """设置用户 Token"""
        self.user_token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        logger.info("用户 Token 已更新")

    def set_device_token(self, token: str):
        self.device_token = token
        logger.info("设备 Token 已更新")

    def _device_headers(self, body: bytes) -> Dict[str, str]:
        if not self.device_token:
            return {}

        ts = str(int(time.time()))
        nonce = secrets.token_hex(12)
        body_hash = hashlib.sha256(body or b'').hexdigest()
        msg = f"{self.device_id}|{ts}|{nonce}|{body_hash}".encode('utf-8')
        sig = hmac.new(self.device_token.encode('utf-8'), msg, hashlib.sha256).hexdigest()
        return {
            'X-Device-Id': self.device_id,
            'X-Device-Timestamp': ts,
            'X-Device-Nonce': nonce,
            'X-Device-Signature': sig
        }

    def login(self, username: str, password: str) -> bool:
        """
        用户登录

        Args:
            username: 用户名
            password: 密码

        Returns:
            登录是否成功
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={'username': username, 'password': password},
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                token = None
                data = result.get('data') or {}
                token = data.get('access_token') or result.get('access_token')
                if not token:
                    logger.error("登录失败：响应缺少 access_token")
                    return False
                self.set_token(token)
                user = data.get('user') or {}
                if isinstance(user, dict) and user.get('id') is not None:
                    try:
                        self.user_id = int(user.get('id'))
                    except Exception:
                        self.user_id = None
                logger.info(f"登录成功：{username}")
                return True
            else:
                logger.error(f"登录失败：{result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"登录异常：{e}")
            return False

    def get_device_members(self) -> Optional[Dict]:
        try:
            payload = b''
            headers = self._device_headers(payload)
            response = self.session.get(
                f"{self.base_url}/api/device/members",
                headers=headers,
                timeout=10
            )
            result = response.json()
            if result.get('success'):
                return result.get('data') or {}
            logger.error(f"设备成员同步失败：{result.get('error') or result}")
            return None
        except Exception as e:
            logger.error(f"设备成员同步异常：{e}")
            return None

    def register_device(self, user_id: Optional[int] = None, device_name: str = "智能门铃") -> bool:
        """
        设备注册

        Args:
            user_id: 用户 ID
            device_name: 设备名称

        Returns:
            注册是否成功
        """
        try:
            if user_id is None:
                user_id = self.user_id
            response = self.session.post(
                f"{self.base_url}/api/device/register",
                json={
                    'device_id': self.device_id,
                    'device_name': device_name,
                    'user_id': user_id,
                    'device_type': 'raspberry_pi_4b',
                    'firmware_version': '1.0.0'
                },
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                device_token = result.get('device_token')
                if device_token:
                    self.set_device_token(device_token)
                logger.info(f"设备注册成功：{self.device_id}")
                return True
            else:
                logger.error(f"设备注册失败：{result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"设备注册异常：{e}")
            return False

    def send_heartbeat(self) -> bool:
        """
        发送心跳

        Returns:
            是否成功
        """
        try:
            payload = json.dumps({'device_id': self.device_id}).encode('utf-8')
            headers = self._device_headers(payload)
            response = self.session.post(
                f"{self.base_url}/api/device/heartbeat",
                data=payload,
                headers={**headers, 'Content-Type': 'application/json'},
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                self.is_connected = True
                self.last_heartbeat = datetime.now()

                # 检查是否有远程命令
                command = result.get('command')
                if command and self.on_command_received:
                    logger.info(f"收到远程命令：{command['type']}")
                    self.on_command_received(command)

                return True
            else:
                self.is_connected = False
                return False

        except Exception as e:
            logger.error(f"心跳发送失败：{e}")
            self.is_connected = False
            return False

    def upload_visitor(
        self,
        visitor_type: str,
        member_name: Optional[str] = None,
        confidence: float = 0.0,
        face_bgr_image=None,
        photo_path: Optional[str] = None
    ) -> Optional[int]:
        """
        上传访客记录

        Args:
            visitor_type: 访客类型 ('family' 或 'stranger')
            member_name: 匹配的成员姓名
            confidence: 匹配置信度
            photo_path: 照片路径

        Returns:
            访客记录 ID，失败返回 None
        """
        try:
            photo_data = None
            photo_key = None
            if face_bgr_image is not None:
                try:
                    import cv2
                    ok, buf = cv2.imencode('.jpg', face_bgr_image)
                    if ok:
                        image_bytes = buf.tobytes()
                        photo_data = base64.b64encode(image_bytes).decode('utf-8')
                        photo_key = hashlib.sha256(image_bytes).hexdigest()[:16]
                except Exception:
                    photo_data = None
            elif photo_path and os.path.exists(photo_path):
                with open(photo_path, 'rb') as f:
                    image_bytes = f.read()
                photo_data = base64.b64encode(image_bytes).decode('utf-8')
                photo_key = hashlib.sha256(image_bytes).hexdigest()[:16]

            vt = (visitor_type or '').strip().lower()
            if vt in ('family', 'member'):
                vt = 'family'
            else:
                vt = 'stranger'

            if vt == 'family':
                visitor_key = f"family:{(member_name or '').strip().lower()}"
            else:
                visitor_key = f"stranger:{photo_key or 'noimg'}"

            now = time.time()
            with self._visitor_upload_lock:
                if now - self._last_visitor_upload_ts < float(self._visitor_upload_global_interval_sec):
                    return None
                last_same = self._last_visitor_by_key.get(visitor_key)
                if last_same is not None and now - float(last_same) < float(self._same_visitor_interval_sec):
                    return None
                self._last_visitor_upload_ts = now
                self._last_visitor_by_key[visitor_key] = now
                if len(self._last_visitor_by_key) > 1024:
                    cutoff = now - 120.0
                    self._last_visitor_by_key = {k: v for k, v in self._last_visitor_by_key.items() if v >= cutoff}

            payload_obj = {
                'device_id': self.device_id,
                'visitor_type': vt,
                'member_name': member_name,
                'confidence': float(confidence or 0.0),
                'photo_data': photo_data
            }
            payload = json.dumps(payload_obj, ensure_ascii=False).encode('utf-8')
            headers = self._device_headers(payload)
            response = self.session.post(
                f"{self.base_url}/api/visitor/upload",
                data=payload,
                headers={**headers, 'Content-Type': 'application/json'},
                timeout=30
            )
            result = response.json()

            if result.get('success'):
                logger.info(f"访客记录上传成功：ID={result.get('visitor_id')}")
                return result.get('visitor_id')
            else:
                logger.error(f"访客记录上传失败：{result.get('error') or result}")
                return None

        except Exception as e:
            logger.error(f"访客记录上传异常：{e}")
            return None

    def check_liveness(self, frames: List[str], member_name: Optional[str] = None) -> Dict:
        try:
            if not frames:
                return {'ok': False, 'live': False, 'score': 0.0, 'reason': 'no frames'}

            payload_obj = {
                'device_id': self.device_id,
                'member_name': member_name,
                'frames': frames
            }
            payload = json.dumps(payload_obj, ensure_ascii=False).encode('utf-8')
            headers = self._device_headers(payload)
            if not headers:
                return {'ok': False, 'live': False, 'score': 0.0, 'reason': 'device auth missing'}

            with self._liveness_lock:
                response = self.session.post(
                    f"{self.base_url}/api/liveness/check",
                    data=payload,
                    headers={**headers, 'Content-Type': 'application/json'},
                    timeout=self._liveness_timeout_sec
                )
            result = response.json()
            if not result.get('success'):
                return {'ok': False, 'live': False, 'score': 0.0, 'reason': result.get('error') or str(result)}

            return {
                'ok': True,
                'live': bool(result.get('live')),
                'score': float(result.get('score') or 0.0),
                'reason': result.get('reason') or '',
                'provider': result.get('provider') or ''
            }
        except Exception as e:
            return {'ok': False, 'live': False, 'score': 0.0, 'reason': str(e)}

    def execute_command_result(self, command_id: int, success: bool, result: str = ""):
        """
        上报命令执行结果

        Args:
            command_id: 命令 ID
            success: 是否成功
            result: 执行结果描述
        """
        try:
            payload_obj = {
                'device_id': self.device_id,
                'command_id': command_id,
                'success': bool(success),
                'result': result
            }
            payload = json.dumps(payload_obj).encode('utf-8')
            headers = self._device_headers(payload)
            self.session.post(
                f"{self.base_url}/api/command/result",
                data=payload,
                headers={**headers, 'Content-Type': 'application/json'},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"命令结果上报失败：{e}")

    def get_blacklist(self, since: Optional[str] = None) -> List[Dict]:
        try:
            params = {}
            if since:
                params['since'] = since
            headers = self._device_headers(b'')
            response = self.session.get(
                f"{self.base_url}/api/device/blacklist/list",
                params=params,
                headers=headers,
                timeout=10
            )
            result = response.json()
            if result.get('success'):
                data = result.get('data') or {}
                return data.get('items') or []
            return []
        except Exception as e:
            logger.error(f"获取黑名单失败：{e}")
            return []

    def report_blacklist_event(
        self,
        blacklist_id: Optional[int],
        confidence: float,
        photo_path: Optional[str] = None,
        video_path: Optional[str] = None,
        location: Optional[str] = None
    ) -> bool:
        try:
            files = {}
            opened = []
            try:
                if photo_path and os.path.exists(photo_path):
                    f = open(photo_path, 'rb')
                    opened.append(f)
                    files['photo'] = (os.path.basename(photo_path), f, 'image/jpeg')
                if video_path and os.path.exists(video_path):
                    f = open(video_path, 'rb')
                    opened.append(f)
                    files['video'] = (os.path.basename(video_path), f, 'video/mp4')

                data = {
                    'device_id': self.device_id,
                    'blacklist_id': '' if blacklist_id is None else str(int(blacklist_id)),
                    'confidence': str(float(confidence)),
                    'location': location or ''
                }

                req = requests.Request('POST', f"{self.base_url}/api/device/blacklist/event", data=data, files=files)
                prepped = self.session.prepare_request(req)
                body = prepped.body or b''
                if isinstance(body, str):
                    body = body.encode('utf-8')
                headers = self._device_headers(body)
                prepped.headers.update(headers)
                resp = self.session.send(prepped, timeout=30)
                j = resp.json()
                return bool(j.get('success'))
            finally:
                for f in opened:
                    try:
                        f.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"上报黑名单事件失败：{e}")
            return False

    def start_background_tasks(self, heartbeat_interval: int = 30):
        """
        启动后台任务

        Args:
            heartbeat_interval: 心跳间隔（秒）
        """
        self._stop_flag = False

        # 启动心跳线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(heartbeat_interval,),
            daemon=True
        )
        self._heartbeat_thread.start()
        logger.info(f"心跳线程已启动 (间隔：{heartbeat_interval}秒)")

    def stop_background_tasks(self):
        """停止后台任务"""
        self._stop_flag = True
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("后台任务已停止")

    def _heartbeat_loop(self, interval: int):
        """心跳循环"""
        while not self._stop_flag:
            self.send_heartbeat()
            time.sleep(interval)

    def get_visitor_list(self, limit: int = 100, visitor_type: Optional[str] = None) -> List[Dict]:
        """
        获取访客列表

        Args:
            limit: 数量限制
            visitor_type: 访客类型过滤

        Returns:
            访客列表
        """
        try:
            params = {'limit': limit}
            if visitor_type:
                params['type'] = visitor_type

            response = self.session.get(
                f"{self.base_url}/api/visitor/list",
                params=params,
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                return result.get('visitors', [])
            else:
                logger.error(f"获取访客列表失败：{result.get('error')}")
                return []

        except Exception as e:
            logger.error(f"获取访客列表异常：{e}")
            return []

    def get_statistics(self) -> Dict:
        """
        获取统计数据

        Returns:
            统计数据
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/stats",
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                return result.get('stats', {})
            else:
                return {}

        except Exception as e:
            logger.error(f"获取统计数据异常：{e}")
            return {}

    def get_connection_status(self) -> Dict:
        """
        获取连接状态

        Returns:
            连接状态信息
        """
        return {
            'is_connected': self.is_connected,
            'server': self.base_url,
            'device_id': self.device_id,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'has_token': bool(self.user_token)
        }


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 测试代码
    cloud = CloudCommunication(
        cloud_host="8.134.196.56",
        cloud_port=5000,
        device_id="test_device_001"
    )

    # 登录
    if cloud.login("admin", "admin123"):
        print("登录成功")

        # 注册设备
        cloud.register_device(user_id=1, device_name="测试门铃")

        # 设置命令回调
        def on_command(cmd):
            print(f"收到命令：{cmd}")
            # 执行命令逻辑...

        cloud.on_command_received = on_command

        # 启动后台心跳
        cloud.start_background_tasks(heartbeat_interval=30)

        # 上传访客记录
        visitor_id = cloud.upload_visitor(
            visitor_type="family",
            member_name="张三",
            confidence=0.95,
            photo_path="test.jpg"
        )

        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cloud.stop_background_tasks()
