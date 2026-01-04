<div align="center">

# 🚀 数据生成任务管理系统

</div>

<div align="center">

基于 Go + React 的分布式数据生成平台，支持多模型并行调用、任务管理和数据质量评估。

[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go)](https://golang.org/)
[![React Version](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[功能特性](#-主要功能) • [快速开始](#-快速开始) • [文档](#-文档) • [贡献](#-贡献)

</div>

---

## 📁 项目架构

```
├── backend/               # Go 后端服务
│   ├── cmd/server/        # 应用入口
│   ├── internal/          # 核心业务逻辑
│   │   ├── config/        # 配置管理
│   │   ├── dto/           # 数据传输对象
│   │   ├── handler/       # HTTP 处理器
│   │   ├── middleware/    # 中间件
│   │   ├── models/        # 数据模型
│   │   ├── repository/    # 数据访问层
│   │   ├── router/        # 路由配置
│   │   ├── service/       # 业务逻辑
│   │   └── utils/         # 工具函数
│   └── pkg/               # 公共包
│       └── redis_limiter/ # Redis 限流器
│
├── frontend/              # React 前端
│   └── src/
│       ├── components/    # React 组件
│       ├── pages/         # 页面组件
│       ├── services/      # API 服务
│       ├── store/         # 状态管理
│       └── types/         # TypeScript 类型
│
├── call_model/            # 模型调用模块
├── develop/               # 数据生成逻辑
├── database/              # 数据库操作
├── main.py                # Python 任务入口
│
├── start.sh               # 一键启动脚本
├── stop.sh                # 停止服务脚本
└── status.sh              # 状态查看脚本
```

## 🛠️ 技术栈

| 类别 | 技术栈 |
|:---:|:---|
| **后端** | ![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat&logo=go) ![Gin](https://img.shields.io/badge/Gin-Web-Framework-green?style=flat) ![GORM](https://img.shields.io/badge/GORM-ORM-blue?style=flat) |
| **前端** | ![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react) ![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat&logo=typescript) ![Vite](https://img.shields.io/badge/Vite-Build-Tool-646CFF?style=flat&logo=vite) |
| **样式** | ![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-38B2AC?style=flat&logo=tailwind-css) |
| **数据库** | ![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=flat&logo=sqlite) |
| **缓存** | ![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=flat&logo=redis) |
| **数据处理** | ![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python) |

## ⚡ 快速开始

### 📋 环境要求

- ![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat) [Go 1.21+](https://golang.org/dl/)
- ![Node.js](https://img.shields.io/badge/Node.js-16+-339933?style=flat&logo=node.js) [Node.js 16+](https://nodejs.org/)
- ![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python) [Python 3.10+](https://www.python.org/)
- ![Redis](https://img.shields.io/badge/Redis-Optional-DC382D?style=flat&logo=redis) Redis（可选）

### 📦 安装步骤

#### 1️⃣ 克隆项目

```bash
git clone https://github.com/lukaipeng666/instruct_data_generate.git
cd instruct_data_generate
```

#### 2️⃣ 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..
```

#### 3️⃣ 配置项目

**复制示例配置文件：**

```bash
cp backend/config/config.example.yaml backend/config/config.yaml
```

**生成 JWT 密钥（生产环境必须使用）：**

```bash
openssl rand -base64 32
```

**生成管理员密码哈希：**

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw('你的密码'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))"
```

**编辑配置文件 `backend/config/config.yaml`：**

```yaml
# 项目根目录
project_root: "/path/to/your/project"

# JWT 认证配置
jwt:
  secret_key: "生成的JWT密钥"  # 填入上面生成的密钥
  algorithm: "HS256"
  expire_minutes: 43200  # 30天

# 管理员配置
admin:
  username: "admin"
  password: "生成的密码哈希"  # 填入上面生成的哈希值
```

> 💡 详细配置说明请参考 `backend/config/config.example.yaml`

#### 4️⃣ 启动服务

```bash
# 一键启动所有服务（Redis + Go后端 + 前端）
./start.sh

# 停止服务
./stop.sh

# 查看服务状态
./status.sh
```

#### 5️⃣ 访问应用

| 服务 | 地址 | 说明 |
|:---:|:---:|:---|
| 🎨 前端 | http://localhost:13000 | Web 界面 |
| 🔌 后端 API | http://localhost:18080 | RESTful API |
| 📚 API 文档 | http://localhost:18080/swagger/index.html | Swagger 文档 |

## 👤 默认账户

首次部署后，使用配置的管理员账户登录：

- **用户名**: `admin`
- **密码**: 在配置步骤中设置的密码

## ✨ 主要功能

<details>
<summary><b>🔐 用户认证</b></summary>

- JWT Token 认证机制
- 支持管理员和普通用户角色
- 安全的密码加密存储（bcrypt）
- Token 自动刷新机制
</details>

<details>
<summary><b>📁 数据文件管理</b></summary>

- 支持上传 CSV 和 JSONL 格式文件
- 在线预览和编辑数据
- 批量下载和格式转换
- 文件内容搜索和过滤
</details>

<details>
<summary><b>🎯 任务管理</b></summary>

- 创建和管理数据生成任务
- 实时查看任务进度
- 任务队列管理
- 支持任务暂停和恢复
</details>

<details>
<summary><b>⚙️ 模型配置</b></summary>

- 管理多个模型服务
- 配置并发限流策略
- 模型服务健康检查
- 动态负载均衡
</details>

<details>
<summary><b>📊 数据评估</b></summary>

- 自动质量评分
- 人工确认机制
- 批量审核功能
- 数据标注工具
</details>

<details>
<summary><b>📈 报告导出</b></summary>

- 导出任务统计数据
- 支持多种格式（JSONL、CSV）
- 自定义导出字段
- 批量导出功能
</details>

<details>
<summary><b>🔄 格式转换</b></summary>

- CSV ↔ JSONL 双向转换
- 批量文件转换
- 格式验证和错误提示
- 转换预览功能
</details>

## 📄 数据文件格式

### JSONL 格式

JSONL (JSON Lines) 是一种轻量级数据交换格式，每行包含一个独立的 JSON 对象。

**示例：**

```jsonl
{"meta": {"description": "示例对话"}, "turns": [{"role": "Human", "text": "你好"}, {"role": "Assistant", "text": "你好！有什么可以帮助你的吗？"}]}
{"meta": {"description": "另一个对话"}, "turns": [{"role": "Human", "text": "今天天气怎么样？"}, {"role": "Assistant", "text": "今天天气很好，适合外出活动。"}]}
```

### CSV 格式

CSV 文件支持特定的对话格式，包含 meta、Human 和 Assistant 列。

**格式要求：**
- 第一列必须为 `meta`
- Human/Assistant 列成对出现
- 支持多轮对话

**示例：**

```csv
meta,Human,Assistant,Human,Assistant
示例对话,你好,你好！有什么可以帮助你的吗？,再见,再见！
另一个对话,今天天气怎么样？,今天天气很好，适合外出活动。,谢谢,不客气！
```

**特殊规则：**
- `meta` 列为空时，自动使用上一行的值
- 支持任意轮数的对话
- 上传时自动转换为 JSONL 格式

## 🔧 开发指南

### 单独启动后端

```bash
# 运行 Go 后端
go run cmd/server/main.go

# 或使用 air 实现热重载（需要安装 air）
air
```

### 单独启动前端

```bash
cd frontend
npm run dev
```

### 查看日志

```bash
# Go 后端日志
tail -f log/go_backend.log

# 前端日志
tail -f log/frontend.log

# Redis 日志
tail -f log/redis.log
```

## 📚 文档

- [API 文档](http://localhost:18080/swagger/index.html) - Swagger 接口文档
- [配置指南](backend/config/config.example.yaml) - 详细配置说明
- [开发指南](#-开发指南) - 开发相关说明

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📝 License

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

感谢所有贡献者的支持！

---

<div align="center">

**[⬆ 返回顶部](#-数据生成任务管理系统)**

Made with ❤️ by [lukaipeng666](https://github.com/lukaipeng666)

</div>
