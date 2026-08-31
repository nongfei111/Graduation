#!/bin/bash
# CLAUDE 智能门铃 - 初始化数据库脚本

echo "========================================="
echo "  CLAUDE 智能门铃 - 数据库初始化"
echo "========================================="

# 创建初始用户
echo "[1/3] 创建 admin 用户..."
python3 << 'PY'
import pymysql
import bcrypt

conn = pymysql.connect(host='localhost', user='root', password='', database='smart_doorbell')
cursor = conn.cursor()

password_hash = bcrypt.hashpw('Guet@084794'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

cursor.execute('SELECT id FROM users WHERE username = %s', ('admin',))
if cursor.fetchone():
    cursor.execute('UPDATE users SET password_hash = %s WHERE username = %s',
                   (password_hash, 'admin'))
    print("      admin 密码已更新为 Guet@084794")
else:
    cursor.execute('INSERT INTO users (username, password_hash) VALUES (%s, %s)',
                   ('admin', password_hash))
    print("      admin 用户已创建，密码：Guet@084794")

conn.commit()
conn.close()
PY

# 创建初始设备
echo "[2/3] 创建设备记录..."
mysql -u root smart_doorbell << 'SQL'
INSERT INTO devices (device_id, device_name, user_id, device_type, firmware_version, is_online)
VALUES ('doorbell_001', '我家门铃', 1, 'raspberry_pi_4b', '1.0.0', TRUE)
ON DUPLICATE KEY UPDATE device_name = '我家门铃';
SQL

echo "      设备 doorbell_001 已创建"

# 验证
echo "[3/3] 验证数据..."
echo ""
echo "用户列表:"
mysql -u root -e "SELECT id, username, created_at FROM smart_doorbell.users;" 2>/dev/null | tail -n +2

echo ""
echo "设备列表:"
mysql -u root -e "SELECT id, device_id, device_name, user_id FROM smart_doorbell.devices;" 2>/dev/null | tail -n +2

echo ""
echo "========================================="
echo "  数据库初始化完成"
echo "========================================="
echo ""
echo "登录信息:"
echo "  用户名：admin"
echo "  密码：Guet@084794"
echo "  设备 ID: doorbell_001"
