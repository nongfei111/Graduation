#!/usr/bin/env python3
"""
测试统计 API
"""

import requests

BASE_URL = "http://8.134.196.56:5000"

# 第一步：登录获取 token
print("=" * 50)
print("测试统计 API")
print("=" * 50)

username = input("请输入用户名：")
password = input("请输入密码：")

print(f"\n[1/3] 登录：{username}")
login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": username,
    "password": password
})

print(f"登录响应状态码：{login_response.status_code}")
print(f"登录响应内容：{login_response.text}")

if login_response.status_code != 200:
    print("登录失败！")
    exit(1)

login_data = login_response.json()
if not login_data.get('success'):
    print("登录失败！")
    exit(1)

# 兼容两种响应格式
access_token = None
if 'data' in login_data and 'access_token' in login_data['data']:
    access_token = login_data['data']['access_token']
elif 'access_token' in login_data:
    access_token = login_data['access_token']

if not access_token:
    print("无法获取 Token")
    exit(1)

print(f"\n登录成功！Token: {access_token[:20]}...")

# 第二步：获取家庭列表
print(f"\n[2/3] 获取家庭列表")
headers = {"Authorization": f"Bearer {access_token}"}
family_response = requests.get(f"{BASE_URL}/api/family/list", headers=headers)

print(f"家庭列表响应状态码：{family_response.status_code}")
print(f"家庭列表响应内容：{family_response.text}")

# 第三步：测试统计 API
print(f"\n[3/3] 测试统计 API")
stats_response = requests.get(f"{BASE_URL}/api/stats", headers=headers)

print(f"统计 API 响应状态码：{stats_response.status_code}")
print(f"统计 API 响应内容：{stats_response.text}")

if stats_response.status_code == 200:
    stats_data = stats_response.json()
    if stats_data.get('success'):
        print("\n✓ 统计 API 测试通过！")
        if 'data' in stats_data:
            print(f"  数据格式：正确 (包含 data 字段)")
            summary = stats_data['data'].get('summary', {})
            print(f"  今日访客：{summary.get('today_visitors', 0)}")
            print(f"  总访客：{summary.get('total_visitors', 0)}")
            print(f"  成员访客：{summary.get('member_visits', 0)}")
            print(f"  陌生访客：{summary.get('stranger_visits', 0)}")
            print(f"  报警数量：{summary.get('alert_count', 0)}")
        else:
            print(f"\n  警告：响应格式不正确，缺少 data 字段")
    else:
        print("\n  统计 API 返回 success=false")
else:
    print(f"\n  统计 API 请求失败：{stats_response.status_code}")

print("\n" + "=" * 50)
