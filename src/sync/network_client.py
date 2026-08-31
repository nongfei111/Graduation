#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络通信模块
负责树莓派与云服务器之间的数据同步

功能：
1. HTTP 客户端封装
2. 心跳保持
3. 数据上传（访客记录、图片）
4. 命令轮询（接收远程开锁指令）
5. 离线缓存与断点续传
"""

import os
import json
import logging
import time
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from config.settings import Config, NetworkConfig

logger = logging.getLogger(__name__)


class NetworkClient:
    """网络客户端 - 封装所有与服务器的通信"""

    def __init__(self, device_id: str, server_host: str = None, server_port: int = None):
        """
        初始化网络客户端

        Args:
            device_id: 设备唯一标识
            server_host: 服务器地址
            server_port: 服务器端口
        """
        self.device_id = device_id
        self.server_host = server_host or NetworkConfig.SERVER_HOST
        self.server_port = server_port or NetworkConfig.SERVER_PORT
        self.base_url = f"http://{self.server_host}:{self.server_port}/api"

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

        self.access_token: Optional[str] = None
        self.is_online = False
        self.last_heartbeat: Optional[datetime] = None

        # 离线缓存
        self.offline_cache: List[Dict] = []
        self.cache_file = os.path.join(Config.DATA_DIR, 'offline_cache.json')

        # 回调函数
        self.on_unlock_command: Optional[Callable] = None
        self.on_reboot_command: Optional[Callable] = None

        # 线程控制
        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._command_poll_thread: Optional[threading.Thread] = None

        logger.info(f"NetworkClient 初始化完成 (设备 ID: {self.device_id})")
        logger.info(f"服务器地址：{self.base_url}")

    def set_auth_token(self, token: str):
        """设置认证 Token"""
        self.access_token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})
        logger.info("认证 Token 已设置")

    def login(self, username: str, password: str) -> bool:
        """
        用户登录（设备绑定用）

        Args:
            username: 用户名
            password: 密码

        Returns:
            登录是否成功
        """
        try:
            url = f"{self.base_url}/auth/login"
            response = self.session.post(url, json={
                'username': username,
                'password': password
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.set_auth_token(data['data']['access_token'])
                    logger.info("登录成功")
                    return True
            logger.error(f"登录失败：{response.text}")
            return False
        except Exception as e:
            logger.error(f"登录异常：{e}")
            return False

    def register_device(self, user_id: int, device_name: str = "智能门铃",
                        device_type: str = "raspberry_pi_4b",
                        firmware_version: str = "1.0.0") -> bool:
        """
        注册设备

        Args:
            user_id: 用户 ID
            device_name: 设备名称
            device_type: 设备类型
            firmware_version: 固件版本

        Returns:
            注册是否成功
        """
        try:
            url = f"{self.base_url}/device/{self.device_id}/register"
            response = self.session.post(url, json={
                'user_id': user_id,
                'device_name': device_name,
                'device_type': device_type,
                'firmware_version': firmware_version
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info(f"设备注册成功：{data['data']}")
                    return True
            logger.error(f"设备注册失败：{response.text}")
            return False
        except Exception as e:
            logger.error(f"设备注册异常：{e}")
            return False

    def send_heartbeat(self) -> Dict:
        """
        发送心跳

        Returns:
            服务器响应数据
        """
        try:
            url = f"{self.base_url}/device/heartbeat"
            response = self.session.post(url, json={
                'device_id': self.device_id,
                'ip_address': self._get_local_ip(),
                'firmware_version': '1.0.0'
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.is_online = True
                self.last_heartbeat = datetime.now()

                # 检查是否有待执行的命令
                if data.get('data', {}).get('pending_commands'):
                    self._handle_commands(data['data']['pending_commands'])

                return data.get('data', {})
            else:
                self.is_online = False
                return {}
        except Exception as e:
            logger.error(f"心跳发送失败：{e}")
            self.is_online = False
            return {}

    def upload_visitor(self, visitor_data: Dict, image_path: str = None,
                       thumbnail_path: str = None) -> bool:
        """
        上传访客记录

        Args:
            visitor_data: 访客数据
            image_path: 抓拍图片路径
            thumbnail_path: 缩略图路径

        Returns:
            上传是否成功
        """
        try:
            url = f"{self.base_url}/device/upload/visitor"

            # 准备文件上传
            files = {}
            if image_path and os.path.exists(image_path):
                files['capture_image'] = open(image_path, 'rb')
            if thumbnail_path and os.path.exists(thumbnail_path):
                files['thumbnail'] = open(thumbnail_path, 'rb')

            response = self.session.post(url, data=visitor_data, files=files, timeout=30)

            # 关闭文件
            for f in files.values():
                f.close()

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info(f"访客记录上传成功：{data['data']}")
                    return True

            logger.error(f"上传失败：{response.text}")
            return False
        except Exception as e:
            logger.error(f"上传异常：{e}")
            # 添加到离线缓存
            self._add_to_offline_cache(visitor_data, image_path, thumbnail_path)
            return False

    def upload_batch_visitors(self, visitors: List[Dict], family_id: int) -> Dict:
        """
        批量上传访客记录

        Args:
            visitors: 访客数据列表
            family_id: 家庭 ID

        Returns:
            上传结果
        """
        try:
            url = f"{self.base_url}/device/upload/batch"
            response = self.session.post(url, json={
                'device_id': self.device_id,
                'family_id': family_id,
                'visitors': visitors
            }, timeout=60)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info(f"批量上传成功：{data['data']}")
                    # 清除已上传的缓存
                    self._clear_offline_cache()
                    return data['data']

            logger.error(f"批量上传失败：{response.text}")
            return {}
        except Exception as e:
            logger.error(f"批量上传异常：{e}")
            return {}

    def poll_commands(self) -> List[Dict]:
        """
        轮询设备命令

        Returns:
            待执行的命令列表
        """
        # 通过心跳接口获取命令
        return []  # 心跳中已处理

    def _handle_commands(self, commands: List[Dict]):
        """
        处理设备命令

        Args:
            commands: 命令列表
        """
        for cmd in commands:
            cmd_type = cmd.get('command_type')
            params = cmd.get('params', {})

            logger.info(f"收到命令：{cmd_type}, 参数：{params}")

            if cmd_type == 'unlock':
                if self.on_unlock_command:
                    self.on_unlock_command(params)
            elif cmd_type == 'reboot':
                if self.on_reboot_command:
                    self.on_reboot_command(params)
            elif cmd_type == 'update_settings':
                logger.info(f"更新设置：{params}")

    def _get_local_ip(self) -> str:
        """获取本地 IP 地址"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.server_host, self.server_port))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    # ==================== 离线缓存 ====================

    def _add_to_offline_cache(self, visitor_data: Dict, image_path: str = None,
                               thumbnail_path: str = None):
        """添加到离线缓存"""
        cache_entry = {
            'visitor_data': visitor_data,
            'image_path': image_path,
            'thumbnail_path': thumbnail_path,
            'timestamp': datetime.now().isoformat()
        }
        self.offline_cache.append(cache_entry)
        self._save_offline_cache()
        logger.info(f"已添加到离线缓存，当前缓存数量：{len(self.offline_cache)}")

    def _save_offline_cache(self):
        """保存离线缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.offline_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存离线缓存失败：{e}")

    def _load_offline_cache(self):
        """从文件加载离线缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.offline_cache = json.load(f)
                logger.info(f"加载离线缓存：{len(self.offline_cache)} 条记录")
        except Exception as e:
            logger.error(f"加载离线缓存失败：{e}")
            self.offline_cache = []

    def _clear_offline_cache(self):
        """清除离线缓存"""
        self.offline_cache = []
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        logger.info("离线缓存已清除")

    def sync_offline_cache(self, family_id: int) -> bool:
        """
        同步离线缓存

        Args:
            family_id: 家庭 ID

        Returns:
            是否同步成功
        """
        if not self.offline_cache:
            return True

        logger.info(f"开始同步离线缓存，共 {len(self.offline_cache)} 条记录")

        # 批量上传
        visitors = []
        for entry in self.offline_cache:
            visitor_data = entry['visitor_data'].copy()
            visitor_data['family_id'] = family_id
            visitors.append(visitor_data)

        result = self.upload_batch_visitors(visitors, family_id)
        return result.get('uploaded_count', 0) == len(visitors)

    # ==================== 后台线程 ====================

    def start_background_tasks(self, heartbeat_interval: int = 30,
                                command_poll_interval: int = 5,
                                family_id: int = None):
        """
        启动后台任务

        Args:
            heartbeat_interval: 心跳间隔（秒）
            command_poll_interval: 命令轮询间隔（秒）
            family_id: 家庭 ID（用于离线缓存同步）
        """
        self._stop_event.clear()

        # 启动心跳线程
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(heartbeat_interval,),
            daemon=True
        )
        self._heartbeat_thread.start()

        # 启动命令轮询线程
        self._command_poll_thread = threading.Thread(
            target=self._command_poll_loop,
            args=(command_poll_interval, family_id),
            daemon=True
        )
        self._command_poll_thread.start()

        logger.info("后台任务已启动")

    def _heartbeat_loop(self, interval: int):
        """心跳循环"""
        while not self._stop_event.is_set():
            self.send_heartbeat()
            self._stop_event.wait(interval)

    def _command_poll_loop(self, interval: int, family_id: int = None):
        """命令轮询循环"""
        while not self._stop_event.is_set():
            # 定期尝试同步离线缓存
            if family_id and self.is_online and self.offline_cache:
                self.sync_offline_cache(family_id)
            self._stop_event.wait(interval)

    def stop_background_tasks(self):
        """停止后台任务"""
        self._stop_event.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        if self._command_poll_thread:
            self._command_poll_thread.join(timeout=5)
        logger.info("后台任务已停止")

    def cleanup(self):
        """清理资源"""
        self.stop_background_tasks()
        self.session.close()
        logger.info("网络客户端已清理")


# ==================== 工具函数 ====================

def get_device_id() -> str:
    """
    获取设备唯一 ID

    Returns:
        设备 ID 字符串
    """
    # 可以使用以下方式之一：
    # 1. MAC 地址
    # 2. CPU 序列号（树莓派）
    # 3. 配置文件中的固定值

    # 读取 CPU 序列号（树莓派）
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    return line.split(':')[1].strip()
    except Exception:
        pass

    # 使用 MAC 地址
    import uuid
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return f"doorbell_{mac}"


# ==================== 测试入口 ====================

if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    device_id = get_device_id()
    print(f"设备 ID: {device_id}")

    client = NetworkClient(device_id=device_id)

    # 测试登录
    success = client.login(username='test', password='test123')
    print(f"登录结果：{success}")

    # 测试心跳
    if success:
        result = client.send_heartbeat()
        print(f"心跳结果：{result}")

    client.cleanup()
