# PowerShell 脚本：配置 SSH 公钥到阿里云服务器
# 使用方法：右键 -> 使用 PowerShell 运行，或在 PowerShell 中执行此脚本

$serverIp = "8.134.196.56"
$sshUser = "root"
$sshPassword = "<请在本机私密保存>"
$sshKeyPath = "C:\Users\HP\.ssh\id_rsa_smartdoorbell.pub"
$sshPrivateKeyPath = "C:\Users\HP\.ssh\id_rsa_smartdoorbell"

# 读取公钥内容
$publicKey = Get-Content $sshKeyPath -Raw

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SSH 密钥配置工具 - 智能门铃系统" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "服务器：$serverIp" -ForegroundColor Yellow
Write-Host "用户：$sshUser" -ForegroundColor Yellow
Write-Host ""

# 创建 PSCredential 对象
$securePassword = ConvertTo-SecureString $sshPassword -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential($sshUser, $securePassword)

try {
    Write-Host "[1/4] 连接到服务器..." -ForegroundColor Yellow

    # 使用 SSH 执行命令（需要安装 OpenSSH 客户端）
    $sshConfig = @"
Host $serverIp
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
"@

    # 第一次连接：创建 .ssh 目录
    Write-Host "[2/4] 创建 .ssh 目录..." -ForegroundColor Yellow
    $sessionScript = {
        mkdir -p ~/.ssh
        chmod 700 ~/.ssh
    }

    # 使用 plink 或 ssh 执行命令
    $plinkPath = "C:\Program Files\PuTTY\plink.exe"
    if (Test-Path $plinkPath) {
        Write-Host "使用 PuTTY plink 执行命令..." -ForegroundColor Green
        & $plinkPath -ssh $sshUser@$serverIp -pw $sshPassword "mkdir -p ~/.ssh && chmod 700 ~/.ssh"

        Write-Host "[3/4] 写入公钥到 authorized_keys..." -ForegroundColor Yellow
        # 将公钥内容转义后写入
        $escapedKey = $publicKey.Replace('"', '\"').Replace('$', '\$')
        & $plinkPath -ssh $sshUser@$serverIp -pw $sshPassword "echo '$escapedKey' >> ~/.ssh/authorized_keys"
        & $plinkPath -ssh $sshUser@$serverIp -pw $sshPassword "chmod 600 ~/.ssh/authorized_keys"
    } else {
        Write-Host "未找到 plink.exe，尝试使用内置 OpenSSH..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "请手动执行以下命令配置 SSH 密钥：" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "ssh root@$serverIp" -ForegroundColor White
        Write-Host "# 输入密码：<你的服务器密码>" -ForegroundColor White
        Write-Host ""
        Write-Host "然后执行：" -ForegroundColor White
        Write-Host "mkdir -p ~/.ssh" -ForegroundColor White
        Write-Host "chmod 700 ~/.ssh" -ForegroundColor White
        Write-Host "echo `"$publicKey`" >> ~/.ssh/authorized_keys" -ForegroundColor White
        Write-Host "chmod 600 ~/.ssh/authorized_keys" -ForegroundColor White
        Write-Host "exit" -ForegroundColor White
        Write-Host "========================================" -ForegroundColor Red
        Write-Host ""

        break
    }

    Write-Host "[4/4] 测试密钥登录..." -ForegroundColor Yellow
    $testResult = ssh -i $sshPrivateKeyPath -o StrictHostKeyChecking=no -o BatchMode=yes $sshUser@$serverIp "echo 'SSH 密钥登录成功！'" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  SSH 密钥配置成功！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "以后可以使用以下命令登录：" -ForegroundColor Cyan
        Write-Host "ssh -i $sshPrivateKeyPath $sshUser@$serverIp" -ForegroundColor White
        Write-Host ""
        Write-Host "或使用简化命令（添加配置后）：" -ForegroundColor Cyan
        Write-Host "ssh smartdoorbell-server" -ForegroundColor White
        Write-Host ""

        # 创建 SSH 配置
        $sshConfigDir = "$env:USERPROFILE\.ssh"
        $sshConfigFile = "$sshConfigDir\config"

        if (-not (Test-Path $sshConfigDir)) {
            New-Item -ItemType Directory -Path $sshConfigDir | Out-Null
        }

        $configEntry = @"
Host smartdoorbell-server
    HostName $serverIp
    User $sshUser
    IdentityFile $sshPrivateKeyPath
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

"@

        Add-Content -Path $sshConfigFile -Value $configEntry
        Write-Host "已创建 SSH 快捷配置" -ForegroundColor Green

    } else {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "  SSH 密钥配置失败，请手动配置" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Red
    }

} catch {
    Write-Host "错误：$_" -ForegroundColor Red
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
