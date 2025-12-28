#!/bin/bash
# 启动数据生成任务管理系统（Go后端 + React前端）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "启动数据生成任务管理系统"
echo "=========================================="

# 从 config.yaml 读取配置
get_config() {
    python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Redis 配置
redis_config = config.get('redis_service', {})
print(redis_config.get('host', 'localhost'))
print(redis_config.get('port', 6379))

# Web 服务配置
web_config = config.get('web_service', {})
print(web_config.get('host', '0.0.0.0'))
print(web_config.get('port', 8080))

# 前端配置
frontend_config = config.get('frontend', {})
frontend_url = frontend_config.get('url', 'http://localhost:3000')
import re
match = re.search(r':(\d+)\$', frontend_url)
print(match.group(1) if match else '3000')
" 2>/dev/null
}

# 读取配置
echo ""
echo "【配置】读取配置文件..."
CONFIG=$(get_config)
if [ -z "$CONFIG" ]; then
    echo "警告: 无法读取配置文件，使用默认配置"
    REDIS_HOST="localhost"
    REDIS_PORT="6379"
    BACKEND_HOST="0.0.0.0"
    BACKEND_PORT="8080"
    FRONTEND_PORT="3000"
else
    REDIS_HOST=$(echo "$CONFIG" | sed -n '1p')
    REDIS_PORT=$(echo "$CONFIG" | sed -n '2p')
    BACKEND_HOST=$(echo "$CONFIG" | sed -n '3p')
    BACKEND_PORT=$(echo "$CONFIG" | sed -n '4p')
    FRONTEND_PORT=$(echo "$CONFIG" | sed -n '5p')
fi

echo "配置信息:"
echo "  - Redis: $REDIS_HOST:$REDIS_PORT"
echo "  - Go后端: $BACKEND_HOST:$BACKEND_PORT"
echo "  - 前端端口: $FRONTEND_PORT"

# 创建日志目录
mkdir -p log

# ==================== 启动 Redis ====================
echo ""
echo "【Redis】检查并启动 Redis 服务..."

if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "✅ Redis 服务已在运行中 ($REDIS_HOST:$REDIS_PORT)"
    else
        if command -v redis-server &> /dev/null; then
            echo "启动 Redis 服务..."
            redis-server --port "$REDIS_PORT" --daemonize yes --save "" --appendonly no > log/redis.log 2>&1
            sleep 1
            
            if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
                echo "✅ Redis 服务已启动 ($REDIS_HOST:$REDIS_PORT)"
            else
                echo "⚠️ Redis 启动失败，任务进度功能可能不可用"
            fi
        else
            echo "⚠️ 未安装 redis-server，跳过 Redis 启动"
            echo "   提示: brew install redis (macOS) 或 apt install redis-server (Linux)"
        fi
    fi
else
    echo "⚠️ 未安装 redis-cli，无法检查 Redis 状态"
fi

# ==================== 启动 Go 后端 ====================
echo ""
echo "【Go后端】检查并启动 API 服务器..."

# 检查 Go 是否安装
if ! command -v go &> /dev/null; then
    echo "❌ 错误: 未安装 Go"
    echo "   请安装 Go: https://golang.org/dl/"
    exit 1
fi

# 检查端口是否被占用
if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
    EXISTING_PID=$(lsof -ti:$BACKEND_PORT)
    echo "端口 $BACKEND_PORT 已被占用 (PID: $EXISTING_PID)"
    echo "正在停止现有进程..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
fi

# 编译 Go 程序
echo "编译 Go 后端..."
if ! go build -o server ./cmd/server/main.go 2>&1; then
    echo "❌ Go 编译失败"
    exit 1
fi

# 启动 Go 后端
echo "启动 Go 后端服务..."
nohup ./server > log/go_backend.log 2>&1 &
GO_PID=$!
echo $GO_PID > log/go_backend.pid
sleep 2

# 验证后端是否启动成功
if curl -s "http://localhost:$BACKEND_PORT" > /dev/null 2>&1; then
    echo "✅ Go 后端已启动 (PID: $GO_PID, 端口: $BACKEND_PORT)"
else
    echo "❌ Go 后端启动失败，请检查日志: log/go_backend.log"
    cat log/go_backend.log | tail -20
    exit 1
fi

# ==================== 启动前端 ====================
echo ""
echo "【前端】检查并启动开发服务器..."

# 检查 Node.js 是否安装
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "❌ 错误: 未安装 Node.js"
    echo "   请安装 Node.js (>= 16): https://nodejs.org/"
    exit 1
fi

# 检查前端端口是否被占用
if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
    EXISTING_PID=$(lsof -ti:$FRONTEND_PORT)
    echo "端口 $FRONTEND_PORT 已被占用 (PID: $EXISTING_PID)"
    echo "正在停止现有进程..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
fi

# 检查并安装前端依赖
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动前端开发服务器
echo "启动前端开发服务器..."
nohup npm run dev -- --port "$FRONTEND_PORT" --host > ../log/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../log/frontend.pid
cd ..
sleep 3

# 验证前端是否启动成功
if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    echo "✅ 前端已启动 (PID: $FRONTEND_PID, 端口: $FRONTEND_PORT)"
else
    echo "⚠️ 前端可能仍在启动中，请稍后检查"
fi

# ==================== 显示状态 ====================

# 获取局域网 IP 地址
get_local_ip() {
    if command -v ipconfig &> /dev/null; then
        # macOS
        ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "未知"
    else
        # Linux
        hostname -I 2>/dev/null | awk '{print $1}' || echo "未知"
    fi
}

LOCAL_IP=$(get_local_ip)

echo ""
echo "=========================================="
echo "🚀 系统启动成功！"
echo "=========================================="
echo ""
echo "📱 访问地址:"
echo "   前端页面:     http://localhost:${FRONTEND_PORT}"
echo "   局域网访问:   http://$LOCAL_IP:${FRONTEND_PORT}"
echo "   后端 API:     http://localhost:${BACKEND_PORT}"
echo ""
echo "📋 日志文件:"
echo "   Go 后端:  tail -f log/go_backend.log"
echo "   前端:     tail -f log/frontend.log"
echo "   Redis:    log/redis.log"
echo ""
echo "🔧 管理命令:"
echo "   停止服务:  ./stop.sh"
echo "   查看状态:  ./status.sh (如有)"
echo ""
echo "=========================================="
