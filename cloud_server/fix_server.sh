#!/bin/bash
# CLAUDE 智能门铃 - 服务器修复脚本
# 使用方法：bash /tmp/fix_server.sh

echo "========================================="
echo "  CLAUDE 智能门铃 - 服务器修复脚本"
echo "========================================="

# 1. 备份
echo "[1/5] 备份原文件..."
cp /home/smart_doorbell/server/app.py /home/smart_doorbell/server/app.py.bak
echo "      已备份到 app.py.bak"

# 2. 修复 app.py
echo "[2/5] 修复 app.py 语法错误..."
python3 << 'PY'
with open('/home/smart_doorbell/server/app.py', 'r') as f:
    lines = f.readlines()

output = []
i = 0
while i < len(lines):
    if i == 0 and lines[i].strip() == '"""':
        if i+1 < len(lines) and 'import bcrypt' in lines[i+1]:
            output.append('"""\n')
            output.append('Flask API 服务器 - 为安卓 APP 提供数据接口\n')
            output.append('支持设备注册、远程控制、实时通信\n')
            output.append('"""\n')
            output.append('import bcrypt\n')
            i += 2
            continue
    output.append(lines[i])
    i += 1

with open('/home/smart_doorbell/server/app.py', 'w') as f:
    f.writelines(output)

print("      app.py 已修复")
PY

# 3. 重启服务
echo "[3/5] 停止旧服务..."
pkill -f "python.*app.py" 2>/dev/null
sleep 2

echo "[4/5] 启动新服务..."
cd /home/smart_doorbell/server
nohup /home/smart_doorbell/venv/bin/python app.py > /tmp/smart_doorbell.log 2>&1 &
sleep 3

# 4. 验证
echo "[5/5] 验证服务..."
echo ""
echo "进程状态:"
ps aux | grep -v grep | grep "python.*app.py" || echo "      未找到进程"

echo ""
echo "端口监听:"
netstat -tlnp | grep 5000 || echo "      端口未监听"

echo ""
echo "健康检查:"
curl -s http://localhost:5000/api/health || echo "      无法连接"

echo ""
echo "========================================="
echo "  修复完成！"
echo "========================================="
