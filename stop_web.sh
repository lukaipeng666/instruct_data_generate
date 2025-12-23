#!/bin/bash
# 停止Web前端服务

PID_FILE="log/web_app.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "正在停止 Web 服务 (PID: $PID)..."
    
    # 尝试优雅停止
    kill $PID
    
    # 等待进程退出
    for i in {1..5}; do
        if ! ps -p $PID > /dev/null; then
            echo "Web 服务已成功停止。"
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done
    
    # 如果还在运行，强制停止
    echo "服务未能在 5 秒内停止，正在强制结束..."
    kill -9 $PID
    rm "$PID_FILE"
    echo "Web 服务已强制停止。"
else
    echo "未找到 PID 文件 ($PID_FILE)，Web 服务可能未运行。"
    
    # 尝试通过进程名查找（备选方案）
    PID=$(pgrep -f "python3 web_app.py")
    if [ ! -z "$PID" ]; then
        echo "发现匹配的进程 (PID: $PID)，正在停止..."
        kill $PID
        echo "已发送停止信号。"
    fi
fi

