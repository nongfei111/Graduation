"""
MQTT 命令通道（设备端）

功能定位索引：
- 启动位置：main.py:_init_cloud_features() 创建并启动 MqttCommandClient
- 订阅 Topic：{MQTT_TOPIC_PREFIX}/{device_id}/cmd（云端 mqtt_publisher.py 发布）
- 收到消息后回调：on_command(cmd) -> RemoteController._on_cloud_command(cmd)

用途：
- MQTT 作为远程控制的低延迟主通道；HTTP 心跳轮询作为兜底通道
"""

import os
import json
import time
import logging
from typing import Callable, Optional, Dict


logger = logging.getLogger(__name__)


class MqttCommandClient:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.client = None
        self.on_command: Optional[Callable[[Dict], None]] = None

        self.broker = os.environ.get('MQTT_BROKER', 'broker.emqx.io')
        self.port = int(os.environ.get('MQTT_PORT', '1883'))
        self.keepalive = int(os.environ.get('MQTT_KEEPALIVE', '60'))
        self.username = os.environ.get('MQTT_USERNAME')
        self.password = os.environ.get('MQTT_PASSWORD')
        self.topic_prefix = os.environ.get('MQTT_TOPIC_PREFIX', 'doorbell').strip('/')
        self.topic_cmd = f"{self.topic_prefix}/{self.device_id}/cmd"
        self.topic_status = f"{self.topic_prefix}/{self.device_id}/status"

        self._running = False

    def set_on_command(self, cb: Callable[[Dict], None]):
        self.on_command = cb

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.topic_cmd, qos=1)
            self.publish_status('online')
        else:
            logger.error(f"MQTT connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        if not self._running:
            return
        time.sleep(2)
        try:
            client.reconnect()
        except Exception:
            pass

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            return

        cmd = {
            'id': payload.get('id'),
            'type': payload.get('type'),
            'data': payload.get('data') or {}
        }
        if self.on_command:
            self.on_command(cmd)

    def connect(self):
        import paho.mqtt.client as mqtt

        client_id = f"{self.device_id}-{os.getpid()}"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        if (self.username or '').strip() and (self.password or '').strip():
            self.client.username_pw_set(self.username.strip(), self.password.strip())
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.connect(self.broker, self.port, self.keepalive)

    def publish_status(self, status: str):
        if not self.client:
            return
        msg = json.dumps({'device_id': self.device_id, 'status': status, 'ts': int(time.time())})
        try:
            self.client.publish(self.topic_status, msg, qos=0, retain=False)
        except Exception:
            pass

    def start(self, blocking: bool = False):
        if not self.client:
            self.connect()
        self._running = True
        if blocking:
            self.client.loop_forever()
        else:
            self.client.loop_start()

    def stop(self):
        self._running = False
        if self.client:
            try:
                self.publish_status('offline')
            except Exception:
                pass
            try:
                self.client.loop_stop()
            except Exception:
                pass
            try:
                self.client.disconnect()
            except Exception:
                pass

