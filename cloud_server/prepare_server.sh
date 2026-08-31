#!/bin/bash
# 在服务器上执行的准备脚本
# 创建必要的目录结构

echo "============================================================"
echo "创建项目目录..."
echo "============================================================"

# 创建主目录
mkdir -p /home/smart_doorbell/server
mkdir -p /home/smart_doorbell/database
mkdir -p /home/smart_doorbell/uploads
mkdir -p /home/smart_doorbell/logs

# 设置权限
chmod -R 755 /home/smart_doorbell

echo "目录创建完成！"
echo ""
echo "目录结构:"
ls -la /home/smart_doorbell/

echo ""
echo "============================================================"
echo "下一步：上传文件"
echo "============================================================"
echo "在你的 Windows 机器上执行:"
echo "  scp deploy.sh root@8.134.196.56:/root/deploy.sh"
echo "  scp -r server/* root@8.134.196.56:/home/smart_doorbell/server/"
echo "  scp -r database/* root@8.134.196.56:/home/smart_doorbell/database/"
