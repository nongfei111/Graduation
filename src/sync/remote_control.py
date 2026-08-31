#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程操控模块
接收云端命令并执行开门、警报、语音播报等操作

功能定位索引（设备端远程命令执行器）：
- 初始化与启动：main.py:_init_cloud_features() -> RemoteController.start()
- 命令接收入口：_on_cloud_command()（由 MQTT 或 HTTP 心跳拉取后触发）
- 命令类型处理：
  - unlock：_handle_unlock() -> gpio.unlock() -> gpio_control.py 电机开锁
  - snapshot：_handle_snapshot() -> frame_provider() -> 上报云端抓拍
  - alert：_handle_alert() -> gpio.trigger_alarm()
  - restart：_handle_restart() -> lockdown.unlock()（解除锁定）
  - speak：_handle_speak()（如启用语音/屏幕提示）

闭环约定：
- 每条命令执行后必须调用 cloud_comm.execute_command_result() 回传结果
"""

import os
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Optional, Callable
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RemoteController:
    """远程控制器类"""

    def __init__(
        self,
        cloud_comm,
        gpio_controller=None,
        display=None,
        audio_player=None,
        frame_provider: Optional[Callable[[], object]] = None
    ):
        """
        初始化远程控制器

        Args:
            cloud_comm: 云端通信实例
            gpio_controller: GPIO 控制器实例
            display: 显示屏实例
            audio_player: 音频播放器实例
        """
        self.cloud_comm = cloud_comm
        self.gpio = gpio_controller
        self.display = display
        self.audio = audio_player
        self.frame_provider = frame_provider
        self._recent_command_ids = deque(maxlen=200)
        self._recent_command_ids_set = set()

        # 命令处理回调
        self.command_handlers = {
            'unlock': self._handle_unlock,
            'alert': self._handle_alert,
            'speak': self._handle_speak,
            'snapshot': self._handle_snapshot,
            'restart': self._handle_restart
        }

        # 运行状态
        self.is_running = False

        # 设置云端命令回调
        self.cloud_comm.on_command_received = self._on_cloud_command

        logger.info("RemoteController 初始化完成")

    def start(self):
        """启动远程控制器"""
        self.is_running = True
        logger.info("远程控制器已启动")

    def stop(self):
        """停止远程控制器"""
        self.is_running = False
        logger.info("远程控制器已停止")

    def _on_cloud_command(self, command: Dict):
        """
        接收云端命令回调

        Args:
            command: 命令数据，格式：
                    {
                        'id': 命令 ID,
                        'type': 命令类型 (unlock/alert/speak/snapshot),
                        'data': 命令数据
                    }
        """
        if not self.is_running:
            logger.warning("远程控制器未运行，忽略命令")
            return

        command_type = command.get('type')
        command_id = command.get('id')
        command_data = command.get('data', {})

        logger.info(f"收到云端命令：ID={command_id}, 类型={command_type}")

        if command_id is not None:
            if command_id in self._recent_command_ids_set:
                return
            self._recent_command_ids.append(command_id)
            self._recent_command_ids_set.add(command_id)
            while len(self._recent_command_ids_set) > self._recent_command_ids.maxlen:
                try:
                    old = self._recent_command_ids.popleft()
                    self._recent_command_ids_set.discard(old)
                except Exception:
                    break

        # 查找并执行命令处理器
        handler = self.command_handlers.get(command_type)
        if handler:
            try:
                result = handler(command_data)
                # 上报执行结果
                self.cloud_comm.execute_command_result(
                    command_id=command_id,
                    success=result.get('success', False),
                    result=result.get('message', '')
                )
            except Exception as e:
                logger.error(f"命令执行失败：{e}")
                self.cloud_comm.execute_command_result(
                    command_id=command_id,
                    success=False,
                    result=str(e)
                )
        else:
            logger.warning(f"未知命令类型：{command_type}")

    def _handle_unlock(self, data: Dict) -> Dict:
        """
        处理开门命令

        Args:
            data: 命令数据 {'user_id': 用户 ID, 'timestamp': 时间戳}

        Returns:
            执行结果
        """
        logger.info("执行远程开门命令...")

        result = {'success': False, 'message': ''}

        try:
            # 1. 控制 GPIO 打开门锁
            if self.gpio:
                self.gpio.unlock()  # 假设 GPIO 控制器有 unlock 方法
                logger.info("门锁已打开")
                result['success'] = True
                result['message'] = '门锁已打开'
            else:
                logger.info("[模拟] 门锁已打开")
                result['success'] = True
                result['message'] = '[模拟] 门锁已打开'

        except Exception as e:
            result['message'] = f"开门失败：{e}"
            logger.error(result['message'])
            return result

        if self.display and result['success']:
            try:
                user_id = data.get('user_id', '未知用户')
                msg = f"远程开门 用户：{user_id}"
                if hasattr(self.display, 'show_message'):
                    self.display.show_message(msg, duration=3)
                elif hasattr(self.display, 'show_welcome_message'):
                    self.display.show_welcome_message(msg)
            except Exception as e:
                logger.warning(f"显示提示失败：{e}")

        if self.audio:
            try:
                self.audio.play("door_open.wav")
            except Exception as e:
                logger.warning(f"播放提示音失败：{e}")

        return result

    def _handle_alert(self, data: Dict) -> Dict:
        """
        处理警报命令

        Args:
            data: 命令数据 {'message': 警报消息}

        Returns:
            执行结果
        """
        logger.info("执行远程警报命令...")

        result = {'success': False, 'message': ''}

        try:
            message = data.get('message', '警告！')

            # 1. 触发蜂鸣器警报
            if self.gpio:
                self.gpio.trigger_alarm(duration=5)  # 假设 GPIO 有警报方法
                logger.info("警报已触发")
                result['success'] = True
                result['message'] = '警报已触发'
            else:
                logger.info(f"[模拟] 警报：{message}")
                result['success'] = True
                result['message'] = f'[模拟] 警报：{message}'

            # 2. 在显示屏上显示警告信息
            if self.display:
                try:
                    if hasattr(self.display, 'show_warning'):
                        self.display.show_warning(message, duration=10)
                    elif hasattr(self.display, 'show_message'):
                        self.display.show_message(message, duration=10)
                except Exception as e:
                    logger.warning(f"显示警告失败：{e}")

        except Exception as e:
            result['message'] = f"警报失败：{e}"
            logger.error(result['message'])

        return result

    def _handle_speak(self, data: Dict) -> Dict:
        """
        处理语音播报命令

        Args:
            data: 命令数据 {'message': 播报内容}

        Returns:
            执行结果
        """
        logger.info("执行语音播报命令...")

        result = {'success': False, 'message': ''}

        try:
            message = data.get('message', '')

            if not message:
                result['message'] = '播报内容为空'
                return result

            # 使用 TTS 或播放预录音频
            if self.audio:
                # 方式 1: TTS 文本转语音
                if hasattr(self.audio, 'speak'):
                    self.audio.speak(message)
                    logger.info(f"语音播报：{message}")
                # 方式 2: 播放预录音频
                else:
                    self.audio.play("message.wav")
                    logger.info("播放预录音频")

                result['success'] = True
                result['message'] = '语音播报完成'
            else:
                logger.info(f"[模拟] 语音播报：{message}")
                result['success'] = True
                result['message'] = f'[模拟] 语音播报：{message}'

            # 在显示屏上显示文字
            if self.display:
                try:
                    if hasattr(self.display, 'show_message'):
                        self.display.show_message(f"远程对讲 {message}", duration=5)
                except Exception as e:
                    logger.warning(f"显示文字失败：{e}")

        except Exception as e:
            result['message'] = f"语音播报失败：{e}"
            logger.error(result['message'])

        return result

    def _handle_snapshot(self, data: Dict) -> Dict:
        """
        处理抓拍命令

        Args:
            data: 命令数据 {'user_id': 用户 ID}

        Returns:
            执行结果
        """
        logger.info("执行远程抓拍命令...")

        result = {'success': False, 'message': ''}

        try:
            if not self.frame_provider:
                result['message'] = '抓拍失败：frame_provider 未配置'
                logger.error(result['message'])
                return result

            frame = self.frame_provider()
            if frame is None:
                result['message'] = '抓拍失败：当前无可用画面'
                logger.error(result['message'])
                return result

            try:
                import cv2
                import base64
                import json
            except Exception as e:
                result['message'] = f'抓拍失败：{e}'
                logger.error(result['message'])
                return result

            ok, buf = cv2.imencode('.jpg', frame)
            if not ok:
                result['message'] = '抓拍失败：图像编码失败'
                logger.error(result['message'])
                return result

            image_bytes = buf.tobytes()
            photo_data = base64.b64encode(image_bytes).decode('utf-8')

            payload_obj = {
                'device_id': self.cloud_comm.device_id,
                'visitor_type': 'stranger',
                'member_name': '远程抓拍',
                'confidence': 1.0,
                'photo_data': photo_data
            }
            payload = json.dumps(payload_obj, ensure_ascii=False).encode('utf-8')
            headers = self.cloud_comm._device_headers(payload)

            resp = self.cloud_comm.session.post(
                f"{self.cloud_comm.base_url}/api/visitor/upload",
                data=payload,
                headers={**headers, 'Content-Type': 'application/json'},
                timeout=30
            )
            data = resp.json()
            if data.get('success'):
                result['success'] = True
                result['message'] = '抓拍成功'
                result['visitor_id'] = data.get('visitor_id')
                logger.info(f"抓拍上传成功：访客 ID={result.get('visitor_id')}")
            else:
                result['message'] = f"抓拍上传失败：{data.get('error') or data}"
                logger.error(result['message'])

        except Exception as e:
            result['message'] = f"抓拍失败：{e}"
            logger.error(result['message'])

        return result

    def _handle_restart(self, data: Dict) -> Dict:
        """
        处理重启命令（解除黑名单锁定状态）

        Args:
            data: 命令数据 {'user_id': 用户 ID}

        Returns:
            执行结果
        """
        logger.info("执行远程重启命令（解除锁定）...")

        result = {'success': False, 'message': ''}

        try:
            from src.security import lockdown

            if lockdown.is_locked():
                lockdown.unlock()
                logger.info("系统已解除锁定状态")
                result['success'] = True
                result['message'] = '系统已解除锁定'
            else:
                logger.info("系统未处于锁定状态")
                result['success'] = True
                result['message'] = '系统未处于锁定状态'

            if self.display:
                try:
                    if hasattr(self.display, 'show_welcome'):
                        self.display.show_welcome()
                    elif hasattr(self.display, 'show_message'):
                        self.display.show_message("系统已重启", duration=3)
                except Exception as e:
                    logger.warning(f"显示提示失败：{e}")

        except Exception as e:
            result['message'] = f"重启失败：{e}"
            logger.error(result['message'])

        return result


# ==================== 集成的远程操控服务 ====================

class RemoteControlService:
    """远程操控服务（独立运行）"""

    def __init__(self, config: Dict):
        """
        初始化远程操控服务

        Args:
            config: 配置字典
                - cloud_host: 云服务器地址
                - cloud_port: 云服务器端口
                - device_id: 设备 ID
                - username: 登录用户名
                - password: 登录密码
        """
        self.config = config
        self.cloud_comm = None
        self.controller = None
        self.is_running = False

    def initialize(self) -> bool:
        """初始化服务"""
        try:
            # 1. 初始化云端通信
            from src.sync.cloud_communication import CloudCommunication

            self.cloud_comm = CloudCommunication(
                cloud_host=self.config['cloud_host'],
                cloud_port=self.config['cloud_port'],
                device_id=self.config.get('device_id')
            )

            # 2. 登录
            if not self.cloud_comm.login(
                self.config['username'],
                self.config['password']
            ):
                logger.error("登录失败")
                return False

            # 3. 注册设备
            self.cloud_comm.register_device(
                user_id=self.cloud_comm.user_id,
                device_name=self.config.get('device_name', '智能门铃')
            )

            # 4. 初始化硬件模块
            gpio = None
            display = None
            audio = None

            try:
                from src.core.gpio_controller import GPIOController
                gpio = GPIOController()
                gpio.setup()
                logger.info("GPIO 控制器已初始化")
            except Exception as e:
                logger.warning(f"GPIO 初始化失败：{e} (模拟模式)")

            try:
                from src.interaction.display import Display
                display = Display()
                display.init()
                logger.info("显示屏已初始化")
            except Exception as e:
                logger.warning(f"显示屏初始化失败：{e}")

            logger.info("远程操控服务初始化完成")
            return True

        except Exception as e:
            logger.error(f"服务初始化失败：{e}")
            return False

    def start(self):
        """启动服务"""
        if not self.cloud_comm:
            logger.error("服务未初始化")
            return

        # 1. 初始化控制器
        self.controller = RemoteController(
            cloud_comm=self.cloud_comm,
            gpio=None,  # 传入实际硬件实例
            display=None,
            audio=None
        )

        # 2. 启动云端通信后台任务
        self.cloud_comm.start_background_tasks(heartbeat_interval=30)

        # 3. 启动控制器
        self.controller.start()

        self.is_running = True
        logger.info("远程操控服务已启动")

        # 4. 主循环
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            self.stop()

    def stop(self):
        """停止服务"""
        self.is_running = False

        if self.controller:
            self.controller.stop()

        if self.cloud_comm:
            self.cloud_comm.stop_background_tasks()

        logger.info("远程操控服务已停止")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 配置
    config = {
        'cloud_host': '8.134.196.56',
        'cloud_port': 5000,
        'device_id': 'doorbell_001',
        'device_name': '我家门铃',
        'username': 'admin',
        'password': 'admin123'
    }

    # 创建并启动服务
    service = RemoteControlService(config)

    if service.initialize():
        print("服务初始化成功，按 Ctrl+C 停止...")
        service.start()
    else:
        print("服务初始化失败")
