"""
CLAUDE 智能门铃系统 - 配置管理模块
"""

import os
import json
from typing import Any, Optional


class Config:
    """
    系统配置管理类
    从 JSON 文件加载配置，支持运行时访问
    """

    _instance = None
    _config = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置"""
        if not self._config:
            self.load()

    def load(self, config_path: str = "config/settings.json") -> bool:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            是否加载成功
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                print(f"配置已加载：{config_path}")
                return True
            else:
                print(f"配置文件不存在：{config_path}，使用默认配置")
                self._config = self._get_default_config()
                return False
        except Exception as e:
            print(f"加载配置失败：{e}")
            self._config = self._get_default_config()
            return False

    def save(self, config_path: str = "config/settings.json") -> bool:
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            print(f"配置已保存：{config_path}")
            return True
        except Exception as e:
            print(f"保存配置失败：{e}")
            return False

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的路径）

        Args:
            key_path: 配置键路径，如 "camera.width"
            default: 默认值

        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any) -> bool:
        """
        设置配置值

        Args:
            key_path: 配置键路径
            value: 配置值

        Returns:
            是否设置成功
        """
        keys = key_path.split('.')
        config = self._config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value
        return True

    def update(self, config_dict: dict):
        """批量更新配置"""
        self._update_nested(self._config, config_dict)

    def _update_nested(self, base: dict, update: dict):
        """递归更新嵌套字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._update_nested(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _get_default_config() -> dict:
        """获取默认配置"""
        return {
            "system": {
                "name": "CLAUDE 智能门铃系统",
                "version": "1.0.0",
                "device": "Raspberry Pi 5"
            },
            "camera": {
                "width": 1280,
                "height": 720,
                "fps": 30
            },
            "face_detection": {
                "confidence_threshold": 0.7,
                "input_size": [320, 240]
            },
            "face_recognition": {
                "threshold": 0.6
            },
            "alert": {
                "stranger_timeout": 30
            },
            "members": {
                "max_count": 20
            }
        }

    def to_dict(self) -> dict:
        """返回配置字典"""
        return dict(self._config)
