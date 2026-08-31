@echo off
echo ========================================
echo   智能门铃服务器代码部署工具
echo ========================================
echo.
echo 服务器：8.134.196.56
echo 用户：root
echo.

REM 检查私钥文件是否存在
if not exist "C:\Users\HP\.ssh\id_rsa_smartdoorbell" (
    echo [错误] SSH 私钥文件不存在！
    echo 请先运行 setup_ssh_key.ps1 配置 SSH 密钥
    pause
    exit /b 1
)

echo [1/3] 上传服务器代码...
scp -i "C:\Users\HP\.ssh\id_rsa_smartdoorbell" -o StrictHostKeyChecking=no "C:\Users\HP\Desktop\graduation\cloud_server\server\app.py" root@8.134.196.56:/home/smart_doorbell/server/app.py

if %ERRORLEVEL% neq 0 (
    echo [上传失败] 请检查 SSH 配置
    pause
    exit /b 1
)

echo [上传成功] app.py 已上传到服务器
echo.
echo [2/3] 连接到服务器重启服务...
echo.

ssh -i "C:\Users\HP\.ssh\id_rsa_smartdoorbell" -o StrictHostKeyChecking=no root@8.134.196.56 ^
    "systemctl stop smart-doorbell.service; ^
     sleep 3; ^
     cd /home/smart_doorbell/server; ^
     pkill -9 python; ^
     sleep 2; ^
     /home/smart_doorbell/venv/bin/python app.py > /tmp/smart_doorbell.log 2>&1 & ^
     sleep 3; ^
     ps aux | grep python | grep -v grep; ^
     netstat -tlnp | grep 5000; ^
     echo '服务已启动！'"

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
pause
