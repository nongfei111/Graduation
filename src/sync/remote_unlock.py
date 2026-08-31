#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLAUDE 智能门铃系统 - 远程开锁控制模块
整合 MQTT 通信和步进电机控制，实现远程开关锁功能
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional, Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入配置
from .cloud_config import CloudConfig, NetworkConfig

# ==================== 步进电机控制 ====================

class StepperMotorController:
    """
    步进电机控制器
    支持 28BYJ-48 步进电机 + ULN2003 驱动板
    """

    def __init__(self, pins: List[int] = None, use_simulator: bool = False):
        """
        初始化步进电机控制器

        Args:
            pins: GPIO 引脚列表 [IN1, IN2, IN3, IN4]
            use_simulator: 是否使用模拟模式（无真实硬件）
        """
        config = NetworkConfig.get_motor_config()
        self.pins = pins or config.get('pins', [1, 7, 8, 25])
        self.steps_per_rev = config.get('steps_per_rev', 2048)
        self.unlock_angle = config.get('unlock_angle', 90)
        self.step_delay = config.get('unlock_delay', 0.002)
        self.use_simulator = use_simulator

        self.handle = None
        self.is_initialized = False

        # 半步模式序列
        self.step_sequence = [
            [1, 0, 0, 0],  # 1
            [1, 1, 0, 0],  # 1+2
            [0, 1, 0, 0],  # 2
            [0, 1, 1, 0],  # 2+3
            [0, 0, 1, 0],  # 3
            [0, 0, 1, 1],  # 3+4
            [0, 0, 0, 1],  # 4
            [0, 0, 0, 1],  # 4+1
        ]

        if not self.use_simulator:
            self._initialize_hardware()
        else:
            self.is_initialized = True
            logger.info("步进电机控制器已初始化（模拟模式）")

    def _initialize_hardware(self):
        """初始化硬件"""
        try:
            import lgpio
            self.handle = lgpio.gpiochip_open(0)
            for pin in self.pins:
                lgpio.gpio_claim_output(self.handle, pin, 0, 0)
            self.is_initialized = True
            logger.info(f"步进电机控制器已初始化 (引脚：{self.pins})")
        except ImportError:
            logger.warning("lgpio 库未安装，切换到模拟模式")
            self.use_simulator = True
            self.is_initialized = True
        except Exception as e:
            logger.error(f"初始化硬件失败：{e}，切换到模拟模式")
            self.use_simulator = True
            self.is_initialized = True

    def _set_pins(self, state: List[int]):
        """设置 GPIO 引脚状态"""
        if not self.is_initialized:
            return

        if self.use_simulator:
            logger.debug(f"[模拟] 设置引脚状态：{state}")
            return

        try:
            import lgpio
            for i, pin in enumerate(self.pins):
                lgpio.gpio_write(self.handle, pin, state[i])
        except Exception as e:
            logger.error(f"设置引脚状态失败：{e}")

    def step(self, clockwise: bool = True):
        """走一步"""
        if not self.is_initialized:
            return

        # 获取当前步序
        state = self.step_sequence[0] if clockwise else self.step_sequence[-1]
        self._set_pins(state)
        time.sleep(self.step_delay)

    def rotate(self, angle: float, clockwise: bool = True):
        """
        旋转指定角度

        Args:
            angle: 旋转角度（度）
            clockwise: 是否顺时针旋转
        """
        if not self.is_initialized:
            logger.info(f"[模拟] 旋转 {angle}度，方向：{'顺时针' if clockwise else '逆时针'}")
            return

        steps_needed = int((angle / 360.0) * self.steps_per_rev)
        logger.info(f"旋转 {angle}度 ({steps_needed} 步)")

        for i in range(steps_needed):
            if clockwise:
                state = self.step_sequence[i % len(self.step_sequence)]
            else:
                state = self.step_sequence[(-i - 1) % len(self.step_sequence)]
            self._set_pins(state)
            time.sleep(self.step_delay)

        # 归零
        self._set_pins([0, 0, 0, 0])

    def unlock(self):
        """执行开锁动作（旋转 90 度）"""
        logger.info(">>> 执行开锁动作")
        self.rotate(self.unlock_angle, clockwise=True)
        logger.info(">>> 开锁完成")

    def lock(self):
        """执行上锁动作（反向旋转 90 度）"""
        logger.info(">>> 执行上锁动作")
        self.rotate(self.unlock_angle, clockwise=False)
        logger.info(">>> 上锁完成")

    def test_rotation(self):
        """测试完整旋转"""
        logger.info("=== 测试：顺时针旋转一圈 ===")
        self.rotate(360, clockwise=True)
        time.sleep(1)
        logger.info("=== 测试：逆时针旋转一圈 ===")
        self.rotate(360, clockwise=False)
        logger.info("=== 测试完成 ===")

    def cleanup(self):
        """清理资源"""
        self._set_pins([0, 0, 0, 0])
        if self.handle:
            try:
                import lgpio
                lgpio.gpiochip_close(self.handle)
            except:
                pass
        logger.info("步进电机控制器已清理")


# ==================== 远程开锁控制器 ====================

class RemoteUnlockController:
    """
    远程开锁控制器
    整合 MQTT 通信和步进电机控制
    """

    def __init__(self, device_id: str = None, use_simulator: bool = False):
        """
        初始化远程开锁控制器

        Args:
            device_id: 设备唯一标识
            use_simulator: 是否使用模拟模式
        """
        # 获取配置
        network_config = NetworkConfig.get_network_config()
        self.device_id = device_id or network_config.get('device_id', 'raspi_doorbell_001')
        self.use_simulator = use_simulator

        # MQTT 配置
        self.mqtt_broker = CloudConfig.MQTT_BROKER
        self.mqtt_port = CloudConfig.MQTT_PORT
        self.mqtt_keepalive = CloudConfig.MQTT_KEEPALIVE

        # MQTT 主题
        self.topic_unlock = CloudConfig.TOPIC_UNLOCK
        self.topic_status = CloudConfig.TOPIC_STATUS
        self.topic_visitor = CloudConfig.TOPIC_VISITOR
        self.topic_alert = CloudConfig.TOPIC_ALERT

        # 组件
        self.motor: Optional[StepperMotorController] = None
        self.mqtt_client = None

        # 回调函数
        self.on_unlock_callback: Optional[Callable] = None

        # 状态
        self.is_running = False
        self.stats = {
            "connected": False,
            "connect_time": None,
            "unlock_count": 0,
            "last_unlock_time": None,
            "messages_received": 0,
            "messages_sent": 0
        }

        logger.info(f"RemoteUnlockController 已初始化 (设备 ID: {self.device_id})")

    def initialize(self):
        """初始化组件"""
        # 初始化步进电机
        self.motor = StepperMotorController(use_simulator=self.use_simulator)
        logger.info("步进电机控制器已初始化")

    def set_unlock_callback(self, callback: Callable):
        """
        设置开锁回调函数

        Args:
            callback: 回调函数，接收参数 (user_id: str, timestamp: str, method: str)
        """
        self.on_unlock_callback = callback
        logger.info("已设置开锁回调函数")

    def connect_mqtt(self) -> bool:
        """
        连接到 MQTT Broker

        Returns:
            是否连接成功
        """
        try:
            import paho.mqtt.client as mqtt

            # 创建客户端
            self.mqtt_client = mqtt.Client(client_id=self.device_id)
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message

            # 连接
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, self.mqtt_keepalive)
            logger.info(f"正在连接 MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")

            return True
        except ImportError:
            logger.error("paho-mqtt 库未安装，请运行：pip install paho-mqtt")
            return False
        except Exception as e:
            logger.error(f"MQTT 连接失败：{e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT 连接回调"""
        if rc == 0:
            self.stats["connected"] = True
            self.stats["connect_time"] = datetime.now().isoformat()
            logger.info(f"成功连接到 MQTT Broker: {self.mqtt_broker}:{self.mqtt_port}")

            # 订阅开锁主题
            self.mqtt_client.subscribe(self.topic_unlock)
            logger.info(f"已订阅主题：{self.topic_unlock}")

            # 发布上线通知
            self.publish_status("online")
        else:
            logger.error(f"连接失败，返回码：{rc}")
            self.stats["connected"] = False

    def _on_disconnect(self, client, userdata, rc):
        """MQTT 断开连接回调"""
        self.stats["connected"] = False
        logger.warning(f"MQTT 连接断开，返回码：{rc}")

        # 尝试重连
        if self.is_running:
            logger.info("将在 5 秒后尝试重连...")
            time.sleep(5)
            try:
                self.mqtt_client.reconnect()
            except Exception as e:
                logger.error(f"重连失败：{e}")

    def _on_message(self, client, userdata, msg):
        """MQTT 收到消息回调"""
        self.stats["messages_received"] += 1

        logger.info(f"收到消息 - 主题：{msg.topic}, 内容：{msg.payload.decode()}")

        try:
            payload = json.loads(msg.payload.decode())

            # 处理开锁指令
            if msg.topic == self.topic_unlock:
                self._handle_unlock_message(payload)

        except json.JSONDecodeError:
            logger.error(f"消息解析失败：{msg.payload}")
        except Exception as e:
            logger.error(f"处理消息失败：{e}")

    def _handle_unlock_message(self, payload: Dict):
        """
        处理开锁消息

        Args:
            payload: 消息内容 {"action": "unlock", "user_id": "xxx", "timestamp": "xxx"}
        """
        if payload.get("action") != "unlock":
            logger.warning(f"未知动作：{payload.get('action')}")
            return

        user_id = payload.get("user_id", "unknown")
        timestamp = payload.get("timestamp", "")
        method = payload.get("method", "mqtt")

        logger.info(f"收到开锁指令 - 用户：{user_id}, 时间：{timestamp}, 方式：{method}")

        # 执行开锁
        self._do_unlock(user_id=user_id, timestamp=timestamp, method=method)

    def _do_unlock(self, user_id: str, timestamp: str, method: str = "mqtt"):
        """
        执行开锁动作

        Args:
            user_id: 用户 ID
            timestamp: 时间戳
            method: 开锁方式 (mqtt, http, local)
        """
        logger.info(f"开始执行开锁 - 用户：{user_id}, 方式：{method}")

        try:
            # 控制步进电机执行开锁
            if self.motor and self.motor.is_initialized:
                self.motor.unlock()

            # 更新统计
            self.stats["unlock_count"] += 1
            self.stats["last_unlock_time"] = datetime.now().isoformat()

            # 调用回调函数
            if self.on_unlock_callback:
                self.on_unlock_callback(user_id=user_id, timestamp=timestamp, method=method)

            # 发布开锁成功通知
            self.publish_unlock_result(success=True, user_id=user_id, method=method)

            logger.info(f"开锁成功 - 用户：{user_id}")

        except Exception as e:
            logger.error(f"开锁失败：{e}")
            self.publish_unlock_result(success=False, error=str(e))

    def publish_status(self, status: str = "online"):
        """发布设备状态"""
        if not self.mqtt_client:
            return

        message = {
            "device_id": self.device_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "unlock_count": self.stats["unlock_count"]
        }

        try:
            self.mqtt_client.publish(self.topic_status, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info(f"已发布设备状态：{status}")
        except Exception as e:
            logger.error(f"发布状态失败：{e}")

    def publish_unlock_result(self, success: bool, user_id: str = None,
                               method: str = None, error: str = None):
        """发布开锁结果"""
        if not self.mqtt_client:
            return

        message = {
            "device_id": self.device_id,
            "type": "unlock_result",
            "success": success,
            "user_id": user_id,
            "method": method,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.mqtt_client.publish(self.topic_status, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info(f"已发布开锁结果：{'成功' if success else '失败'}")
        except Exception as e:
            logger.error(f"发布开锁结果失败：{e}")

    def publish_visitor(self, visitor_info: Dict):
        """发布访客通知"""
        if not self.mqtt_client:
            return

        message = {
            "device_id": self.device_id,
            "type": "visitor",
            "data": visitor_info,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.mqtt_client.publish(self.topic_visitor, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info("已发布访客通知")
        except Exception as e:
            logger.error(f"发布访客通知失败：{e}")

    def publish_alert(self, alert_info: Dict):
        """发布报警通知"""
        if not self.mqtt_client:
            return

        message = {
            "device_id": self.device_id,
            "type": "alert",
            "data": alert_info,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.mqtt_client.publish(self.topic_alert, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info("已发布报警通知")
        except Exception as e:
            logger.error(f"发布报警通知失败：{e}")

    def start(self, blocking: bool = True):
        """
        启动远程开锁控制器

        Args:
            blocking: 是否阻塞运行
        """
        if not self.motor:
            self.initialize()

        if not self.mqtt_client:
            if not self.connect_mqtt():
                logger.error("MQTT 连接失败，无法启动")
                return

        self.is_running = True

        if blocking:
            logger.info("远程开锁控制器启动（阻塞模式）")
            self.mqtt_client.loop_forever()
        else:
            logger.info("远程开锁控制器启动（后台模式）")
            self.mqtt_client.loop_start()

    def stop(self):
        """停止远程开锁控制器"""
        self.is_running = False

        # 发布下线通知
        self.publish_status("offline")

        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("MQTT 客户端已停止")

        if self.motor:
            self.motor.cleanup()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()

    def test_unlock(self):
        """测试开锁功能"""
        logger.info("=== 测试开锁功能 ===")
        self._do_unlock(user_id="test_user", timestamp=datetime.now().isoformat(), method="test")
        logger.info("=== 测试完成 ===")


# ==================== 入口函数 ====================

def create_remote_unlock_controller(device_id: str = None, use_simulator: bool = False) -> RemoteUnlockController:
    """
    创建远程开锁控制器

    Args:
        device_id: 设备 ID
        use_simulator: 是否使用模拟模式

    Returns:
        RemoteUnlockController 实例
    """
    controller = RemoteUnlockController(device_id=device_id, use_simulator=use_simulator)
    controller.initialize()
    return controller


# ==================== 测试入口 ====================

if __name__ == "__main__":
    # 测试代码
    logger.info("=" * 60)
    logger.info("CLAUDE 智能门铃 - 远程开锁控制测试")
    logger.info("=" * 60)

    # 创建控制器
    controller = create_remote_unlock_controller(use_simulator=True)

    # 设置回调
    def on_unlock(user_id: str, timestamp: str, method: str):
        logger.info(f"开锁回调 - 用户：{user_id}, 方式：{method}")

    controller.set_unlock_callback(on_unlock)

    # 测试开锁
    logger.info("\n[测试] 本地开锁")
    controller.test_unlock()

    # 启动 MQTT（如果可用）
    logger.info("\n[提示] 按 Ctrl+C 停止")
    try:
        controller.start(blocking=True)
    except KeyboardInterrupt:
        logger.info("测试结束，正在退出...")
        controller.stop()
