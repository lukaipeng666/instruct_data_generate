# 数据生成任务管理系统

基于 Go + React 的分布式数据生成平台，支持多模型并行调用、任务管理和数据质量评估。

## 项目架构

```
├── backend/               # Go 后端服务
│   ├── cmd/server/        # Go 后端入口
│   ├── internal/          # Go 后端核心代码
│   │   ├── config/        # 配置管理
│   │   ├── dto/           # 数据传输对象
│   │   ├── handler/       # API 处理器
│   │   ├── middleware/    # 中间件（认证、CORS等）
│   │   ├── models/        # 数据模型
│   │   ├── repository/    # 数据访问层
│   │   ├── router/        # 路由配置
│   │   ├── service/       # 业务逻辑
│   │   └── utils/         # 工具函数
│   └── pkg/               # Go 包
│       └── redis_limiter/ # Redis 限流器
├── frontend/              # React 前端 (Vite + TypeScript)
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── pages/         # 页面组件
│   │   ├── services/      # API 服务
│   │   ├── store/         # 状态管理
│   │   └── types/         # TypeScript 类型定义
├── config/                # 配置文件
├── database/              # Python 数据库操作
├── develop/               # Python 数据生成逻辑
├── call_model/            # Python 模型调用模块
├── main.py                # Python 任务入口（Go 后端调用）
├── start.sh               # 启动脚本
├── stop.sh                # 停止脚本
└── status.sh              # 状态查看脚本
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
# 服务配置文件

# 项目根目录（用于执行 Python 脚本）
project_root: "/Users/lukaipeng2/Desktop/GEN_GO_PYTHON/gen_go"

# Web 服务配置
web_service:
  host: "0.0.0.0"
  port: 8080
  # 生产模式：禁用 API 文档（/docs, /redoc, /openapi.json）
  # 开发时设为 false，部署时设为 true
  production_mode: false

# 前端配置
frontend:
  url: "http://localhost:3000"

# CORS 配置（跨域访问）
cors:
  # 允许的跨域源列表
  origins:
    - "http://localhost:3000"
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"

# JWT 认证配置
jwt:
  # 密钥（生产环境请修改为随机字符串）
  # 留空则自动生成随机密钥（每次重启会变化）
  secret_key: "5K2UTSU7eIztM-qyayws7F47Nd48AfuXYqRPpRnUdu6rQiydUbV7dvrMhMhSXWMt6_hq6rjOIRaW1VJp81dlNQ"
  # 加密算法
  algorithm: "HS256"
  # Token 过期时间（分钟），默认30天
  expire_minutes: 43200

# 管理员配置
admin:
  # 默认管理员用户名
  username: "admin"
  # 默认管理员密码哈希值（使用 bcrypt 加密）
  # 如需修改密码，请使用 bcrypt 生成新的哈希值替换此处
  # 生成方式: python3 -c "import bcrypt; print(bcrypt.hashpw('你的密码'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))"
  password: "$2b$12$PAofQYRSUA3d9axVq/gVIOs6UTjalXW9Q0Rrm4xgoLG8JEa8rs3lO"

# Redis 服务配置（用于模型调用限流和任务进度）
redis_service:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  # 等待并发槽位的最大时间（秒）
  max_wait_time: 300
  # 默认最大并发数（当模型未配置时使用）
  default_max_concurrency: 16

# 默认模型服务配置
model_services:
  # 默认 API 服务地址列表
  default_services:
    - "http://localhost:6466/v1"
    - "http://localhost:6467/v1"
    - "http://localhost:6468/v1"
    - "http://localhost:6469/v1"
    - "http://localhost:6470/v1"
    - "http://localhost:6471/v1"
    - "http://localhost:6472/v1"
    - "http://localhost:6473/v1"
  # 默认模型路径
  default_model: "/data/models/Qwen3-32B"
  # 默认 API Key
  default_api_key: ""
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
- **数据文件管理**: 上传、下载、预览 CSV 和 JSONL 数据文件
- **任务管理**: 创建数据生成任务，实时查看进度
- **模型配置**: 管理多个模型服务，支持并发限流
- **数据评估**: 自动评分和人工确认生成数据
- **报告导出**: 导出任务统计和生成数据
- **数据格式转换**: 支持 CSV 与 JSONL 之间的相互转换

## 数据文件格式

### JSONL 格式

JSONL (JSON Lines) 是一种数据交换格式，每行包含一个独立的 JSON 对象。上传的文件每行应包含一个有效的 JSON 对象，通常用于存储对话数据或结构化数据。

示例格式：

```jsonl
{"meta": {"meta_description": "示例对话"}, "turns": [{"role": "Human", "text": "你好"}, {"role": "Assistant", "text": "你好！有什么可以帮助你的吗？"}]}
{"meta": {"meta_description": "另一个对话"}, "turns": [{"role": "Human", "text": "今天天气怎么样？"}, {"role": "Assistant", "text": "今天天气很好，适合外出活动。"}]}
```

### CSV 格式

CSV (Comma-Separated Values) 文件支持特定的对话格式，包含 meta、Human 和 Assistant 列，用于表示对话元数据和多轮对话。

#### CSV 文件格式要求

1. **表头格式**: CSV 文件必须包含表头，第一列为 `meta`，后续列按 Human/Assistant 成对出现
2. **列命名**: 每个对话轮次应包含 Human 和 Assistant 列
3. **元数据**: `meta` 列用于存储对话的元数据描述

#### CSV 文件示例

```csv
meta,Human,Assistant,Human,Assistant
示例对话,你好,你好！有什么可以帮助你的吗？,再见,再见！
另一个对话,今天天气怎么样？,今天天气很好，适合外出活动。,谢谢,不客气！
```

#### CSV 特殊处理规则

- 如果 `meta` 列为空，将使用上一行的 `meta` 值（支持共享元数据）
- 支持多轮对话，每对 Human/Assistant 列代表一轮对话
- 系统会自动将 CSV 文件转换为 JSONL 格式存储

### 数据格式转换

系统支持以下格式转换：

1. **CSV → JSONL**: 上传 CSV 文件时自动转换
2. **JSONL → CSV**: 下载时可选择 CSV 格式
3. **批量转换**: 支持批量转换多个文件

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
