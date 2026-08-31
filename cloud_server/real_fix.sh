#!/bin/bash
# ============================================================
# CLAUDE 智能门铃系统 - 真正能用的修复脚本
# ============================================================

set -e
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  真正能用的修复 - 手动生成密码并验证"
echo "============================================================"
echo ""

# 步骤 1: 停止服务
echo "停止服务..."
systemctl stop smart-doorbell

# 步骤 2: 生成有效的 bcrypt 哈希
echo "生成 bcrypt 密码哈希..."
HASH=$(/home/smart_doorbell/venv/bin/python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(rounds=12)).decode('utf-8'))")
echo "生成的哈希：$HASH"

# 步骤 3: 清空并重新创建用户
echo "创建 admin 用户..."
mysql -u root smart_doorbell << MYSQL
DELETE FROM users WHERE username='admin';
INSERT INTO users (username, password_hash, email, is_active) VALUES ('admin', '$HASH', 'admin@example.com', TRUE);
MYSQL

# 步骤 4: 验证数据库中的哈希
echo "验证数据库中的用户..."
mysql -u root smart_doorbell -e "SELECT username, LEFT(password_hash, 30) as hash FROM users WHERE username='admin';"

# 步骤 5: 用 Python 直接验证
echo ""
echo "测试密码验证..."
/home/smart_doorbell/venv/bin/python3 << PYTEST
import bcrypt
import pymysql

# 从数据库获取哈希
conn = pymysql.connect(host='localhost', user='root', database='smart_doorbell', charset='utf8mb4')
cursor = conn.cursor()
cursor.execute("SELECT password_hash FROM users WHERE username='admin'")
db_hash = cursor.fetchone()[0]
conn.close()

print(f"数据库哈希：{db_hash}")

# 验证密码
result = bcrypt.checkpw(b'admin123', db_hash.encode('utf-8'))
print(f"bcrypt 验证结果：{result}")

if result:
    print("✅ 密码验证通过！")
else:
    print("❌ 密码验证失败！")
PYTEST

# 步骤 6: 启动服务
echo ""
echo "启动服务..."
systemctl start smart-doorbell
sleep 3

# 步骤 7: 测试登录
echo ""
echo "测试登录..."
RESULT=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')
echo "$RESULT"

if [[ "$RESULT" == *"access_token"* ]]; then
    echo ""
    echo -e "${GREEN}✅✅✅ 登录成功！✅✅✅${NC}"
    TOKEN=$(echo "$RESULT" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    echo "$TOKEN" > /root/api_token.txt
    echo "Token: ${TOKEN:0:50}..."
else
    echo ""
    echo -e "${RED}❌ 登录失败${NC}"
    echo ""
    echo "查看日志:"
    journalctl -u smart-doorbell -n 10 --no-pager
fi

echo ""
echo "============================================================"
