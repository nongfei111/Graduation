#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预警系统模块
负责蜂鸣器控制、异常预警逻辑
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from config.settings import Config

logger = logging.getLogger(__name__)


class AlertSystem:
    """预警系统类"""

    def __init__(self, buzzer_pin: int = None):
        """
        初始化预警系统

        Args:
            buzzer_pin: 蜂鸣器 GPIO 引脚号
        """
        self.buzzer_pin = buzzer_pin or Config.BUZZER_PIN
        self.gpio_available = False

        # 预警配置
        self.warning_time = Config.UNKNOWN_VISITOR_WARNING_TIME  # 预警时间 (秒)
        self.warning_interval = Config.WARNING_INTERVAL  # 预警间隔

        # 状态
        self.is_armed = True  # 是否布防
        self.is_warning = False  # 是否正在预警
        self.unknown_visitor_start: Optional[datetime] = None
        self.last_warning_time: Optional[datetime] = None

        # 尝试初始化 GPIO
        self._init_gpio()

        logger.info(f"AlertSystem 初始化完成 (GPIO 引脚：{self.buzzer_pin})")

    def _init_gpio(self):
        """初始化 GPIO"""
        try:
            # 尝试导入 gpiozero (树莓派)
            from gpiozero import Buzzer
            self.buzzer = Buzzer(self.buzzer_pin)
            self.gpio_available = True
            logger.info("GPIO 初始化成功 (树莓派)")
        except ImportError:
            logger.warning("gpiozero 未安装，使用模拟模式")
            self.gpio_available = False
            self.buzzer = None
        except Exception as e:
            logger.warning(f"GPIO 初始化失败：{e}，使用模拟模式")
            self.gpio_available = False
            self.buzzer = None

    def start_monitoring(self):
        """开始监控陌生访客"""
        if not self.is_armed:
            return

        if self.unknown_visitor_start is None:
            self.unknown_visitor_start = datetime.now()
            logger.info("开始监控陌生访客")

    def stop_monitoring(self):
        """停止监控（访客离开）"""
        self.unknown_visitor_start = None
        self.is_warning = False
        self._turn_off_buzzer()
        logger.info("停止监控")

    def reset_monitoring(self):
        """重置监控计时器"""
        self.unknown_visitor_start = datetime.now()
        logger.info("重置监控计时器")

    def check_warning_condition(self) -> bool:
        """
        检查是否满足预警条件

        Returns:
            是否触发预警
        """
        if not self.is_armed:
            return False

        if self.unknown_visitor_start is None:
            return False

        # 检查是否超过预警时间
        elapsed = (datetime.now() - self.unknown_visitor_start).total_seconds()

        if elapsed >= self.warning_time:
            # 检查是否在预警间隔内
            if self.last_warning_time is None:
                return True

            time_since_last = (datetime.now() - self.last_warning_time).total_seconds()
            if time_since_last >= self.warning_interval:
                return True

        return False

    def trigger_warning(self):
        """触发预警"""
        if self.is_warning:
            return

        self.is_warning = True
        self.last_warning_time = datetime.now()

        logger.warning("触发预警！")
        print("⚠️  预警：陌生访客停留时间过长！")

        # 触发蜂鸣器
        self._activate_buzzer()

    def _activate_buzzer(self, duration: float = 2.0):
        """
        激活蜂鸣器

        Args:
            duration: 鸣响时长 (秒)
        """
        if self.gpio_available and self.buzzer:
            try:
                self.buzzer.on()
                time.sleep(duration)
                self.buzzer.off()
            except Exception as e:
                logger.error(f"蜂鸣器控制失败：{e}")
        else:
            # 模拟模式
            print(f"🔔 蜂鸣器鸣响 {duration} 秒 (模拟模式)")

    def _turn_off_buzzer(self):
        """关闭蜂鸣器"""
        if self.gpio_available and self.buzzer:
            try:
                self.buzzer.off()
            except Exception as e:
                logger.error(f"关闭蜂鸣器失败：{e}")
        else:
            print("🔕 蜂鸣器关闭")

    def arm(self):
        """布防"""
        self.is_armed = True
        logger.info("系统已布防")
        print("系统已布防")

    def disarm(self):
        """撤防"""
        self.is_armed = False
        self.is_warning = False
        self._turn_off_buzzer()
        logger.info("系统已撤防")
        print("系统已撤防")

    def get_status(self) -> dict:
        """获取系统状态"""
        return {
            'is_armed': self.is_armed,
            'is_warning': self.is_warning,
            'unknown_visitor_start': self.unknown_visitor_start.isoformat() if self.unknown_visitor_start else None,
            'gpio_available': self.gpio_available
        }

    def cleanup(self):
        """清理资源"""
        self._turn_off_buzzer()
        if self.gpio_available and self.buzzer:
            try:
                self.buzzer.close()
            except Exception as e:
                logger.error(f"清理蜂鸣器失败：{e}")
        logger.info("预警系统已清理")


if __name__ == "__main__":
    # 测试预警系统
    alert = AlertSystem()

    print(f"GPIO 可用：{alert.gpio_available}")
    print(f"系统状态：{alert.get_status()}")

    # 测试布防/撤防
    alert.arm()
    alert.start_monitoring()

    print("\n模拟陌生访客停留...")
    time.sleep(1)

    # 模拟超时
    alert.unknown_visitor_start = datetime.now() - timedelta(seconds=35)

    if alert.check_warning_condition():
        print("满足预警条件")
        alert.trigger_warning()

    alert.disarm()
    alert.cleanup()
