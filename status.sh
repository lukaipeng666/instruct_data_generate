#!/bin/bash
# 查看数据生成任务管理系统服务状态

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "数据生成任务管理系统 - 服务状态"
echo "=========================================="

# 从 config.yaml 读取配置
get_config() {
    python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

redis_config = config.get('redis_service', {})
print(redis_config.get('host', 'localhost'))
print(redis_config.get('port', 16379))

web_config = config.get('server', {})
print(web_config.get('port', 18080))

frontend_config = config.get('frontend', {})
frontend_url = frontend_config.get('url', 'http://localhost:13000')
import re
match = re.search(r':(\d+)\$', frontend_url)
print(match.group(1) if match else '13000')
" 2>/dev/null
}

CONFIG=$(get_config)
if [ -z "$CONFIG" ]; then
    REDIS_HOST="localhost"
    REDIS_PORT="16379"
    BACKEND_PORT="18080"
    FRONTEND_PORT="13000"
else
    REDIS_HOST=$(echo "$CONFIG" | sed -n '1p')
    REDIS_PORT=$(echo "$CONFIG" | sed -n '2p')
    BACKEND_PORT=$(echo "$CONFIG" | sed -n '3p')
    FRONTEND_PORT=$(echo "$CONFIG" | sed -n '4p')
fi

echo ""

# ==================== Redis 状态 ====================
echo "【Redis】端口 $REDIS_PORT"
if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "   状态: ✅ 运行中"
        REDIS_INFO=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" info server 2>/dev/null | grep -E "redis_version|uptime_in_seconds" | head -2)
        if [ ! -z "$REDIS_INFO" ]; then
            VERSION=$(echo "$REDIS_INFO" | grep redis_version | cut -d: -f2 | tr -d '\r')
            UPTIME=$(echo "$REDIS_INFO" | grep uptime_in_seconds | cut -d: -f2 | tr -d '\r')
            echo "   版本: $VERSION"
            if [ ! -z "$UPTIME" ]; then
                HOURS=$((UPTIME / 3600))
                MINUTES=$(((UPTIME % 3600) / 60))
                echo "   运行时间: ${HOURS}小时${MINUTES}分钟"
            fi
        fi
    else
        echo "   状态: ❌ 未运行"
    fi
else
    echo "   状态: ⚠️ redis-cli 未安装"
fi

echo ""

# ==================== Go 后端状态 ====================
echo "【Go后端】端口 $BACKEND_PORT"
GO_PID_FILE="log/go_backend.pid"
GO_PID=""

if [ -f "$GO_PID_FILE" ]; then
    GO_PID=$(cat "$GO_PID_FILE")
fi

# 检查端口是否有服务
if curl -s "http://localhost:$BACKEND_PORT" > /dev/null 2>&1; then
    RESPONSE=$(curl -s "http://localhost:$BACKEND_PORT")
    echo "   状态: ✅ 运行中"
    if [ ! -z "$GO_PID" ] && ps -p $GO_PID > /dev/null 2>&1; then
        echo "   PID: $GO_PID"
    else
        PORT_PID=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
        if [ ! -z "$PORT_PID" ]; then
            echo "   PID: $PORT_PID"
        fi
    fi
    VERSION=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "   版本: $VERSION"
else
    echo "   状态: ❌ 未运行"
fi

echo ""

# ==================== 前端状态 ====================
echo "【前端】端口 $FRONTEND_PORT"
FRONTEND_PID_FILE="log/frontend.pid"
FRONTEND_PID=""

if [ -f "$FRONTEND_PID_FILE" ]; then
    FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
fi

if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    echo "   状态: ✅ 运行中"
    if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "   PID: $FRONTEND_PID"
    else
        PORT_PID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null | head -1)
        if [ ! -z "$PORT_PID" ]; then
            echo "   PID: $PORT_PID"
        fi
    fi
else
    echo "   状态: ❌ 未运行"
fi

echo ""

# ==================== 获取局域网 IP ====================
get_local_ip() {
    if command -v ipconfig &> /dev/null; then
        ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "未知"
    else
        hostname -I 2>/dev/null | awk '{print $1}' || echo "未知"
    fi
}

LOCAL_IP=$(get_local_ip)

# ==================== 访问地址 ====================
echo "【访问地址】"
if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    echo "   本地:     http://localhost:$FRONTEND_PORT"
    echo "   局域网:   http://$LOCAL_IP:$FRONTEND_PORT"
else
    echo "   前端未运行，无法访问"
fi

echo ""
echo "=========================================="

