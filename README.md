# 数据生成任务管理系统

基于 Go + React 的分布式数据生成平台，支持多模型并行调用、任务管理和数据质量评估。

## 项目架构

```
├── cmd/server/          # Go 后端入口
├── internal/            # Go 后端核心代码
│   ├── handler/         # API 处理器
│   ├── service/         # 业务逻辑
│   ├── repository/      # 数据访问层
│   ├── models/          # 数据模型
│   ├── middleware/      # 中间件（认证、CORS等）
│   └── utils/           # 工具函数
├── frontend/            # React 前端 (Vite + TypeScript)
├── config/              # 配置文件
├── database/            # Python 数据库操作（供任务脚本使用）
├── develop/             # Python 数据生成逻辑
├── call_model/          # Python 模型调用模块
└── main.py              # Python 任务入口（Go 后端调用）
```

## 技术栈

- **后端**: Go 1.21+ (Gin + GORM + JWT)
- **前端**: React 18 + TypeScript + Vite + TailwindCSS
- **数据库**: SQLite
- **缓存**: Redis（任务进度、模型限流）
- **数据生成**: Python 3.10+（异步并行处理）

## 快速开始

### 环境要求

- Go 1.21+
- Node.js 16+
- Python 3.10+
- Redis（可选，用于任务进度）

### 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..
```

### 配置

编辑 `config/config.yaml`：

```yaml
# Web 服务配置
web_service:
  host: "0.0.0.0"
  port: 8080

# 前端配置
frontend:
  url: "http://localhost:3000"

# Redis 配置
redis_service:
  host: "localhost"
  port: 6379

# 模型服务配置
model_services:
  default_services:
    - "http://localhost:6466/v1"
  default_model: "/data/models/Qwen3-32B"
```

### 启动服务

```bash
# 一键启动（Redis + Go后端 + 前端）
./start.sh

# 停止服务
./stop.sh

# 查看状态
./status.sh
```

### 访问

- 前端页面: http://localhost:3000
- 后端 API: http://localhost:8080

## 默认账户

- 用户名: `admin`
- 密码: 见 `config/config.yaml` 中的配置

## 主要功能

- **用户认证**: JWT Token 认证，支持管理员和普通用户
- **数据文件管理**: 上传、下载、预览 JSONL 数据文件
- **任务管理**: 创建数据生成任务，实时查看进度
- **模型配置**: 管理多个模型服务，支持并发限流
- **数据评估**: 自动评分和人工确认生成数据
- **报告导出**: 导出任务统计和生成数据

## 日志

日志文件位于 `log/` 目录：

```bash
tail -f log/go_backend.log   # Go 后端日志
tail -f log/frontend.log     # 前端日志
tail -f log/redis.log        # Redis 日志
```

## API 文档

启动服务后访问: http://localhost:8080/swagger/index.html

## 开发

```bash
# 单独启动后端
go run cmd/server/main.go

# 单独启动前端
cd frontend && npm run dev
```

## License

MIT
