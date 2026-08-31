#!/bin/bash
# CLAUDE 智能门铃 - 完整功能测试脚本

echo "========================================="
echo "  CLAUDE 智能门铃 - 云端功能测试"
echo "========================================="

# 登录信息
USERNAME="admin"
PASSWORD="admin123456"
BASE_URL="http://localhost:5000"

# 1. 登录获取 Token
echo ""
echo "[1/8] 用户登录..."
LOGIN_RESULT=$(/home/smart_doorbell/venv/bin/python3 << PY
import requests
r = requests.post("$BASE_URL/api/auth/login", json={"username": "$USERNAME", "password": "$PASSWORD"})
data = r.json()
if data.get('success'):
    print(data.get('access_token'))
else:
    print('ERROR:' + str(data.get('error')))
PY
)

if [[ "$LOGIN_RESULT" == ERROR:* ]]; then
    echo "登录失败：${LOGIN_RESULT#ERROR:}"
    exit 1
fi

ACCESS_TOKEN="$LOGIN_RESULT"
echo "登录成功！Token: ${ACCESS_TOKEN:0:50}..."

# 2. 注册设备
echo ""
echo "[2/8] 注册设备..."
curl -s -X POST "$BASE_URL/api/device/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\",\"device_name\":\"我家门铃\",\"user_id\":8,\"device_type\":\"raspberry_pi_4b\",\"firmware_version\":\"1.0.0\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('设备注册:', d.get('message') or d.get('error'))"

# 3. 设备状态
echo ""
echo "[3/8] 设备状态..."
curl -s "$BASE_URL/api/device/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); devs=d.get('devices',[]); print('设备数量:', len(devs)); [print(f'  - {x.get(\"device_id\")}: {x.get(\"device_name\")}') for x in devs]"

# 4. 远程开门
echo ""
echo "[4/8] 远程开门..."
curl -s -X POST "$BASE_URL/api/control/unlock" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('开门:', d.get('message') or d.get('error'))"

# 5. 远程警报
echo ""
echo "[5/8] 远程警报..."
curl -s -X POST "$BASE_URL/api/control/alert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\",\"message\":\"测试警报\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('警报:', '成功' if d.get('success') else d.get('error'))"

# 6. 远程语音
echo ""
echo "[6/8] 远程语音..."
curl -s -X POST "$BASE_URL/api/control/speak" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\",\"message\":\"您好，请问有什么事？\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('语音:', '成功' if d.get('success') else d.get('error'))"

# 7. 远程抓拍
echo ""
echo "[7/8] 远程抓拍..."
curl -s -X POST "$BASE_URL/api/control/snapshot" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('抓拍:', '成功' if d.get('success') else d.get('error'))"

# 8. 上传访客
echo ""
echo "[8/8] 上传访客记录..."
curl -s -X POST "$BASE_URL/api/visitor/upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"device_id\":\"doorbell_001\",\"visitor_type\":\"family\",\"member_name\":\"张三\",\"confidence\":0.95}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('上传:', '成功，ID=' + str(d.get('visitor_id')) if d.get('success') else d.get('error'))"

# 统计
echo ""
echo "========================================="
echo "  统计数据"
echo "========================================="
curl -s "$BASE_URL/api/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('stats',{}); print('设备数:', s.get('device_count')); print('今日访客:', s.get('today_visitors') or 0); print('未处理警报:', s.get('unhandled_alerts') or 0)"

echo ""
echo "========================================="
echo "  测试完成"
echo "========================================="
echo ""
echo "登录信息已保存："
echo "  用户名：$USERNAME"
echo "  密码：$PASSWORD"
echo "  Token: ${ACCESS_TOKEN:0:60}..."
