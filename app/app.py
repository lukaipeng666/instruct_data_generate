#!/usr/bin/env python3
"""
Web前端应用 - 主入口文件
提供Web界面来配置和运行数据生成任务
"""

import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加路径以便正确导入模块
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, PROJECT_ROOT)  # 项目根目录（用于 database 等）
sys.path.insert(0, APP_DIR)  # app目录（用于 routes 等）

# 导入配置模块
from config import get_cors_config, get_web_config, get_frontend_url

# 导入数据库初始化
from database import init_database

# 导入所有路由模块
from routes import auth_routes, data_routes, task_routes, admin_routes, model_routes

app = FastAPI(title="数据生成任务管理", version="1.0.0")

# 从 config.yaml 读取 CORS 配置
_cors_config = get_cors_config()

# 配置CORS，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_config['origins'],
    allow_credentials=_cors_config['allow_credentials'],
    allow_methods=_cors_config['allow_methods'],
    allow_headers=_cors_config['allow_headers'],
)

# 初始化数据库
init_database()

# 注册所有路由
app.include_router(auth_routes.router)
app.include_router(data_routes.router)
app.include_router(task_routes.router)
app.include_router(model_routes.router)
app.include_router(admin_routes.router)


# 从配置获取前端和后端地址
_web_config = get_web_config()
_frontend_url = get_frontend_url()


@app.get('/')
def index():
    """API根路径 - 返回API信息"""
    return {
        "message": "数据生成任务管理系统 API",
        "version": "1.0.0",
        "frontend": f"请访问 {_frontend_url}",
        "docs": f"API文档: http://localhost:{_web_config['port']}/docs"
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=_web_config['host'], port=_web_config['port'])
