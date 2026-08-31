#!/bin/bash
# CLAUDE 智能门铃 - 完整功能测试脚本

echo "========================================="
echo "  CLAUDE 智能门铃 - 云端功能测试"
echo "========================================="

BASE_URL="http://localhost:5000"

# 1. 健康检查
echo ""
echo "[测试 1] 健康检查..."
curl -s "$BASE_URL/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print('状态:', d.get('status'), '| 服务器:', d.get('server'))"

# 2. 登录
echo ""
echo "[测试 2] 用户登录..."
echo "请输入用户名 (默认 admin): "
read -r USERNAME
USERNAME=${USERNAME:-admin}

echo "请输入密码: "
read -sr PASSWORD
echo ""

LOGIN_RESULT=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

echo "$LOGIN_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('登录:', '成功' if d.get('success') else '失败:', d.get('error') or d.get('user_id'))"

TOKEN=$(echo "$LOGIN_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token', ''))")

if [ -z "$TOKEN" ]; then
    echo "登录失败，无法继续测试"
    exit 1
fi

# 3. 设备状态
echo ""
echo "[测试 3] 设备状态..."
curl -s "$BASE_URL/api/device/status" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); devs=d.get('devices',[]); print('设备数:', len(devs)); [print(f'  - {x.get(\"device_name\")}: 在线={x.get(\"is_online\")}') for x in devs]"

# 4. 统计数据
echo ""
echo "[测试 4] 统计数据..."
curl -s "$BASE_URL/api/stats" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); s=d.get('stats',{}); print('设备数:', s.get('device_count'), '| 今日访客:', s.get('today_visitors') or 0)"

# 5. 注册设备（如果没有设备）
echo ""
echo "[测试 5] 注册设备..."
DEVICE_RESULT=$(curl -s -X POST "$BASE_URL/api/device/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device","device_name":"云端测试设备","user_id":1,"device_type":"test","firmware_version":"1.0.0"}')

echo "$DEVICE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('注册:', '成功' if d.get('success') else '失败:', d.get('message') or d.get('error'))"

# 6. 设备心跳
echo ""
echo "[测试 6] 设备心跳..."
curl -s -X POST "$BASE_URL/api/device/heartbeat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('心跳:', '成功' if d.get('success') else '失败', '| 在线:', d.get('online'))"

# 7. 远程开门
echo ""
echo "[测试 7] 远程开门..."
curl -s -X POST "$BASE_URL/api/control/unlock" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('开门:', d.get('message') or d.get('error'))"

# 8. 远程警报
echo ""
echo "[测试 8] 远程警报..."
curl -s -X POST "$BASE_URL/api/control/alert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device","message":"测试警报"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('警报:', '成功' if d.get('success') else d.get('error'))"

# 9. 远程语音
echo ""
echo "[测试 9] 远程语音..."
curl -s -X POST "$BASE_URL/api/control/speak" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device","message":"您好，这是测试语音"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('语音:', '成功' if d.get('success') else d.get('error'))"

# 10. 远程抓拍
echo ""
echo "[测试 10] 远程抓拍..."
curl -s -X POST "$BASE_URL/api/control/snapshot" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('抓拍:', '成功' if d.get('success') else d.get('error'))"

# 11. 上传访客
echo ""
echo "[测试 11] 上传访客记录..."
curl -s -X POST "$BASE_URL/api/visitor/upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_id":"cloud_test_device","visitor_type":"family","member_name":"测试用户","confidence":0.95}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('上传:', '成功，ID=' + str(d.get('visitor_id')) if d.get('success') else d.get('error'))"

# 12. 访客列表
echo ""
echo "[测试 12] 获取访客列表..."
curl -s "$BASE_URL/api/visitor/list?limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); vlist=d.get('visitors',[]); print('访客数:', len(vlist)); [print(f'  - {v.get(\"visitor_type\")}: {v.get(\"member_name\")}') for v in vlist[:3]]"

echo ""
echo "========================================="
echo "  测试完成"
echo "========================================="
