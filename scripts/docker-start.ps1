# Docker 一键部署脚本（Windows PowerShell）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\docker-start.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\docker-start.ps1 --rebuild
#   powershell -ExecutionPolicy Bypass -File scripts\docker-start.ps1 --down

param(
    [switch]$Rebuild,   # 强制重新构建镜像
    [switch]$Down       # 停止并移除容器（保留数据卷）
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  高校奖助学金申请条件评估与指导系统 - Docker 部署" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# 1. 检查 docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[X] 未检测到 docker 命令。请先安装 Docker Desktop：" -ForegroundColor Red
    Write-Host "    winget install -e --id Docker.DockerDesktop" -ForegroundColor Yellow
    Write-Host "    安装后启动 Docker Desktop 并等待引擎就绪，再重跑本脚本。" -ForegroundColor Yellow
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Docker 引擎未运行。请先启动 Docker Desktop。" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker 引擎可用：" -ForegroundColor Green
docker --version

# 2. 检查 .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[!] 已从 .env.example 生成 .env，请检查其中的配置" -ForegroundColor Yellow
}

# 3. 检查线上模型 API Key（不输出密钥内容）
$apiKeyLine = Get-Content ".env" | Where-Object { $_ -match '^LLM_API_KEY=' } | Select-Object -First 1
$apiKeyValue = if ($apiKeyLine) { ($apiKeyLine -split '=', 2)[1].Trim() } else { "" }
if (-not $apiKeyValue -or $apiKeyValue -eq "sk-your-api-key") {
    Write-Host "[X] .env 中尚未配置 LLM_API_KEY。" -ForegroundColor Red
    Write-Host "    请先填写阿里云百炼或其他 OpenAI 兼容服务的 API Key。" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] 已检测到线上模型 API Key（内容已隐藏）" -ForegroundColor Green

# 4. 确保基础镜像存在（Docker Hub 国内直连超时，自动走加速器预拉）
$baseImages = @{
    "python:3.12-slim" = @("docker.1ms.run/library/python:3.12-slim", "docker.m.daocloud.io/library/python:3.12-slim")
    "node:20-alpine"   = @("docker.1ms.run/library/node:20-alpine",   "docker.m.daocloud.io/library/node:20-alpine")
    "nginx:alpine"     = @("docker.1ms.run/library/nginx:alpine",     "docker.m.daocloud.io/library/nginx:alpine")
}
foreach ($key in $baseImages.Keys) {
    $exist = docker images -q $key 2>$null
    if (-not $exist) {
        Write-Host "[!] 缺少基础镜像 $key，尝试从国内加速器预拉..." -ForegroundColor Yellow
        $pulled = $false
        foreach ($mirror in $baseImages[$key]) {
            docker pull $mirror *> $null
            if ($LASTEXITCODE -eq 0) {
                docker tag $mirror $key
                $pulled = $true
                Write-Host "[OK] 已通过 $mirror 预拉 $key" -ForegroundColor Green
                break
            }
        }
        if (-not $pulled) {
            Write-Host "[X] 基础镜像 $key 拉取失败，请检查网络后重试" -ForegroundColor Red
            exit 1
        }
    }
}

# 5. 部署 / 停止
if ($Down) {
    docker compose down
    Write-Host "[OK] 容器已停止并移除（app.db/chroma_db 等数据仍保留在宿主目录）" -ForegroundColor Green
    exit 0
}

if ($Rebuild) {
    docker compose build --no-cache
} else {
    docker compose build
}
docker compose up -d

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  部署完成，访问地址：" -ForegroundColor Cyan
Write-Host "    前端页面   http://localhost:5173" -ForegroundColor Green
Write-Host "    后端接口   http://localhost:8000/docs" -ForegroundColor Green
Write-Host "    健康检查   http://localhost:8000/health" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "常用命令：" -ForegroundColor Yellow
Write-Host "  docker compose ps                查看容器状态" -ForegroundColor Yellow
Write-Host "  docker compose logs -f backend   跟踪后端日志" -ForegroundColor Yellow
Write-Host "  docker compose exec backend python ingest.py   重建知识库" -ForegroundColor Yellow
Write-Host "  docker compose down              停止服务" -ForegroundColor Yellow
