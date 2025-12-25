# BowenGen - 分布式数据生成任务管理系统

基于大语言模型的分布式对话数据生成平台，支持多服务并行处理，提供完整的 Web 管理界面。

## 功能特性

- **分布式数据生成**：支持多个 vLLM/OpenAI 兼容服务并行处理，最大化数据生成效率
- **任务管理**：任务创建、实时进度监控、任务停止与删除
- **模型管理**：支持配置多个模型服务，灵活切换
- **用户系统**：完整的用户注册、登录、权限管理（管理员/普通用户）
- **数据管理**：文件上传、数据预览、生成结果导出
- **实时进度**：基于 Redis 的任务进度追踪，支持 SSE 实时推送
- **数据质量评估**：自动评分机制，确保生成数据质量

## 系统架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React 前端    │────▶│  FastAPI 后端   │────▶│   vLLM 服务     │
│   (Port 3000)   │     │   (Port 5000)   │     │  (多服务并行)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  SQLite  │ │  Redis   │ │  日志    │
              │  数据库  │ │  缓存    │ │  系统    │
              └──────────┘ └──────────┘ └──────────┘
```

## 项目结构

```
bowengen/
├── app/                          # 后端应用目录
│   ├── app.py                    # FastAPI 主入口
│   ├── routes/                   # 路由模块
│   │   ├── auth_routes.py        # 认证相关路由
│   │   ├── data_routes.py        # 数据管理路由
│   │   ├── task_routes.py        # 任务管理路由
│   │   ├── model_routes.py       # 模型配置路由
│   │   └── admin_routes.py       # 管理员路由
│   └── services/                 # 服务层
│       └── task_manager.py       # 任务管理器
├── call_model/                   # 模型调用模块
│   └── model_call.py             # 统一模型调用接口
├── config/                       # 配置文件
│   ├── config.yaml               # 系统配置
│   ├── prompt_config.py          # 提示词配置
│   └── tools.py                  # 工具函数
├── database/                     # 数据库模块
│   ├── models.py                 # 数据模型定义
│   ├── auth.py                   # 认证服务
│   ├── file_service.py           # 文件服务
│   ├── user_service.py           # 用户服务
│   └── generated_data_service.py # 生成数据服务
├── develop/                      # 核心生成模块
│   ├── pipeline_gen.py           # 分布式管道生成器
│   ├── single_gen.py             # 单服务数据生成器
│   ├── file_reader.py            # 文件读取器
│   └── report_generator.py       # 报告生成器
├── frontend/                     # 前端项目 (React + Vite)
│   ├── src/
│   │   ├── components/           # React 组件
│   │   ├── pages/                # 页面组件
│   │   ├── services/             # API 服务
│   │   └── store/                # 状态管理 (Zustand)
│   └── package.json
├── main.py                       # 命令行入口
├── start.sh                      # 启动脚本
├── stop.sh                       # 停止脚本
└── requirements.txt              # Python 依赖
```

## 环境要求

### 后端
- Python 3.8+
- Redis (可选，用于任务进度追踪)

### 前端
- Node.js 16+
- npm 或 yarn

### 模型服务
- vLLM 或任何 OpenAI 兼容的 API 服务

## 快速开始

### 1. 克隆项目

```bash
git clone ssh://git@code.in.wezhuiyi.com:60022/nlp-algorithm/bowenability/bowengen.git
cd bowengen
git checkout v.2.0.1
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate    # Windows

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 3. 配置

编辑 `config/config.yaml`：

```yaml
# Web 服务配置
web_service:
  host: "0.0.0.0"
  port: 5000

# Redis 服务配置（用于模型调用限流和任务进度）
redis_service:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  max_wait_time: 300
  default_max_concurrency: 16
```

### 4. 启动服务

```bash
# 一键启动（推荐）
./start.sh

# 或手动启动
# 启动后端
python -m uvicorn app.app:app --host 0.0.0.0 --port 5000

# 启动前端（新终端）
cd frontend && npm run dev
```

### 5. 访问系统

- 前端界面：http://localhost:3000
- API 文档：http://localhost:5000/docs
- 后端 API：http://localhost:5000

## 命令行使用

除了 Web 界面，还支持命令行方式运行：

```bash
python main.py \
    --services http://localhost:6466/v1 http://localhost:6467/v1 \
    --model /data/models/Qwen3-32B \
    --file-id 1 \
    --user-id 1 \
    --task-id my_task \
    --batch-size 16 \
    --max-concurrent 16 \
    --min-score 8 \
    --task-type entity_extraction \
    --variants-per-sample 3 \
    --data-rounds 10 \
    --directions "信用卡年费" "股票爆仓" "基金赎回"
```

### 命令行参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--services` | localhost:6466-6473 | API 服务地址列表 |
| `--model` | /data/models/Qwen3-32B | 模型路径 |
| `--file-id` | 必填 | 数据库中的文件 ID |
| `--user-id` | 必填 | 用户 ID |
| `--task-id` | 必填 | 任务 ID |
| `--batch-size` | 16 | 批处理大小 |
| `--max-concurrent` | 16 | 最大并发数 |
| `--min-score` | 8 | 最低评分要求 (0-10) |
| `--task-type` | entity_extraction | 任务类型 |
| `--variants-per-sample` | 3 | 每个样本生成的变体数 |
| `--data-rounds` | 10 | 数据使用轮次 |
| `--retry-times` | 3 | API 调用重试次数 |
| `--directions` | - | 需要构造的题材列表 |
| `--is-vllm` | True | 是否使用 vLLM 格式 |
| `--top-p` | 1.0 | top_p 采样参数 |
| `--max-tokens` | 8192 | 最大生成 token 数 |
| `--timeout` | 600 | API 超时时间（秒）|

## API 接口

### 认证相关
- `POST /api/login` - 用户登录
- `POST /api/register` - 用户注册
- `GET /api/me` - 获取当前用户信息

### 任务管理
- `POST /api/start` - 启动任务
- `GET /api/tasks` - 获取任务列表
- `GET /api/progress/{task_id}` - 获取任务进度 (SSE)
- `GET /api/task_progress/{task_id}` - 获取任务进度 (JSON)
- `POST /api/stop/{task_id}` - 停止任务
- `DELETE /api/task/{task_id}` - 删除任务

### 数据管理
- `POST /api/upload` - 上传数据文件
- `GET /api/files` - 获取文件列表
- `GET /api/generated-data/{task_id}` - 获取生成数据
- `GET /api/export/{task_id}` - 导出数据

### 模型管理
- `GET /api/models` - 获取模型列表
- `POST /api/models` - 添加模型配置
- `PUT /api/models/{id}` - 更新模型配置
- `DELETE /api/models/{id}` - 删除模型配置

## 停止服务

```bash
./stop.sh
```

## 技术栈

### 后端
- **FastAPI** - 高性能 Web 框架
- **SQLAlchemy** - ORM 数据库操作
- **SQLite** - 轻量级数据库
- **Redis** - 缓存和任务进度追踪
- **python-jose** - JWT 认证

### 前端
- **React 18** - UI 框架
- **Vite** - 构建工具
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **Zustand** - 状态管理
- **Axios** - HTTP 客户端

## 许可证

内部项目，仅供授权用户使用。

## 更新日志

### v2.0.1 (2024-12)
- 新增前后端分离架构
- 添加用户认证和权限管理
- 支持模型配置管理
- 实现基于 Redis 的任务进度追踪
- 生成数据存储到 SQL 数据库
- 优化分布式并行处理性能
