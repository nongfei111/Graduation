#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端功能测试脚本 - 简化版
"""

import requests
import json

BASE_URL = "http://8.134.196.56:5000"

def test_cloud_functions():
    print("=" * 60)
    print("  CLAUDE 智能门铃 - 云端功能测试")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查...")
    r = requests.get(f"{BASE_URL}/api/health")
    print(f"    状态：{r.json().get('status')}")
    print(f"    服务器：{r.json().get('server')}")

    # 2. 注册测试用户
    print("\n[2] 注册用户...")
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": "test2026",
        "password": "test123456"
    })
    result = r.json()
    print(f"    结果：{'成功' if result.get('success') else '失败'}")
    if result.get('success'):
        token = result['access_token']
        user_id = result['user_id']
        print(f"    用户 ID: {user_id}")
        headers = {'Authorization': f'Bearer {token}'}

        # 3. 注册设备
        print("\n[3] 注册设备...")
        r = requests.post(f"{BASE_URL}/api/device/register", json={
            "device_id": "test_2026",
            "device_name": "测试门铃",
            "user_id": user_id,
            "device_type": "test",
            "firmware_version": "1.0.0"
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 4. 设备心跳
        print("\n[4] 设备心跳...")
        r = requests.post(f"{BASE_URL}/api/device/heartbeat", json={
            "device_id": "test_2026"
        }, headers=headers)
        result = r.json()
        print(f"    在线：{result.get('online')}")
        if result.get('command'):
            print(f"    有待执行命令：{result.get('command')}")

        # 5. 统计数据
        print("\n[5] 统计数据...")
        r = requests.get(f"{BASE_URL}/api/stats", headers=headers)
        stats = r.json().get('stats', {})
        print(f"    设备数：{stats.get('device_count')}")
        print(f"    今日访客：{stats.get('today_visitors')}")
        print(f"    未处理警报：{stats.get('unhandled_alerts')}")

        # 6. 远程开门
        print("\n[6] 远程开门...")
        r = requests.post(f"{BASE_URL}/api/control/unlock", json={
            "device_id": "test_2026"
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 7. 远程警报
        print("\n[7] 远程警报...")
        r = requests.post(f"{BASE_URL}/api/control/alert", json={
            "device_id": "test_2026",
            "message": "测试警报"
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 8. 远程语音
        print("\n[8] 远程语音...")
        r = requests.post(f"{BASE_URL}/api/control/speak", json={
            "device_id": "test_2026",
            "message": "您好，这是测试语音"
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 9. 远程抓拍
        print("\n[9] 远程抓拍...")
        r = requests.post(f"{BASE_URL}/api/control/snapshot", json={
            "device_id": "test_2026"
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 10. 上传访客
        print("\n[10] 上传访客记录...")
        r = requests.post(f"{BASE_URL}/api/visitor/upload", json={
            "device_id": "test_2026",
            "visitor_type": "family",
            "member_name": "测试用户",
            "confidence": 0.95
        }, headers=headers)
        print(f"    结果：{r.json()}")

        # 11. 获取访客列表
        print("\n[11] 获取访客列表...")
        r = requests.get(f"{BASE_URL}/api/visitor/list?limit=10", headers=headers)
        visitors = r.json().get('visitors', [])
        print(f"    访客数量：{len(visitors)}")
        for v in visitors[:3]:
            print(f"      - {v.get('visitor_type')}: {v.get('member_name')}")

        # 12. 获取设备状态
        print("\n[12] 获取设备状态...")
        r = requests.get(f"{BASE_URL}/api/device/status", headers=headers)
        result = r.json()
        devices = result.get('devices', [])
        print(f"    设备数量：{len(devices)}")
        if isinstance(devices, list):
            for d in devices:
                if isinstance(d, dict):
                    status = "在线" if d.get('is_online') else "离线"
                    print(f"      - {d.get('device_name')}: {status}")
        else:
            print(f"    设备数据格式异常：{devices}")

    else:
        print("    注册失败，可能是用户名已存在")
        # 尝试登录
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "test2026",
            "password": "test123456"
        })
        result = r.json()
        if result.get('success'):
            token = result['access_token']
            print(f"    登录成功，Token: {token[:50]}...")
        else:
            print(f"    登录也失败：{result.get('error')}")
            return

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_cloud_functions()
