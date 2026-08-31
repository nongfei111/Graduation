#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android APP 通信测试接口
模拟 APP 向服务器发送各种请求，测试服务器响应
"""

import requests
import time
import json
from datetime import datetime

# 配置
BASE_URL = "http://8.134.196.56:5000"
USERNAME = "testuser"
PASSWORD = "test123"


class SmartDoorbellAppSimulator:
    """智能门铃 APP 模拟器"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token = None
        self.user_id = None

    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        print(f"\n[APP] 用户登录：{username}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={'username': username, 'password': password},
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                self.access_token = result['access_token']
                self.user_id = result['user_id']
                print(f"[APP] 登录成功！用户 ID: {self.user_id}")
                return True
            else:
                print(f"[APP] 登录失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 登录异常：{e}")
            return False

    def _get_headers(self) -> dict:
        """获取请求头"""
        if self.access_token:
            return {'Authorization': f'Bearer {self.access_token}'}
        return {}

    def get_device_status(self) -> dict:
        """获取设备状态"""
        print("\n[APP] 获取设备状态...")

        try:
            response = self.session.get(
                f"{self.base_url}/api/device/status",
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                devices = result.get('devices', [])
                print(f"[APP] 设备数量：{len(devices)}")
                for device in devices:
                    online_status = "在线" if device.get('is_online') else "离线"
                    print(f"  - {device.get('device_name')}: {online_status}")
                return result
            else:
                print(f"[APP] 获取失败：{result.get('error')}")
                return {}

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return {}

    def remote_unlock(self, device_id: str) -> bool:
        """远程开门"""
        print(f"\n[APP] 远程开门：{device_id}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/control/unlock",
                json={'device_id': device_id},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                print(f"[APP] 开门成功！命令 ID: {result.get('command_id')}")
                return True
            else:
                print(f"[APP] 开门失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return False

    def remote_alert(self, device_id: str, message: str) -> bool:
        """远程警报"""
        print(f"\n[APP] 远程警报：{device_id}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/control/alert",
                json={'device_id': device_id, 'message': message},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                print(f"[APP] 警报发送成功！命令 ID: {result.get('command_id')}")
                return True
            else:
                print(f"[APP] 警报失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return False

    def remote_speak(self, device_id: str, message: str) -> bool:
        """远程语音对讲"""
        print(f"\n[APP] 远程对讲：{device_id}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/control/speak",
                json={'device_id': device_id, 'message': message},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                print(f"[APP] 语音发送成功！命令 ID: {result.get('command_id')}")
                return True
            else:
                print(f"[APP] 语音失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return False

    def remote_snapshot(self, device_id: str) -> bool:
        """远程抓拍"""
        print(f"\n[APP] 远程抓拍：{device_id}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/control/snapshot",
                json={'device_id': device_id},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                print(f"[APP] 抓拍命令已发送！命令 ID: {result.get('command_id')}")
                return True
            else:
                print(f"[APP] 抓拍失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return False

    def get_visitor_list(self, limit: int = 10) -> list:
        """获取访客列表"""
        print(f"\n[APP] 获取访客列表...")

        try:
            response = self.session.get(
                f"{self.base_url}/api/visitor/list",
                params={'limit': limit},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                visitors = result.get('visitors', [])
                print(f"[APP] 访客数量：{len(visitors)}")

                for v in visitors[:5]:
                    v_type = "家人" if v.get('visitor_type') == 'family' else "陌生人"
                    name = v.get('member_name', '未知')
                    conf = v.get('confidence', 0)
                    time_str = v.get('created_at', '')
                    print(f"  - {v_type}: {name} (置信度：{conf:.2f}) - {time_str}")

                return visitors
            else:
                print(f"[APP] 获取失败：{result.get('error')}")
                return []

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return []

    def get_alert_list(self, limit: int = 10) -> list:
        """获取报警列表"""
        print(f"\n[APP] 获取报警列表...")

        try:
            response = self.session.get(
                f"{self.base_url}/api/alert/list",
                params={'limit': limit},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                alerts = result.get('alerts', [])
                print(f"[APP] 报警数量：{len(alerts)}")

                for a in alerts[:5]:
                    reason = a.get('reason', '未知')
                    handled = "已处理" if a.get('handled') else "未处理"
                    time_str = a.get('created_at', '')
                    print(f"  - {reason} ({handled}) - {time_str}")

                return alerts
            else:
                print(f"[APP] 获取失败：{result.get('error')}")
                return []

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return []

    def handle_alert(self, alert_id: int, handled: bool = True) -> bool:
        """处理报警"""
        print(f"\n[APP] 处理报警：ID={alert_id}")

        try:
            response = self.session.post(
                f"{self.base_url}/api/alert/handle",
                json={'alert_id': alert_id, 'handled': handled},
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                print(f"[APP] 处理成功！")
                return True
            else:
                print(f"[APP] 处理失败：{result.get('error')}")
                return False

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return False

    def get_statistics(self) -> dict:
        """获取统计数据"""
        print(f"\n[APP] 获取统计数据...")

        try:
            response = self.session.get(
                f"{self.base_url}/api/stats",
                headers=self._get_headers(),
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                stats = result.get('stats', {})
                print(f"[APP] 统计数据:")
                print(f"  - 设备数量：{stats.get('device_count', 0)}")
                print(f"  - 今日访客：{stats.get('today_visitors', 0)}")
                print(f"  - 今日开门：{stats.get('today_access', 0)}")
                print(f"  - 未处理警报：{stats.get('unhandled_alerts', 0)}")
                return stats
            else:
                print(f"[APP] 获取失败：{result.get('error')}")
                return {}

        except Exception as e:
            print(f"[APP] 异常：{e}")
            return {}


def run_app_simulation():
    """运行 APP 模拟测试"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     CLAUDE 智能门铃系统 - Android APP 模拟器                 ║
    ║     模拟 APP 向服务器发送请求，测试远程控制功能             ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # 创建 APP 模拟器
    app = SmartDoorbellAppSimulator(BASE_URL)

    # 1. 登录
    if not app.login(USERNAME, PASSWORD):
        print("\n[错误] 登录失败，无法继续测试")
        return

    # 2. 获取统计数据
    app.get_statistics()

    # 3. 获取设备状态
    device_info = app.get_device_status()

    # 获取第一个设备 ID 用于测试
    devices = device_info.get('devices', [])
    if not devices:
        print("\n[错误] 没有可用设备")
        return

    device_id = devices[0].get('device_id')
    print(f"\n[测试] 使用设备：{device_id}")

    # 4. 远程开门测试
    print("\n--- 远程开门测试 ---")
    app.remote_unlock(device_id)
    time.sleep(1)

    # 5. 远程警报测试
    print("\n--- 远程警报测试 ---")
    app.remote_alert(device_id, "警告！请勿靠近！")
    time.sleep(1)

    # 6. 远程语音测试
    print("\n--- 远程语音测试 ---")
    app.remote_speak(device_id, "您好，请问有什么事吗？")
    time.sleep(1)

    # 7. 远程抓拍测试
    print("\n--- 远程抓拍测试 ---")
    app.remote_snapshot(device_id)
    time.sleep(1)

    # 8. 获取访客列表
    print("\n--- 访客列表 ---")
    app.get_visitor_list(limit=5)

    # 9. 获取报警列表
    print("\n--- 报警列表 ---")
    alerts = app.get_alert_list(limit=5)

    # 10. 处理一个报警（如果有）
    if alerts:
        print("\n--- 处理报警 ---")
        app.handle_alert(alerts[0].get('id'), handled=True)

    # 11. 再次获取统计数据
    print("\n--- 最终统计 ---")
    app.get_statistics()

    print("\n[完成] APP 模拟测试完成！")


def interactive_mode():
    """交互模式"""
    print("\n进入交互模式...")

    app = SmartDoorbellAppSimulator(BASE_URL)

    if not app.login(USERNAME, PASSWORD):
        print("登录失败")
        return

    device_id = None
    device_info = app.get_device_status()
    devices = device_info.get('devices', [])
    if devices:
        device_id = devices[0].get('device_id')

    while True:
        print("\n" + "=" * 40)
        print("  智能门铃 APP 控制台")
        print("=" * 40)
        print("  1. 远程开门")
        print("  2. 远程警报")
        print("  3. 远程语音")
        print("  4. 远程抓拍")
        print("  5. 查看访客列表")
        print("  6. 查看报警列表")
        print("  7. 查看统计数据")
        print("  0. 退出")
        print("=" * 40)

        choice = input("请选择操作 (0-7): ").strip()

        if choice == '0':
            print("退出控制台")
            break
        elif choice == '1':
            if device_id:
                app.remote_unlock(device_id)
        elif choice == '2':
            if device_id:
                msg = input("警报内容：")
                app.remote_alert(device_id, msg or "警告！")
        elif choice == '3':
            if device_id:
                msg = input("语音内容：")
                app.remote_speak(device_id, msg or "您好")
        elif choice == '4':
            if device_id:
                app.remote_snapshot(device_id)
        elif choice == '5':
            app.get_visitor_list()
        elif choice == '6':
            app.get_alert_list()
        elif choice == '7':
            app.get_statistics()
        else:
            print("无效选择")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '-i':
        # 交互模式
        interactive_mode()
    else:
        # 自动测试模式
        run_app_simulation()
