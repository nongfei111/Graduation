#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT 客户端模块
负责与云服务器通信，接收远程控制指令（开锁等）
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional, Dict
import paho.mqtt.client as mqtt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MQTT 配置 ====================

# 公共 MQTT Broker（与云服务器使用同一个）
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# MQTT 主题
TOPIC_UNLOCK = "doorbell/unlock"      # 接收开锁指令
TOPIC_STATUS = "doorbell/status"      # 发送设备状态
TOPIC_VISITOR = "doorbell/visitor"    # 发送访客通知
TOPIC_ALERT = "doorbell/alert"        # 发送报警通知


class MQTTClient:
    """MQTT 客户端类"""

    def __init__(self, device_id: str = "raspi_doorbell"):
        """
        初始化 MQTT 客户端

        Args:
            device_id: 设备唯一标识
        """
        self.device_id = device_id
        self.client: Optional[mqtt.Client] = None
        self.running = False
        self.unlock_callback: Optional[Callable] = None

        # 统计信息
        self.stats = {
            "connected": False,
            "connect_time": None,
            "messages_received": 0,
            "messages_sent": 0,
            "last_message_time": None
        }

    def set_unlock_callback(self, callback: Callable):
        """
        设置开锁回调函数

        Args:
            callback: 回调函数，接收参数 (user_id: str, timestamp: str)
        """
        self.unlock_callback = callback
        logger.info("已设置开锁回调函数")

    def _on_connect(self, client, userdata, flags, rc):
        """连接回调"""
        if rc == 0:
            self.stats["connected"] = True
            self.stats["connect_time"] = datetime.now().isoformat()
            logger.info(f"成功连接到 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")

            # 订阅主题
            self.client.subscribe(TOPIC_UNLOCK)
            logger.info(f"已订阅主题：{TOPIC_UNLOCK}")

            # 发布上线通知
            self.publish_status("online")
        else:
            logger.error(f"连接失败，返回码：{rc}")
            self.stats["connected"] = False

    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        self.stats["connected"] = False
        logger.warning(f"MQTT 连接断开，返回码：{rc}")

        # 尝试重连
        if self.running:
            logger.info("将在 5 秒后尝试重连...")
            time.sleep(5)
            try:
                self.client.reconnect()
            except Exception as e:
                logger.error(f"重连失败：{e}")

    def _on_message(self, client, userdata, msg):
        """收到消息回调"""
        self.stats["messages_received"] += 1
        self.stats["last_message_time"] = datetime.now().isoformat()

        logger.info(f"收到消息 - 主题：{msg.topic}, 内容：{msg.payload.decode()}")

        try:
            payload = json.loads(msg.payload.decode())

            # 处理开锁指令
            if msg.topic == TOPIC_UNLOCK:
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

        logger.info(f"收到开锁指令 - 用户：{user_id}, 时间：{timestamp}")

        # 调用回调函数执行开锁
        if self.unlock_callback:
            try:
                self.unlock_callback(user_id=user_id, timestamp=timestamp)
            except Exception as e:
                logger.error(f"执行开锁回调失败：{e}")
        else:
            logger.warning("未设置开锁回调函数，无法执行开锁")

    def connect(self) -> bool:
        """
        连接到 MQTT Broker

        Returns:
            是否连接成功
        """
        try:
            # 创建客户端
            self.client = mqtt.Client(client_id=self.device_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # 连接
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            logger.info(f"正在连接 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")

            return True
        except Exception as e:
            logger.error(f"MQTT 连接失败：{e}")
            return False

    def start(self, blocking: bool = True):
        """
        启动 MQTT 客户端

        Args:
            blocking: 是否阻塞运行
        """
        if not self.client:
            logger.error("MQTT 未连接，请先调用 connect()")
            return

        self.running = True

        if blocking:
            logger.info("MQTT 客户端启动（阻塞模式）")
            self.client.loop_forever()
        else:
            logger.info("MQTT 客户端启动（后台模式）")
            self.client.loop_start()

    def stop(self):
        """停止 MQTT 客户端"""
        self.running = False

        # 发布下线通知
        self.publish_status("offline")

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT 客户端已停止")

    def publish_status(self, status: str = "online"):
        """
        发布设备状态

        Args:
            status: 状态 ("online" 或 "offline")
        """
        if not self.client:
            return

        message = {
            "device_id": self.device_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.client.publish(TOPIC_STATUS, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info(f"已发布状态：{status}")
        except Exception as e:
            logger.error(f"发布状态失败：{e}")

    def publish_visitor(self, visitor_info: Dict):
        """
        发布访客通知

        Args:
            visitor_info: 访客信息
        """
        if not self.client:
            return

        message = {
            "device_id": self.device_id,
            "type": "visitor",
            "data": visitor_info,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.client.publish(TOPIC_VISITOR, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info(f"已发布访客通知")
        except Exception as e:
            logger.error(f"发布访客通知失败：{e}")

    def publish_alert(self, alert_info: Dict):
        """
        发布报警通知

        Args:
            alert_info: 报警信息
        """
        if not self.client:
            return

        message = {
            "device_id": self.device_id,
            "type": "alert",
            "data": alert_info,
            "timestamp": datetime.now().isoformat()
        }

        try:
            self.client.publish(TOPIC_ALERT, json.dumps(message))
            self.stats["messages_sent"] += 1
            logger.info(f"已发布报警通知")
        except Exception as e:
            logger.error(f"发布报警通知失败：{e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()


# ==================== 开锁动作实现 ====================

def do_unlock_action(user_id: str, timestamp: str):
    """
    执行开锁动作

    Args:
        user_id: 用户 ID
        timestamp: 时间戳
    """
    logger.info(f"执行开锁动作 - 用户：{user_id}")

    # 导入 GPIO 控制模块
    try:
        from gpio_control import GPIOController
        controller = GPIOController()
        controller.unlock()  # 假设你的 GPIO 控制模块有这个方法
        logger.info("开锁成功")
    except ImportError:
        logger.warning("GPIO 控制模块未导入，模拟开锁动作")
        # 如果没有 GPIO 模块，这里只是日志记录
        pass
    except Exception as e:
        logger.error(f"开锁失败：{e}")


# ==================== 主程序（测试用） ====================

if __name__ == "__main__":
    logger.info("MQTT 客户端测试程序启动")

    # 创建客户端
    client = MQTTClient(device_id="raspi_doorbell_001")

    # 设置开锁回调
    client.set_unlock_callback(do_unlock_action)

    # 连接
    if client.connect():
        # 启动（阻塞模式）
        try:
            client.start(blocking=True)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")
            client.stop()
    else:
        logger.error("MQTT 连接失败，程序退出")
