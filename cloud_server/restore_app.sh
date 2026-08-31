#!/bin/bash
# 恢复服务器 app.py - 使用备份恢复

echo "========================================="
echo "  恢复 app.py 文件"
echo "========================================="

cd /home/smart_doorbell/server

# 检查备份文件
if [ -f "app.py.bak" ]; then
    echo "发现原始备份，开始恢复..."

    # 从原始备份恢复，只修复 bcrypt 导入位置
    python3 << 'PY'
# 读取备份文件
with open('/home/smart_doorbell/server/app.py.bak', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查备份文件的格式
lines = content.split('\n')
print("备份文件前 5 行:")
for i, line in enumerate(lines[:5]):
    print(f"  {i+1}: {repr(line)}")

# 修复：把 import bcrypt 从文档字符串里移出来
if '"""' in lines[0] and 'import bcrypt' in lines[1]:
    print("\n检测到错误格式，开始修复...")

    # 创建正确的新内容
    new_content = '''"""
Flask API 服务器 - 为安卓 APP 提供数据接口
支持设备注册、远程控制、实时通信
"""

import os
import json
import base64
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from typing import Dict, Optional
import pymysql
import redis
import bcrypt
from werkzeug.security import generate_password_hash
'''
    # 找到原文件从哪一行开始是正确的
    skip_lines = 0
    for i, line in enumerate(lines):
        if line.strip() == 'import os':
            skip_lines = i
            break

    # 添加剩余内容
    remaining = '\n'.join(lines[skip_lines:])
    new_content += remaining

    with open('/home/smart_doorbell/server/app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("修复完成!")
else:
    print("备份文件格式未知，尝试其他方法...")
PY

    # 验证
    echo ""
    echo "验证语法..."
    /home/smart_doorbell/venv/bin/python -m py_compile app.py
    if [ $? -eq 0 ]; then
        echo "语法正确!"
    else
        echo "语法错误，尝试直接复制本地文件..."
    fi
else
    echo "未找到备份文件 app.py.bak"
    ls -la /home/smart_doorbell/server/
fi

# 启动服务
echo ""
echo "启动服务..."
pkill -f "python.*app.py" 2>/dev/null
sleep 2

cd /home/smart_doorbell/server
nohup /home/smart_doorbell/venv/bin/python app.py > /tmp/smart_doorbell.log 2>&1 &
sleep 3

# 检查
echo ""
echo "检查结果..."
ps aux | grep -v grep | grep "python.*app.py"
netstat -tlnp | grep 5000
curl -s http://localhost:5000/api/health

echo ""
echo "========================================="
