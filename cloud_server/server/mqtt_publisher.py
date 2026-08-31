import os
import json
import logging
from typing import Dict, Optional


logger = logging.getLogger(__name__)


def publish_command(device_id: str, command: Dict) -> bool:
    # 功能定位索引（远程控制命令投递）：
    # - 由 app.py 的 /api/control/* 接口创建命令后调用本函数
    # - MQTT Topic 约定：{MQTT_TOPIC_PREFIX}/{device_id}/cmd
    # - 消息格式：{id,type,data}，设备端在 src/sync/mqtt_commands.py 订阅并转交 RemoteController 执行
    broker = os.environ.get('MQTT_BROKER', 'broker.emqx.io')
    port = int(os.environ.get('MQTT_PORT', '1883'))
    username = os.environ.get('MQTT_USERNAME')
    password = os.environ.get('MQTT_PASSWORD', '')
    topic_prefix = os.environ.get('MQTT_TOPIC_PREFIX', 'doorbell').strip('/')
    topic = f"{topic_prefix}/{device_id}/cmd"

    try:
        import paho.mqtt.client as mqtt
    except Exception:
        return False

    payload = json.dumps({
        'id': command.get('id'),
        'type': command.get('type'),
        'data': command.get('data') or {}
    })

    client = mqtt.Client(client_id=f"cloud_{device_id}", clean_session=True)
    if username:
        client.username_pw_set(username, password)

    try:
        client.connect(broker, port, keepalive=30)
        client.loop_start()
        info = client.publish(topic, payload, qos=1, retain=False)
        info.wait_for_publish()
        client.loop_stop()
        client.disconnect()
        return True
    except Exception as e:
        logger.error(f"MQTT 发布失败：{e}")
        try:
            client.loop_stop()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass
        return False

