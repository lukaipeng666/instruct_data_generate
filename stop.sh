#!/bin/bash
# 停止数据生成任务管理系统（Go后端 + React前端）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "停止数据生成任务管理系统"
echo "=========================================="

STOPPED_SOMETHING=false

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

# ==================== 停止 Go 后端 ====================
echo ""
echo "【Go后端】停止服务..."

# 方法1: 通过 PID 文件停止
GO_PID_FILE="log/go_backend.pid"
if [ -f "$GO_PID_FILE" ]; then
    PID=$(cat "$GO_PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "正在停止 Go 后端 (PID: $PID)..."
        kill $PID 2>/dev/null || true
        
        # 等待进程退出
        for i in {1..5}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                echo "✅ Go 后端已停止"
                rm -f "$GO_PID_FILE"
                STOPPED_SOMETHING=true
                break
            fi
            sleep 1
        done
        
        # 如果还在运行，强制停止
        if ps -p $PID > /dev/null 2>&1; then
            echo "强制停止 Go 后端..."
            kill -9 $PID 2>/dev/null || true
            rm -f "$GO_PID_FILE"
            STOPPED_SOMETHING=true
        fi
    else
        echo "Go 后端未运行（PID 文件存在但进程不存在）"
        rm -f "$GO_PID_FILE"
    fi
fi

# 方法2: 通过进程名查找并停止
GO_PIDS=$(pgrep -f "./server" 2>/dev/null || true)
if [ ! -z "$GO_PIDS" ]; then
    echo "发现 Go 后端进程，正在停止..."
    for pid in $GO_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 1
    # 强制停止仍在运行的进程
    GO_PIDS=$(pgrep -f "./server" 2>/dev/null || true)
    if [ ! -z "$GO_PIDS" ]; then
        for pid in $GO_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "✅ Go 后端已停止"
    STOPPED_SOMETHING=true
fi

# 方法3: 通过端口停止
BACKEND_PORT=8080
PORT_PID=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
if [ ! -z "$PORT_PID" ]; then
    echo "发现端口 $BACKEND_PORT 上的进程 (PID: $PORT_PID)，正在停止..."
    kill -9 $PORT_PID 2>/dev/null || true
    echo "✅ 端口 $BACKEND_PORT 已释放"
    STOPPED_SOMETHING=true
fi

if [ "$STOPPED_SOMETHING" = false ]; then
    echo "Go 后端未在运行"
fi

# ==================== 停止前端 ====================
echo ""
echo "【前端】停止开发服务器..."

STOPPED_SOMETHING=false

# 方法1: 通过 PID 文件停止
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
        rm -f "$FRONTEND_PID_FILE"
        echo "✅ 前端开发服务器已停止"
        STOPPED_SOMETHING=true
    else
        rm -f "$FRONTEND_PID_FILE"
    fi
fi

# 方法2: 通过进程名查找并停止 (vite 和 npm 进程)
VITE_PIDS=$(pgrep -f "vite" 2>/dev/null || true)
if [ ! -z "$VITE_PIDS" ]; then
    echo "发现 Vite 进程，正在停止..."
    for pid in $VITE_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 1
    VITE_PIDS=$(pgrep -f "vite" 2>/dev/null || true)
    if [ ! -z "$VITE_PIDS" ]; then
        for pid in $VITE_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "✅ Vite 进程已停止"
    STOPPED_SOMETHING=true
fi

# 方法3: 通过端口停止
FRONTEND_PORT=3000
PORT_PID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null || true)
if [ ! -z "$PORT_PID" ]; then
    echo "发现端口 $FRONTEND_PORT 上的进程 (PID: $PORT_PID)，正在停止..."
    kill -9 $PORT_PID 2>/dev/null || true
    echo "✅ 端口 $FRONTEND_PORT 已释放"
    STOPPED_SOMETHING=true
fi

if [ "$STOPPED_SOMETHING" = false ]; then
    echo "前端开发服务器未在运行"
fi

# ==================== 停止 Redis ====================
echo ""
echo "【Redis】检查 Redis 服务..."

REDIS_CONFIG=$(get_redis_config)
if [ ! -z "$REDIS_CONFIG" ]; then
    REDIS_HOST=$(echo "$REDIS_CONFIG" | sed -n '1p')
    REDIS_PORT=$(echo "$REDIS_CONFIG" | sed -n '2p')
else
    REDIS_HOST="localhost"
    REDIS_PORT="6379"
fi

if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "正在停止 Redis 服务 ($REDIS_HOST:$REDIS_PORT)..."
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" shutdown nosave 2>/dev/null || true
        sleep 1
        echo "✅ Redis 服务已停止"
    else
        echo "Redis 服务未运行"
    fi
else
    echo "未安装 redis-cli，跳过 Redis 检查"
fi

# ==================== 清理旧的 Python 后端进程（如有）====================
echo ""
echo "【清理】检查旧的 Python 后端进程..."

PYTHON_PIDS=$(pgrep -f "uvicorn.*app.app\|python3.*app/app.py" 2>/dev/null || true)
if [ ! -z "$PYTHON_PIDS" ]; then
    echo "发现旧的 Python 后端进程，正在停止..."
    for pid in $PYTHON_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 1
    PYTHON_PIDS=$(pgrep -f "uvicorn.*app.app\|python3.*app/app.py" 2>/dev/null || true)
    if [ ! -z "$PYTHON_PIDS" ]; then
        for pid in $PYTHON_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
    echo "✅ 旧的 Python 后端进程已停止"
fi

# 清理旧的 PID 文件
rm -f log/web_app.pid 2>/dev/null

echo ""
echo "=========================================="
echo "🛑 系统已停止"
echo "=========================================="
