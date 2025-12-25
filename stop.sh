#!/bin/bash
# 停止数据生成任务管理系统（前后端）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "停止数据生成任务管理系统"
echo "=========================================="

# 从 config.yaml 读取 Redis 配置
get_redis_config() {
    python3 -c "
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
redis_config = config.get('redis_service', {})
print(redis_config.get('host', 'localhost'))
print(redis_config.get('port', 6379))
" 2>/dev/null
}

# 停止后端服务
BACKEND_PID_FILE="log/web_app.pid"
STOPPED=false

if [ -f "$BACKEND_PID_FILE" ]; then
    PID=$(cat "$BACKEND_PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "正在停止后端服务 (PID: $PID)..."
        
        # 尝试优雅停止
        kill $PID 2>/dev/null || true
        
        # 等待进程退出
        for i in {1..5}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                echo "后端服务已成功停止"
                rm "$BACKEND_PID_FILE"
                STOPPED=true
                break
            fi
            sleep 1
        done
        
        # 如果还在运行，强制停止
        if [ "$STOPPED" = false ]; then
            echo "服务未能在 5 秒内停止，正在强制结束..."
            kill -9 $PID 2>/dev/null || true
            rm "$BACKEND_PID_FILE"
            echo "后端服务已强制停止"
            STOPPED=true
        fi
    else
        echo "后端服务未运行（PID文件存在但进程不存在）"
        rm "$BACKEND_PID_FILE"
    fi
else
    echo "未找到后端服务PID文件"
fi

# 尝试通过进程名查找并停止后端服务（备选方案）
BACKEND_PIDS=$(pgrep -f "uvicorn.*app.app\|python3.*app/app.py" 2>/dev/null || true)
if [ ! -z "$BACKEND_PIDS" ]; then
    echo "发现后端进程，正在停止..."
    for pid in $BACKEND_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 1
    # 强制停止仍在运行的进程
    BACKEND_PIDS=$(pgrep -f "python3.*app.app" 2>/dev/null || true)
    if [ ! -z "$BACKEND_PIDS" ]; then
        for pid in $BACKEND_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "后端服务已停止"
    STOPPED=true
fi

# 停止前端开发服务器（如果有）
FRONTEND_PID_FILE="log/frontend.pid"
if [ -f "$FRONTEND_PID_FILE" ]; then
    PID=$(cat "$FRONTEND_PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "正在停止前端开发服务器 (PID: $PID)..."
        kill $PID 2>/dev/null || true
        sleep 1
        if ps -p $PID > /dev/null 2>&1; then
            kill -9 $PID 2>/dev/null || true
        fi
        rm "$FRONTEND_PID_FILE"
        echo "前端开发服务器已停止"
    else
        rm "$FRONTEND_PID_FILE"
    fi
fi

# 尝试通过进程名查找并停止前端开发服务器
FRONTEND_PIDS=$(pgrep -f "vite" 2>/dev/null || true)
if [ ! -z "$FRONTEND_PIDS" ]; then
    echo "发现前端开发服务器进程，正在停止..."
    for pid in $FRONTEND_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 1
    FRONTEND_PIDS=$(pgrep -f "vite" 2>/dev/null || true)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        for pid in $FRONTEND_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "前端开发服务器已停止"
fi

# 停止 Redis 服务
echo ""
echo "【Redis】检查 Redis 服务..."

REDIS_CONFIG=$(get_redis_config)
if [ ! -z "$REDIS_CONFIG" ]; then
    REDIS_HOST=$(echo "$REDIS_CONFIG" | sed -n '1p')
    REDIS_PORT=$(echo "$REDIS_CONFIG" | sed -n '2p')
    
    if command -v redis-cli &> /dev/null; then
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
            echo "正在停止 Redis 服务 ($REDIS_HOST:$REDIS_PORT)..."
            redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" shutdown nosave 2>/dev/null || true
            sleep 1
            echo "Redis 服务已停止"
            STOPPED=true
        else
            echo "Redis 服务未运行"
        fi
    else
        echo "未安装 redis-cli，跳过 Redis 停止"
    fi
else
    echo "无法读取 Redis 配置，跳过 Redis 停止"
fi

echo ""
if [ "$STOPPED" = true ]; then
    echo "=========================================="
    echo "系统已停止"
    echo "=========================================="
else
    echo "=========================================="
    echo "未发现运行中的服务"
    echo "=========================================="
fi

