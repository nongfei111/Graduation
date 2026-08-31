#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云服务器配置模块
配置阿里云服务器连接参数
"""

import os
import json
from typing import Optional


class CloudConfig:
    """云服务器配置类"""

    # ==================== 阿里云服务器配置 ====================

    # 阿里云 ECS 服务器信息
    SERVER_HOST = "8.134.196.56"        # 公网 IP
    SERVER_PORT = 5000                   # Flask 服务端口

    # 实例信息
    INSTANCE_ID = "7a518455b93b47cca76ffbe076ae2112"
    INSTANCE_NAME = "Alibaba Cloud Linux-vmgc"

    # 地域信息
    REGION = "华南 3（广州）"

    # 镜像信息
    MIRROR = "Alibaba Cloud Linux 3.21.04"

    # IP 地址
    PUBLIC_IP = "8.134.196.56"
    PRIVATE_IP = "172.19.47.170"

    # 到期时间
    EXPIRE_DATE = "2026 年 10 月 11 日 00:00:00"

    # ==================== MQTT 配置 ====================

    # 公共 MQTT Broker
    MQTT_BROKER = "broker.emqx.io"
    MQTT_PORT = 1883
    MQTT_KEEPALIVE = 60

    # MQTT 主题
    TOPIC_UNLOCK = "doorbell/unlock"      # 开锁指令
    TOPIC_STATUS = "doorbell/status"      # 设备状态
    TOPIC_VISITOR = "doorbell/visitor"    # 访客通知
    TOPIC_ALERT = "doorbell/alert"        # 报警通知

    # ==================== API 接口配置 ====================

    @classmethod
    def get_base_url(cls) -> str:
        """获取 API 基础 URL"""
        return f"http://{cls.SERVER_HOST}:{cls.SERVER_PORT}/api"

    @classmethod
    def get_mqtt_config(cls) -> dict:
        """获取 MQTT 配置"""
        return {
            "broker": cls.MQTT_BROKER,
            "port": cls.MQTT_PORT,
            "keepalive": cls.MQTT_KEEPALIVE,
            "topics": {
                "unlock": cls.TOPIC_UNLOCK,
                "status": cls.TOPIC_STATUS,
                "visitor": cls.TOPIC_VISITOR,
                "alert": cls.TOPIC_ALERT
            }
        }

    @classmethod
    def get_server_info(cls) -> dict:
        """获取服务器信息"""
        return {
            "instance_id": cls.INSTANCE_ID,
            "instance_name": cls.INSTANCE_NAME,
            "region": cls.REGION,
            "mirror": cls.MIRROR,
            "public_ip": cls.PUBLIC_IP,
            "private_ip": cls.PRIVATE_IP,
            "expire_date": cls.EXPIRE_DATE,
            "status": "运行中"
        }


class NetworkConfig:
    """网络配置类 - 从配置文件加载"""

    _config_cache: Optional[dict] = None

    @classmethod
    def _load_config(cls):
        """加载配置文件"""
        if cls._config_cache is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "settings.json"
            )
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cls._config_cache = json.load(f)
            except Exception as e:
                print(f"加载配置文件失败：{e}，使用默认配置")
                cls._config_cache = {}

    @classmethod
    def get(cls, key: str, default=None):
        """获取配置值"""
        cls._load_config()
        keys = key.split('.')
        value = cls._config_cache
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @classmethod
    def get_network_config(cls) -> dict:
        """获取网络配置"""
        return cls.get('network', {})

    @classmethod
    def get_motor_config(cls) -> dict:
        """获取电机配置"""
        return cls.get('motor', {})


# 打印服务器信息
if __name__ == "__main__":
    print("=" * 60)
    print("CLAUDE 智能门铃 - 云服务器配置")
    print("=" * 60)

    info = CloudConfig.get_server_info()
    for key, value in info.items():
        print(f"{key}: {value}")

    print("\n" + "=" * 60)
    print("MQTT 配置")
    print("=" * 60)
    mqtt_config = CloudConfig.get_mqtt_config()
    print(f"Broker: {mqtt_config['broker']}:{mqtt_config['port']}")
    print(f"Keepalive: {mqtt_config['keepalive']}秒")
    print("\n主题列表:")
    for topic_name, topic in mqtt_config['topics'].items():
        print(f"  - {topic_name}: {topic}")

    print("\n" + "=" * 60)
    print("API 接口")
    print("=" * 60)
    print(f"Base URL: {CloudConfig.get_base_url()}")
