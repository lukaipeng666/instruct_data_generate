#!/bin/bash
# 启动Web前端服务

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查并安装依赖
echo "检查依赖..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "安装Flask依赖..."
    pip3 install -r requirements_web.txt
fi

# 启动Web服务
echo "正在后台启动Web服务..."

# 创建日志目录
mkdir -p log

# 检查是否已经在运行
if [ -f log/web_app.pid ]; then
    PID=$(cat log/web_app.pid)
    if ps -p $PID > /dev/null; then
        echo "Web服务已经在运行中 (PID: $PID)"
        exit 0
    else
        rm log/web_app.pid
    fi
fi

# 使用 nohup 后台运行，并重定向输出到日志文件
# 这样即使断开连接，程序也会继续运行
nohup python3 web_app.py > log/web_app.log 2>&1 &
echo $! > log/web_app.pid

echo "Web服务已在后台启动 (PID: $(cat log/web_app.pid))"
echo "访问地址: http://localhost:5000"
echo "日志文件: log/web_app.log"
echo "提示: 可以使用 'tail -f log/web_app.log' 查看实时日志"

