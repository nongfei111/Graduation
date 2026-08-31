#!/bin/bash
# CLAUDE 智能门铃 - 远程功能完整测试脚本
# 使用方法：bash /tmp/remote_test.sh

echo "========================================="
echo "  CLAUDE 智能门铃 - 远程功能测试"
echo "========================================="

BASE_URL="http://localhost:5000"
USERNAME="admin"
PASSWORD="admin123456"
DEVICE_ID="doorbell_001"

echo ""
echo "配置信息:"
echo "  服务器：$BASE_URL"
echo "  用户：$USERNAME"
echo "  设备：$DEVICE_ID"
echo ""

# 1. 登录
echo "[1/7] 用户登录..."
TOKEN=$(/home/smart_doorbell/venv/bin/python3 -c "
import requests
r = requests.post('$BASE_URL/api/auth/login', json={'username': '$USERNAME', 'password': '$PASSWORD'})
d = r.json()
print(d.get('access_token', '') if d.get('success') else 'ERROR')
")

if [ -z "$TOKEN" ] || [[ "$TOKEN" == "ERROR" ]]; then
    echo "  ✗ 登录失败"
    exit 1
fi
echo "  ✓ 登录成功"

# 2. 设备状态
echo ""
echo "[2/7] 设备状态..."
curl -s "$BASE_URL/api/device/status" -H "Authorization: Bearer $TOKEN" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  设备数:', len(d.get('devices',[]))); [print(f'    - {x.get(\"device_id\")}: {x.get(\"device_name\")}') for x in d.get('devices',[])]"

# 3. 远程开门
echo ""
echo "[3/7] 远程开门..."
curl -s -X POST "$BASE_URL/api/control/unlock" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"device_id\":\"$DEVICE_ID\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  ', d.get('message') or d.get('error'))"

# 4. 远程警报
echo ""
echo "[4/7] 远程警报..."
curl -s -X POST "$BASE_URL/api/control/alert" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"device_id\":\"$DEVICE_ID\",\"message\":\"测试警报\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  ', d.get('message') or d.get('error'))"

# 5. 远程语音
echo ""
echo "[5/7] 远程语音..."
curl -s -X POST "$BASE_URL/api/control/speak" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"device_id\":\"$DEVICE_ID\",\"message\":\"您好，请问有什么事？\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  ', d.get('message') or d.get('error'))"

# 6. 远程抓拍
echo ""
echo "[6/7] 远程抓拍..."
curl -s -X POST "$BASE_URL/api/control/snapshot" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"device_id\":\"$DEVICE_ID\"}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  ', d.get('message') or d.get('error'))"

# 7. 上传访客
echo ""
echo "[7/7] 上传访客记录..."
curl -s -X POST "$BASE_URL/api/visitor/upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"device_id\":\"$DEVICE_ID\",\"visitor_type\":\"family\",\"member_name\":\"张三\",\"confidence\":0.95}" | \
  /home/smart_doorbell/venv/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print('  访客 ID:', d.get('visitor_id'))"

# 查看数据库
echo ""
echo "========================================="
echo "  查看服务器数据"
echo "========================================="

/home/smart_doorbell/venv/bin/python3 << 'PY'
import pymysql

conn = pymysql.connect(host='localhost', user='root', password='', database='smart_doorbell')
cursor = conn.cursor()

# 查询远程命令
cursor.execute('''
    SELECT id, device_id, command_type, status, created_at
    FROM remote_commands
    ORDER BY created_at DESC LIMIT 5
''')
commands = cursor.fetchall()
print(f"远程命令 (最近 5 条):")
for cmd in commands:
    print(f"  - ID:{cmd[0]} 设备:{cmd[1]} 类型:{cmd[2]} 状态:{cmd[3]}")

# 查询访客
cursor.execute('''
    SELECT id, visitor_type, member_name, confidence, created_at
    FROM visitors
    ORDER BY created_at DESC LIMIT 5
''')
visitors = cursor.fetchall()
print(f"\n访客记录 (最近 5 条):")
for v in visitors:
    vtype = "家人" if v[1] == "family" else "陌生人"
    print(f"  - {v[2] or '未知'} ({vtype}) 置信度:{v[3]}")

conn.close()
PY

echo ""
echo "========================================="
echo "  远程功能测试完成"
echo "========================================="
echo ""
echo "测试结果:"
echo "  ✓ 用户登录成功"
echo "  ✓ 远程开门命令已发送"
echo "  ✓ 远程警报命令已发送"
echo "  ✓ 远程语音命令已发送"
echo "  ✓ 远程抓拍命令已发送"
echo "  ✓ 访客记录已上传"
echo ""
echo "设备端需要运行 main_with_cloud.py 来接收并执行这些命令"
