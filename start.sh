#!/bin/bash
# 启动数据生成任务管理系统（前后端分离模式）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "启动数据生成任务管理系统"
echo "=========================================="

# 从 config.yaml 读取配置
get_all_config() {
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
print(web_config.get('port', 5000))

# 前端配置
frontend_config = config.get('frontend', {})
frontend_url = frontend_config.get('url', 'http://localhost:3000')
# 从 URL 提取端口
import re
match = re.search(r':(\d+)$', frontend_url)
print(match.group(1) if match else '3000')
"
}

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查并安装后端依赖
echo ""
echo "【后端】检查Python依赖..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "安装后端依赖..."
    pip3 install -r requirements.txt
else
    echo "后端依赖已安装"
fi

# 检查Node.js环境（用于前端）
HAS_NODE=false
if command -v node &> /dev/null && command -v npm &> /dev/null; then
    HAS_NODE=true
    echo ""
    echo "【前端】检查Node.js依赖..."
    cd frontend
    
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    else
        echo "前端依赖已安装"
    fi
    
    cd ..
else
    echo ""
    echo "警告: 未安装Node.js，前端无法启动"
    echo "请安装Node.js (>= 16): https://nodejs.org/"
    exit 1
fi

# 创建日志目录
mkdir -p log

# 启动 Redis 服务
echo ""
echo "【Redis】检查并启动 Redis 服务..."

# 读取所有配置
ALL_CONFIG=$(get_all_config)
REDIS_HOST=$(echo "$ALL_CONFIG" | sed -n '1p')
REDIS_PORT=$(echo "$ALL_CONFIG" | sed -n '2p')
BACKEND_HOST=$(echo "$ALL_CONFIG" | sed -n '3p')
BACKEND_PORT=$(echo "$ALL_CONFIG" | sed -n '4p')
FRONTEND_PORT=$(echo "$ALL_CONFIG" | sed -n '5p')

echo "配置信息:"
echo "  - Redis: $REDIS_HOST:$REDIS_PORT"
echo "  - 后端: $BACKEND_HOST:$BACKEND_PORT"
echo "  - 前端端口: $FRONTEND_PORT"

# 检查 Redis 是否已在运行
if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "Redis 服务已在运行中 ($REDIS_HOST:$REDIS_PORT)"
    else
        # Redis 未运行，尝试启动
        if command -v redis-server &> /dev/null; then
            echo "启动 Redis 服务 (端口: $REDIS_PORT, 持久化已禁用)..."
            nohup redis-server --port "$REDIS_PORT" --daemonize yes --save "" --appendonly no > log/redis.log 2>&1
            sleep 1
            
            # 验证 Redis 是否启动成功
            if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
                echo "Redis 服务已启动 ($REDIS_HOST:$REDIS_PORT)"
            else
                echo "警告: Redis 启动失败，任务进度功能可能不可用"
            fi
        else
            echo "警告: 未安装 redis-server，跳过 Redis 启动"
            echo "提示: 可通过 'brew install redis' (macOS) 或 'apt install redis-server' (Linux) 安装"
        fi
    fi
else
    echo "警告: 未安装 redis-cli，无法检查 Redis 状态"
    echo "提示: 可通过 'brew install redis' (macOS) 或 'apt install redis-server' (Linux) 安装"
fi

# 启动后端服务
echo ""
echo "【后端】启动API服务器 (${BACKEND_PORT}端口)..."
if [ -f log/web_app.pid ]; then
    PID=$(cat log/web_app.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "后端服务已经在运行中 (PID: $PID)"
    else
        rm log/web_app.pid
        # 启动后端
        if python3 -c "import uvicorn" 2>/dev/null; then
            nohup python3 -m uvicorn app.app:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > log/web_app.log 2>&1 &
        else
            nohup python3 ./app/app.py > log/web_app.log 2>&1 &
        fi
        BACKEND_PID=$!
        echo $BACKEND_PID > log/web_app.pid
        sleep 2
        echo "后端服务已启动 (PID: $BACKEND_PID)"
    fi
else
    if python3 -c "import uvicorn" 2>/dev/null; then
        nohup python3 -m uvicorn app.app:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > log/web_app.log 2>&1 &
    else
        nohup python3 ./app/app.py > log/web_app.log 2>&1 &
    fi
    BACKEND_PID=$!
    echo $BACKEND_PID > log/web_app.pid
    sleep 2
    echo "后端服务已启动 (PID: $BACKEND_PID)"
fi

# 启动前端服务
echo ""
echo "【前端】启动开发服务器 (${FRONTEND_PORT}端口)..."
if [ -f log/frontend.pid ]; then
    PID=$(cat log/frontend.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "前端服务已经在运行中 (PID: $PID)"
    else
        rm log/frontend.pid
        cd frontend
        nohup npm run dev -- --port "$FRONTEND_PORT" > ../log/frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > ../log/frontend.pid
        cd ..
        sleep 3
        echo "前端服务已启动 (PID: $FRONTEND_PID)"
    fi
else
    cd frontend
    nohup npm run dev -- --port "$FRONTEND_PORT" > ../log/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../log/frontend.pid
    cd ..
    sleep 3
    echo "前端服务已启动 (PID: $FRONTEND_PID)"
fi

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
echo "系统启动成功！"
echo "=========================================="
echo "前端地址: http://localhost:${FRONTEND_PORT}"
echo "局域网前端: http://$LOCAL_IP:${FRONTEND_PORT}"
echo "后端API: http://localhost:${BACKEND_PORT}"
echo "API文档: http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "日志文件:"
echo "  - 后端: log/web_app.log"
echo "  - 前端: log/frontend.log"
echo "  - Redis: log/redis.log"
echo ""
echo "提示:"
echo "  - 查看后端日志: tail -f log/web_app.log"
echo "  - 查看前端日志: tail -f log/frontend.log"
echo "  - 停止服务: ./stop.sh"
echo "  - 配置文件: config/config.yaml"
echo "=========================================="
