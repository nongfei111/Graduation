#!/usr/bin/env python3
"""
测试家庭列表接口脚本
用于验证 /api/family/list 接口是否正常工作
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_family_api():
    print("=" * 50)
    print("  测试家庭列表接口")
    print("=" * 50)

    # 测试账号
    username = "111"
    password = "123456"

    print(f"\n[1/3] 登录账号：{username}")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password}
    )

    print(f"登录响应状态码：{login_response.status_code}")

    if login_response.status_code != 200:
        print(f"登录失败：{login_response.text}")
        return False

    login_data = login_response.json()
    if not login_data.get("success"):
        print(f"登录失败：{login_data.get('error', '未知错误')}")
        return False

    # 获取 Token
    token = login_data["data"]["access_token"]
    print(f"登录成功！Token: {token[:50]}...")

    print(f"\n[2/3] 测试家庭列表接口")
    family_response = requests.get(
        f"{BASE_URL}/api/family/list",
        headers={"Authorization": f"Bearer {token}"}
    )

    print(f"家庭列表响应状态码：{family_response.status_code}")
    print(f"家庭列表响应内容：{json.dumps(family_response.json(), ensure_ascii=False, indent=2)}")

    if family_response.status_code == 200:
        family_data = family_response.json()
        if family_data.get("success") and family_data.get("data", {}).get("families"):
            print(f"\n✓ 家庭列表接口测试通过！")
            print(f"  家庭数量：{len(family_data['data']['families'])}")
            for family in family_data["data"]["families"]:
                print(f"  - 家庭 ID: {family['id']}, 名称：{family['name']}")
            return True
        elif family_data.get("success"):
            print(f"\n✓ 接口调用成功，但家庭列表为空")
            return True
        else:
            print(f"\n✗ 家庭列表接口返回错误：{family_data.get('error', '未知错误')}")
            return False
    else:
        print(f"\n✗ 家庭列表接口调用失败")
        return False

    print(f"\n[3/3] 测试完成")

if __name__ == "__main__":
    success = test_family_api()
    if success:
        print("\n" + "=" * 50)
        print("  测试通过！服务器代码已更新")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("  测试失败！请检查服务器代码")
        print("=" * 50)
