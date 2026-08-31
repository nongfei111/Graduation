#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备端与云端通信完整测试脚本
测试心跳、命令接收、访客上传、远程控制等功能
"""

import os
import sys
import time
import logging
import base64
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Windows 控制台兼容性 - 使用 ASCII 符号
OK = "[OK]"    # 替代 ✓
FAIL = "[FAIL]" # 替代 ✗

# 确保 Windows 控制台输出 UTF-8
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')

# 配置
CLOUD_HOST = os.environ.get('CLOUD_HOST', '8.134.196.56')
CLOUD_PORT = int(os.environ.get('CLOUD_PORT', '5000'))
DEVICE_ID = os.environ.get('DEVICE_ID', 'doorbell_test_001')
USERNAME = os.environ.get('CLOUD_USERNAME', 'testuser')
PASSWORD = os.environ.get('CLOUD_PASSWORD', 'test123')

BASE_URL = f"http://{CLOUD_HOST}:{CLOUD_PORT}"


def print_section(title):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_health_check():
    """测试 1: 健康检查"""
    print_section("测试 1: 健康检查")

    import requests

    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        result = response.json()

        if result.get('status') == 'ok':
            print(f"{OK} 健康检查通过")
            print(f"    服务器时间：{result.get('timestamp')}")
            print(f"    服务器名称：{result.get('server')}")
            return True
        else:
            print(f"{FAIL} 健康检查失败：{result}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"{FAIL} 无法连接到服务器 {BASE_URL}")
        print(f"    请检查：")
        print(f"    1. 服务器是否运行")
        print(f"    2. 端口 5000 是否开放")
        print(f"    3. 防火墙设置")
        return False
    except Exception as e:
        print(f"{FAIL} 测试失败：{e}")
        return False


def test_user_login():
    """测试 2: 用户登录"""
    print_section("测试 2: 用户登录")

    import requests

    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={'username': USERNAME, 'password': PASSWORD},
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            token = result.get('access_token', '')
            user_id = result.get('user_id')
            print(f"[OK] 登录成功")
            print(f"    用户 ID: {user_id}")
            print(f"    Token: {token[:50]}...")
            return token
        else:
            print(f"[FAIL] 登录失败：{result.get('error')}")
            print(f"    请检查用户名和密码是否正确")
            return None

    except Exception as e:
        print(f"[FAIL] 登录异常：{e}")
        return None


def test_device_registration(token):
    """测试 3: 设备注册"""
    print_section("测试 3: 设备注册")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.post(
            f"{BASE_URL}/api/device/register",
            json={
                'device_id': DEVICE_ID,
                'device_name': '测试门铃设备',
                'user_id': 1,
                'device_type': 'raspberry_pi_4b',
                'firmware_version': '1.0.0'
            },
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            print(f"[OK] 设备注册成功")
            print(f"    设备 ID: {DEVICE_ID}")
            print(f"    消息：{result.get('message')}")
            return True
        else:
            print(f"[FAIL] 设备注册失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 注册异常：{e}")
        return False


def test_device_heartbeat(token):
    """测试 4: 设备心跳"""
    print_section("测试 4: 设备心跳")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.post(
            f"{BASE_URL}/api/device/heartbeat",
            json={'device_id': DEVICE_ID},
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            print(f"[OK] 心跳发送成功")
            print(f"    在线状态：{result.get('online')}")

            # 检查是否有远程命令
            command = result.get('command')
            if command:
                print(f"    [!] 收到远程命令:")
                print(f"        命令 ID: {command.get('id')}")
                print(f"        命令类型：{command.get('type')}")
                print(f"        命令数据：{command.get('data')}")
            else:
                print(f"    暂无远程命令")
            return True
        else:
            print(f"[FAIL] 心跳失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 心跳异常：{e}")
        return False


def test_visitor_upload(token):
    """测试 5: 访客上传"""
    print_section("测试 5: 访客上传")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    # 创建测试图片（简单的 1x1 像素 PNG）
    test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    test_cases = [
        {
            'name': '家庭成员',
            'data': {
                'device_id': DEVICE_ID,
                'visitor_type': 'family',
                'member_name': '张三',
                'confidence': 0.95,
                'photo_data': test_image_base64
            }
        },
        {
            'name': '陌生访客',
            'data': {
                'device_id': DEVICE_ID,
                'visitor_type': 'stranger',
                'confidence': 0.75,
                'photo_data': test_image_base64
            }
        }
    ]

    all_passed = True

    for test in test_cases:
        try:
            response = requests.post(
                f"{BASE_URL}/api/visitor/upload",
                json=test['data'],
                headers=headers,
                timeout=30
            )
            result = response.json()

            if result.get('success'):
                print(f"[OK] {test['name']}上传成功")
                print(f"    访客 ID: {result.get('visitor_id')}")
            else:
                print(f"[FAIL] {test['name']}上传失败：{result.get('error')}")
                all_passed = False

        except Exception as e:
            print(f"[FAIL] {test['name']}上传异常：{e}")
            all_passed = False

    return all_passed


def test_get_visitor_list(token):
    """测试 6: 获取访客列表"""
    print_section("测试 6: 获取访客列表")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(
            f"{BASE_URL}/api/visitor/list",
            params={'limit': 10},
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            visitors = result.get('visitors', [])
            print(f"[OK] 获取访客列表成功")
            print(f"    访客数量：{len(visitors)}")

            if visitors:
                print(f"    最近访客:")
                for v in visitors[:3]:
                    visitor_type = '家人' if v.get('visitor_type') == 'family' else '陌生人'
                    name = v.get('member_name', '未知')
                    print(f"      - {visitor_type}: {name} ({v.get('created_at')})")
            return True
        else:
            print(f"[FAIL] 获取访客列表失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 获取列表异常：{e}")
        return False


def test_remote_unlock(token):
    """测试 7: 远程开门"""
    print_section("测试 7: 远程开门")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.post(
            f"{BASE_URL}/api/control/unlock",
            json={'device_id': DEVICE_ID},
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            print(f"[OK] 远程开门命令已发送")
            print(f"    命令 ID: {result.get('command_id')}")
            print(f"    消息：{result.get('message')}")
            return True
        else:
            print(f"[FAIL] 远程开门失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 远程开门异常：{e}")
        return False


def test_remote_alert(token):
    """测试 8: 远程警报"""
    print_section("测试 8: 远程警报")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.post(
            f"{BASE_URL}/api/control/alert",
            json={
                'device_id': DEVICE_ID,
                'message': '测试警报！请勿靠近！'
            },
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            print(f"[OK] 远程警报命令已发送")
            print(f"    命令 ID: {result.get('command_id')}")
            return True
        else:
            print(f"[FAIL] 远程警报失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 远程警报异常：{e}")
        return False


def test_get_statistics(token):
    """测试 9: 获取统计数据"""
    print_section("测试 9: 获取统计数据")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(
            f"{BASE_URL}/api/stats",
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            stats = result.get('stats', {})
            print(f"[OK] 获取统计数据成功")
            print(f"    设备数量：{stats.get('device_count', 0)}")
            print(f"    今日访客：{stats.get('today_visitors', 0)}")
            print(f"    今日开门：{stats.get('today_access', 0)}")
            print(f"    未处理警报：{stats.get('unhandled_alerts', 0)}")
            return True
        else:
            print(f"[FAIL] 获取统计数据失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 获取统计异常：{e}")
        return False


def test_device_status(token):
    """测试 10: 获取设备状态"""
    print_section("测试 10: 获取设备状态")

    import requests

    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(
            f"{BASE_URL}/api/device/status",
            headers=headers,
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            devices = result.get('devices', [])
            print(f"[OK] 获取设备状态成功")
            print(f"    设备数量：{len(devices)}")

            for device in devices:
                print(f"    设备信息:")
                print(f"      - ID: {device.get('device_id')}")
                print(f"      - 名称：{device.get('device_name')}")
                print(f"      - 类型：{device.get('device_type')}")
                print(f"      - 在线：{'是' if device.get('is_online') else '否'}")
                print(f"      - 最后心跳：{device.get('last_heartbeat')}")
            return True
        else:
            print(f"[FAIL] 获取设备状态失败：{result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] 获取设备状态异常：{e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print_section("CLAUDE 智能门铃系统 - 云端通信测试")
    print(f"服务器地址：{BASE_URL}")
    print(f"设备 ID: {DEVICE_ID}")
    print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        '健康检查': False,
        '用户登录': False,
        '设备注册': False,
        '设备心跳': False,
        '访客上传': False,
        '获取访客列表': False,
        '远程开门': False,
        '远程警报': False,
        '获取统计数据': False,
        '获取设备状态': False
    }

    token = None

    # 测试 1: 健康检查
    if test_health_check():
        results['健康检查'] = True

    # 测试 2: 用户登录
    token = test_user_login()
    if token:
        results['用户登录'] = True

        # 测试 3: 设备注册
        if test_device_registration(token):
            results['设备注册'] = True

        # 测试 4: 设备心跳
        if test_device_heartbeat(token):
            results['设备心跳'] = True

        # 测试 5: 访客上传
        if test_visitor_upload(token):
            results['访客上传'] = True

        # 测试 6: 获取访客列表
        if test_get_visitor_list(token):
            results['获取访客列表'] = True

        # 测试 7: 远程开门
        if test_remote_unlock(token):
            results['远程开门'] = True

        # 测试 8: 远程警报
        if test_remote_alert(token):
            results['远程警报'] = True

        # 测试 9: 获取统计数据
        if test_get_statistics(token):
            results['获取统计数据'] = True

        # 测试 10: 获取设备状态
        if test_device_status(token):
            results['获取设备状态'] = True

    # 打印测试结果汇总
    print_section("测试结果汇总")

    passed = 0
    total = len(results)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1

    print(f"\n总计：{passed}/{total} 测试通过")
    print(f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return passed == total


def continuous_heartbeat_test(token, duration=60):
    """持续心跳测试"""
    print_section(f"持续心跳测试 ({duration}秒)")

    import requests

    headers = {'Authorization': f'Bearer {token}'}
    interval = 5  # 每 5 秒发送一次心跳
    start_time = time.time()
    heartbeat_count = 0

    while time.time() - start_time < duration:
        try:
            response = requests.post(
                f"{BASE_URL}/api/device/heartbeat",
                json={'device_id': DEVICE_ID},
                headers=headers,
                timeout=10
            )
            result = response.json()

            if result.get('success'):
                heartbeat_count += 1
                command = result.get('command')

                if command:
                    print(f"[心跳 {heartbeat_count}] 收到命令：{command.get('type')}")
                else:
                    print(f"[心跳 {heartbeat_count}] 正常")
            else:
                print(f"[心跳 {heartbeat_count}] 失败：{result.get('error')}")

        except Exception as e:
            print(f"[心跳] 异常：{e}")

        time.sleep(interval)

    print(f"\n心跳测试完成：共发送 {heartbeat_count} 次心跳")
    return heartbeat_count


if __name__ == "__main__":
    import requests

    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     CLAUDE 智能门铃系统 - 云端通信测试工具                 ║
    ║     测试项目：健康检查、登录、注册、心跳、访客上传等       ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # 运行所有测试
    success = run_all_tests()

    # 询问是否进行持续心跳测试
    print_section("是否进行持续心跳测试？")
    print("该测试将持续发送心跳 60 秒，模拟设备运行状态")

    try:
        choice = input("\n是否继续？(y/n): ").strip().lower()
        if choice == 'y':
            # 需要先登录获取 token
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={'username': USERNAME, 'password': PASSWORD},
                timeout=10
            )
            result = response.json()
            token = result.get('access_token')

            if token:
                continuous_heartbeat_test(token, duration=60)
            else:
                print("无法获取 Token，跳过心跳测试")
    except KeyboardInterrupt:
        print("\n测试被中断")
    except Exception as e:
        print(f"\n错误：{e}")

    print("\n感谢使用测试工具！")
