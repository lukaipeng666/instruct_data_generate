# Python 后端重构为 Go + Gin 后端需求文档

## 1. 项目概述

### 1.1 当前系统（Python）
- **框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy ORM
- **缓存**: Redis
- **认证**: JWT (JSON Web Tokens)
- **前端**: React + TypeScript

### 1.2 目标系统（Go）
- **框架**: Gin Web Framework
- **数据库**: SQLite + GORM ORM
- **缓存**: Redis (go-redis/redis/v8)
- **认证**: JWT (golang-jwt/jwt/v5)
- **前端**: 保持现有 React + TypeScript（无需改动）

### 1.3 核心业务
本系统是一个**AI 数据生成管理平台**，主要功能包括：
- 用户管理和权限控制
- 数据文件上传和管理（JSONL/CSV格式）
- AI 模型配置和调用
- 分布式数据生成任务管理
- 生成数据审核和导出
- 文件格式转换
- 任务进度实时监控（SSE）

---

## 2. 系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (React)                        │
│              http://localhost:3000                      │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Go + Gin 后端服务                          │
│              (单体应用)                                  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  路由层  │──│ 中间件   │──│ 处理器   │             │
│  │ (Routes) │  │(Middleware)│ │(Handlers)│             │
│  └──────────┘  └──────────┘  └──────────┘             │
│  ┌──────────────────────────────────────────┐          │
│  │           业务逻辑层 (Services)           │          │
│  │  - AuthService                           │          │
│  │  - TaskService                           │          │
│  │  - DataFileService                       │          │
│  │  - ModelService                          │          │
│  │  - GeneratedDataService                  │          │
│  │  - FileConversionService                 │          │
│  └──────────────────────────────────────────┘          │
│  ┌──────────────────────────────────────────┐          │
│  │           数据访问层 (Repositories)       │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
                     │                │
                     ▼                ▼
         ┌───────────────────┐  ┌──────────────┐
         │    SQLite 数据库   │  │   Redis 缓存 │
         │   + GORM ORM      │  │  (进度跟踪)   │
         └───────────────────┘  └──────────────┘
                     │
                     ▼
         ┌──────────────────────────────┐
         │   外部 AI 模型服务 (vLLM)     │
         │  http://localhost:6466-6473  │
         └──────────────────────────────┘
```

### 2.2 项目目录结构

```
gen-go/
├── cmd/
│   └── server/
│       └── main.go                 # 应用入口
├── internal/
│   ├── config/
│   │   ├── config.go              # 配置结构定义
│   │   ├── config.yaml            # 配置文件
│   │   └── loader.go              # 配置加载器
│   ├── models/
│   │   ├── user.go                # 用户模型
│   │   ├── task.go                # 任务模型
│   │   ├── data_file.go           # 数据文件模型
│   │   ├── generated_data.go      # 生成数据模型
│   │   └── model_config.go        # 模型配置
│   ├── repository/
│   │   ├── user_repository.go     # 用户数据访问
│   │   ├── task_repository.go     # 任务数据访问
│   │   ├── data_file_repository.go
│   │   ├── generated_data_repository.go
│   │   └── model_config_repository.go
│   ├── service/
│   │   ├── auth_service.go        # 认证服务
│   │   ├── task_service.go        # 任务管理服务
│   │   ├── data_file_service.go   # 文件管理服务
│   │   ├── model_service.go       # 模型服务
│   │   ├── generated_data_service.go
│   │   ├── file_conversion_service.go
│   │   └── task_manager.go        # 任务执行器
│   ├── handler/
│   │   ├── auth_handler.go        # 认证处理器
│   │   ├── task_handler.go        # 任务处理器
│   │   ├── data_file_handler.go   # 文件处理器
│   │   ├── model_handler.go       # 模型处理器
│   │   ├── generated_data_handler.go
│   │   ├── file_conversion_handler.go
│   │   ├── report_handler.go      # 报告处理器
│   │   └── admin_handler.go       # 管理员处理器
│   ├── middleware/
│   │   ├── cors.go                # CORS 中间件
│   │   ├── auth.go                # JWT 认证中间件
│   │   ├── admin.go               # 管理员权限中间件
│   │   └── logger.go              # 日志中间件
│   ├── router/
│   │   └── router.go              # 路由注册
│   ├── dto/
│   │   ├── auth_dto.go            # 认证相关 DTO
│   │   ├── task_dto.go            # 任务相关 DTO
│   │   ├── data_file_dto.go
│   │   └── model_dto.go
│   └── utils/
│       ├── jwt.go                 # JWT 工具
│       ├── password.go            # 密码哈希
│       ├── validator.go           # 数据验证
│       ├── response.go            # 统一响应格式
│       └── file_utils.go          # 文件处理工具
├── pkg/
│   ├── model_caller/
│   │   └── model_caller.go       # 模型调用客户端
│   └── data_generator/
│       ├── pipeline.go           # 分布式生成器
│       ├── single_gen.go         # 单个生成器
│       └── evaluator.go          # 数据评估器
├── migrations/
│   └── init.sql                   # 数据库初始化脚本
├── config.yaml                    # 主配置文件（根目录）
├── go.mod
├── go.sum
└── README.md
```

---

## 3. 数据库设计

### 3.1 数据库迁移
- Python SQLAlchemy → Go GORM
- 保持 SQLite 数据库
- 数据库表结构完全兼容

### 3.2 表结构定义

#### 3.2.1 users 表
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
```

**GORM Model**:
```go
type User struct {
    ID           uint      `gorm:"primarykey" json:"id"`
    Username     string    `gorm:"uniqueIndex;size:50;not null" json:"username"`
    PasswordHash string    `gorm:"size:255;not null" json:"-"`
    IsActive     bool      `gorm:"default:true" json:"is_active"`
    IsAdmin      bool      `gorm:"default:false" json:"is_admin"`
    CreatedAt    time.Time `json:"created_at"`
    UpdatedAt    time.Time `json:"updated_at"`

    // 关联
    Tasks       []Task       `gorm:"foreignKey:UserID;constraint:OnDelete:CASCADE" json:"tasks,omitempty"`
    DataFiles   []DataFile   `gorm:"foreignKey:UserID;constraint:OnDelete:CASCADE" json:"data_files,omitempty"`
    GeneratedData []GeneratedData `gorm:"foreignKey:UserID" json:"generated_data,omitempty"`
}
```

#### 3.2.2 model_configs 表
```sql
CREATE TABLE model_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    api_url VARCHAR(255) NOT NULL,
    api_key VARCHAR(255) DEFAULT 'sk-xxxxx',
    model_path VARCHAR(500) NOT NULL,
    max_concurrent INTEGER DEFAULT 16,
    temperature REAL DEFAULT 1.0,
    top_p REAL DEFAULT 1.0,
    max_tokens INTEGER DEFAULT 2048,
    is_vllm BOOLEAN DEFAULT 1,
    timeout INTEGER DEFAULT 600,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**GORM Model**:
```go
type ModelConfig struct {
    ID            uint    `gorm:"primarykey" json:"id"`
    Name          string  `gorm:"uniqueIndex;size:100;not null" json:"name"`
    APIURL        string  `gorm:"size:255;not null" json:"api_url"`
    APIKey        string  `gorm:"size:255;default:'sk-xxxxx'" json:"api_key"`
    ModelPath     string  `gorm:"size:500;not null" json:"model_path"`
    MaxConcurrent int     `gorm:"default:16" json:"max_concurrent"`
    Temperature   float64 `gorm:"default:1.0" json:"temperature"`
    TopP          float64 `gorm:"default:1.0" json:"top_p"`
    MaxTokens     int     `gorm:"default:2048" json:"max_tokens"`
    IsVLLM        bool    `gorm:"default:true" json:"is_vllm"`
    Timeout       int     `gorm:"default:600" json:"timeout"`
    Description   string  `gorm:"type:text" json:"description"`
    IsActive      bool    `gorm:"default:true" json:"is_active"`
    CreatedAt     time.Time `json:"created_at"`
    UpdatedAt     time.Time `json:"updated_at"`
}
```

#### 3.2.3 tasks 表
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'running',
    params TEXT,
    result TEXT,
    error_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_tasks_task_id ON tasks(task_id);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
```

**GORM Model**:
```go
type Task struct {
    ID           uint      `gorm:"primarykey" json:"id"`
    TaskID       string    `gorm:"uniqueIndex;size:100;not null" json:"task_id"`
    UserID       uint      `gorm:"not null;index" json:"user_id"`
    Status       string    `gorm:"size:20;default:'running'" json:"status"`
    Params       string    `gorm:"type:text" json:"params"`
    Result       string    `gorm:"type:text" json:"result"`
    ErrorMessage string    `gorm:"type:text" json:"error_message"`
    StartedAt    time.Time `json:"started_at"`
    FinishedAt   *time.Time `json:"finished_at"`

    // 关联
    User          User           `gorm:"foreignKey:UserID" json:"user,omitempty"`
    GeneratedData []GeneratedData `gorm:"foreignKey:TaskID" json:"generated_data,omitempty"`
}
```

#### 3.2.4 data_files 表
```sql
CREATE TABLE data_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    file_content BLOB NOT NULL,
    file_size INTEGER NOT NULL,
    content_type VARCHAR(100) DEFAULT 'application/x-jsonlines',
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_data_files_user_id ON data_files(user_id);
```

**GORM Model**:
```go
type DataFile struct {
    ID          uint      `gorm:"primarykey" json:"id"`
    Filename    string    `gorm:"size:255;not null" json:"filename"`
    FileContent []byte    `gorm:"type:blob;not null" json:"-"`
    FileSize    int       `gorm:"not null" json:"file_size"`
    ContentType string    `gorm:"size:100;default:'application/x-jsonlines'" json:"content_type"`
    UserID      uint      `gorm:"not null;index" json:"user_id"`
    CreatedAt   time.Time `json:"created_at"`
    UpdatedAt   time.Time `json:"updated_at"`

    // 关联
    User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}
```

#### 3.2.5 generated_data 表
```sql
CREATE TABLE generated_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(100) NOT NULL,
    user_id INTEGER NOT NULL,
    data_content TEXT NOT NULL,
    model_score REAL,
    rule_score INTEGER,
    retry_count INTEGER DEFAULT 0,
    generation_model VARCHAR(255),
    task_type VARCHAR(50),
    is_confirmed BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

CREATE INDEX idx_generated_data_task_id ON generated_data(task_id);
CREATE INDEX idx_generated_data_user_id ON generated_data(user_id);
```

**GORM Model**:
```go
type GeneratedData struct {
    ID              uint      `gorm:"primarykey" json:"id"`
    TaskID          string    `gorm:"size:100;not null;index" json:"task_id"`
    UserID          uint      `gorm:"not null;index" json:"user_id"`
    DataContent     string    `gorm:"type:text;not null" json:"data_content"`
    ModelScore      *float64  `json:"model_score"`
    RuleScore       *int      `json:"rule_score"`
    RetryCount      int       `gorm:"default:0" json:"retry_count"`
    GenerationModel string    `gorm:"size:255" json:"generation_model"`
    TaskType        string    `gorm:"size:50" json:"task_type"`
    IsConfirmed     bool      `gorm:"default:false" json:"is_confirmed"`
    CreatedAt       time.Time `json:"created_at"`
    UpdatedAt       time.Time `json:"updated_at"`

    // 关联
    User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
    Task Task `gorm:"foreignKey:TaskID" json:"task,omitempty"`
}
```

---

## 4. API 接口设计

### 4.1 统一响应格式

```go
type Response struct {
    Code    int         `json:"code"`    // 状态码
    Message string      `json:"message"` // 消息
    Data    interface{} `json:"data"`    // 数据
}
```

### 4.2 认证相关接口 (`/api`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | `/api/register` | 用户注册 | 公开 |
| POST | `/api/login` | 用户登录 | 公开 |
| GET | `/api/me` | 获取当前用户信息 | 用户 |
| POST | `/api/logout` | 用户登出 | 用户 |

#### 4.2.1 用户注册
**请求**:
```json
POST /api/register
{
    "username": "testuser",
    "password": "password123"
}
```

**响应**:
```json
{
    "code": 200,
    "message": "注册成功",
    "data": {
        "id": 1,
        "username": "testuser",
        "is_active": true,
        "is_admin": false
    }
}
```

#### 4.2.2 用户登录
**请求**:
```json
POST /api/login
{
    "username": "testuser",
    "password": "password123"
}
```

**响应**:
```json
{
    "code": 200,
    "message": "登录成功",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "username": "testuser",
            "is_admin": false
        }
    }
}
```

### 4.3 任务管理接口 (`/api`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/tasks` | 获取任务列表 | 用户 |
| POST | `/api/start` | 启动新任务 | 用户 |
| GET | `/api/status/:task_id` | 获取任务状态 | 用户 |
| GET | `/api/progress/:task_id` | SSE 获取任务进度 | 用户 |
| POST | `/api/stop/:task_id` | 停止任务 | 用户 |
| DELETE | `/api/task/:task_id` | 删除任务 | 用户 |
| GET | `/api/active_task` | 获取运行中的任务 | 用户 |
| GET | `/api/task_types` | 获取任务类型列表 | 用户 |

#### 4.3.1 启动任务
**请求**:
```json
POST /api/start
{
    "file_id": 1,
    "task_type": "entity_extraction",
    "batch_size": 5,
    "max_concurrent": 5,
    "min_score": 8,
    "variants_per_sample": 3,
    "data_rounds": 3,
    "directions": ["信用卡年费"],
    "special_prompt": ""
}
```

**响应**:
```json
{
    "code": 200,
    "message": "任务已启动",
    "data": {
        "task_id": "task_20250128_123456",
        "status": "running"
    }
}
```

#### 4.3.2 任务进度 (SSE)
```
GET /api/progress/:task_id
```

响应格式（Server-Sent Events）:
```
data: {"type": "log", "message": "开始处理..."}

data: {"type": "progress", "current": 50, "total": 100, "percent": 50}

data: {"type": "complete", "status": "finished"}
```

### 4.4 数据文件管理接口 (`/api/data_files`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/data_files` | 获取文件列表 | 用户 |
| POST | `/api/data_files/upload` | 上传文件 | 用户 |
| GET | `/api/data_files/:id` | 获取文件详情 | 用户 |
| GET | `/api/data_files/:id/download` | 下载文件 | 用户 |
| GET | `/api/data_files/:id/download_csv` | 下载CSV格式 | 用户 |
| GET | `/api/data_files/:id/content` | 查看文件内容 | 用户 |
| PUT | `/api/data_files/:id/content/:index` | 更新单条数据 | 用户 |
| POST | `/api/data_files/:id/content` | 添加新数据 | 用户 |
| DELETE | `/api/data_files/:id/content/batch` | 批量删除数据 | 用户 |
| DELETE | `/api/data_files/:id` | 删除文件 | 用户 |
| POST | `/api/data_files/batch_delete` | 批量删除文件 | 用户 |
| POST | `/api/data_files/batch_download` | 批量下载 | 用户 |

### 4.5 文件转换接口 (`/api`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | `/api/data_files/batch_convert` | 批量转换格式 | 用户 |
| POST | `/api/convert_files` | 上传并转换 | 用户 |

### 4.6 生成数据接口 (`/api/generated_data`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/generated_data` | 获取生成数据列表 | 用户 |
| POST | `/api/generated_data/batch_update` | 批量更新数据 | 用户 |
| POST | `/api/generated_data/batch_confirm` | 批量确认数据 | 用户 |
| GET | `/api/generated_data/export` | 导出数据 | 用户 |

### 4.7 报告接口 (`/api/reports`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/reports` | 获取报告列表 | 用户 |
| GET | `/api/reports/:task_id` | 获取任务报告 | 用户 |
| GET | `/api/reports/:task_id/download` | 下载报告数据 | 用户 |

### 4.8 模型接口 (`/api`)

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/models` | 获取激活的模型列表 | 用户 |
| POST | `/api/model-call` | 模型调用代理（带限流） | 用户 |

### 4.9 管理员接口 (`/api/admin`)

#### 4.9.1 用户管理
| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/admin/users` | 获取所有用户 | 管理员 |
| DELETE | `/api/admin/users/:id` | 删除用户 | 管理员 |
| GET | `/api/admin/users/:id/reports` | 获取用户报告 | 管理员 |
| GET | `/api/admin/users/:id/reports/:task_id/download` | 下载用户报告 | 管理员 |

#### 4.9.2 模型管理
| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/admin/models` | 获取所有模型配置 | 管理员 |
| POST | `/api/admin/models` | 创建模型配置 | 管理员 |
| PUT | `/api/admin/models/:id` | 更新模型配置 | 管理员 |
| DELETE | `/api/admin/models/:id` | 删除模型配置 | 管理员 |

#### 4.9.3 任务管理
| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | `/api/admin/tasks` | 获取所有任务 | 管理员 |
| DELETE | `/api/admin/tasks/:id` | 删除任务记录 | 管理员 |

---

## 5. 核心功能模块

### 5.1 认证与授权

#### 5.1.1 JWT 认证流程
```
1. 用户登录 → 验证用户名密码
2. 生成 JWT Token（包含 user_id, username, is_admin）
3. 返回 Token 给客户端
4. 客户端每次请求在 Header 携带 Token
5. 中间件验证 Token 有效性
6. 解析 Token 获取用户信息
```

**关键实现**:
```go
// 生成 Token
func GenerateToken(userID uint, username string, isAdmin bool) (string, error)

// 验证 Token
func ValidateToken(tokenString string) (*jwt.Claims, error)

// 中间件
func AuthMiddleware() gin.HandlerFunc
```

#### 5.1.2 密码哈希
使用 `golang.org/x/crypto/bcrypt` 进行密码哈希
```go
// 哈希密码
func HashPassword(password string) (string, error)

// 验证密码
func CheckPassword(password, hash string) error
```

### 5.2 任务管理

#### 5.2.1 任务生命周期
```
创建 → 运行中 → 完成/失败/停止
 ↓
内存状态同步 + 数据库持久化 + Redis 进度跟踪
```

#### 5.2.2 任务执行器 (TaskManager)
```go
type TaskManager struct {
    db        *gorm.DB
    redis     *redis.Client
    tasks     map[string]*TaskContext // 内存任务状态
    mutex     sync.RWMutex
}

type TaskContext struct {
    TaskID    string
    UserID    uint
    Status    string
    Cancel    context.CancelFunc // 用于取消任务
    Progress  chan TaskProgress
}

// 启动任务
func (tm *TaskManager) StartTask(req *StartTaskRequest) (*Task, error)

// 停止任务
func (tm *TaskManager) StopTask(taskID string, userID uint) error

// 获取任务进度
func (tm *TaskManager) GetProgress(taskID string) <-chan TaskProgress
```

#### 5.2.3 实时进度推送 (SSE)
```go
func (h *TaskHandler) GetProgress(c *gin.Context) {
    taskID := c.Param("task_id")

    // 设置 SSE 响应头
    c.Header("Content-Type", "text/event-stream")
    c.Header("Cache-Control", "no-cache")
    c.Header("Connection", "keep-alive")

    // 获取进度通道
    progressChan := h.taskManager.GetProgress(taskID)

    // 发送进度事件
    for progress := range progressChan {
        data, _ := json.Marshal(progress)
        fmt.Fprintf(c.Writer, "data: %s\n\n", data)
        c.Writer.Flush()
    }
}
```

### 5.3 分布式数据生成

#### 5.3.1 Pipeline 生成器
```go
type PipelineGenerator struct {
    services   []string  // 模型服务地址列表
    model      string
    apiKeys    map[string]string
    redis      *redis.Client
    db         *gorm.DB
}

// 生成数据（多服务并行）
func (pg *PipelineGenerator) GenerateData(ctx context.Context, req *GenerateRequest) (*GenerateResult, error) {
    // 1. 从数据库读取样本数据
    samples, err := pg.loadSamples(req.FileID, req.UserID)

    // 2. 分割样本到各个服务
    sampleParts := pg.splitSamples(samples, len(pg.services))

    // 3. 创建并行任务
    var wg sync.WaitGroup
    results := make(chan *ServiceResult, len(pg.services))

    for i, service := range pg.services {
        wg.Add(1)
        go func(serviceIdx int, apiBase string, samples []Sample) {
            defer wg.Done()
            result := pg.processService(ctx, serviceIdx, apiBase, samples, req)
            results <- result
        }(i, service, sampleParts[i])
    }

    // 4. 等待所有任务完成
    go func() {
        wg.Wait()
        close(results)
    }()

    // 5. 聚合结果
    return pg.aggregateResults(results)
}
```

#### 5.3.2 单个服务处理
```go
func (pg *PipelineGenerator) processService(
    ctx context.Context,
    serviceIdx int,
    apiBase string,
    samples []Sample,
    req *GenerateRequest,
) *ServiceResult {
    // 批量处理样本
    for i := 0; i < len(samples); i += req.BatchSize {
        end := min(i+req.BatchSize, len(samples))
        batch := samples[i:end]

        // 并发调用模型
        generatedData := pg.processBatch(ctx, apiBase, batch, req)

        // 保存到数据库
        pg.saveToDatabase(generatedData, req.TaskID, req.UserID)

        // 更新 Redis 进度
        pg.updateProgress(req.TaskID, serviceIdx, i, len(samples))
    }

    return &ServiceResult{Success: true, OutputCount: len(samples)}
}
```

### 5.4 文件格式转换

#### 5.4.1 支持的转换
- CSV → JSONL
- JSONL → CSV
- UTF-8-BOM → UTF-8

```go
type FileConverter struct{}

// CSV 转 JSONL
func (fc *FileConverter) CsvToJsonl(csvData []byte) ([]byte, error)

// JSONL 转 CSV
func (fc *FileConverter) JsonlitToCsv(jsonlData []byte) ([]byte, error)

// 批量转换
func (fc *FileConverter) BatchConvert(fileIDs []uint, targetFormat string) ([]ConvertedFile, error)
```

### 5.5 模型调用

#### 5.5.1 模型调用客户端
```go
type ModelCaller struct {
    client     *http.Client
    apiBase    string
    apiKey     string
    model      string
    timeout    time.Duration
}

// 调用模型（支持 OpenAI/vLLM 格式）
func (mc *ModelCaller) Call(ctx context.Context, messages []Message, options *CallOptions) (*ModelResponse, error)

// 流式调用
func (mc *ModelCaller) CallStream(ctx context.Context, messages []Message, options *CallOptions) (<-chan StreamChunk, error)
```

#### 5.5.2 并发限流（Redis）
```go
type ConcurrencyLimiter struct {
    redis      *redis.Client
    maxConcurrent int
}

// 获取并发槽位
func (cl *ConcurrencyLimiter) Acquire(ctx context.Context, key string) error {
    for {
        count, err := cl.redis.Incr(ctx, key).Result()
        if err != nil {
            return err
        }

        if count <= int64(cl.maxConcurrent) {
            // 首次设置过期时间
            if count == 1 {
                cl.redis.Expire(ctx, key, time.Hour)
            }
            return nil
        }

        // 超过限制，释放并等待
        cl.redis.Decr(ctx, key)
        time.Sleep(100 * time.Millisecond)
    }
}

// 释放并发槽位
func (cl *ConcurrencyLimiter) Release(ctx context.Context, key string) {
    cl.redis.Decr(ctx, key)
}
```

---

## 6. 技术选型

### 6.1 Web 框架
**Gin** - 高性能 HTTP Web 框架
- 快速路由（基于 Radix Tree）
- 中间件支持
- JSON 验证和解析
- 路由分组

### 6.2 ORM
**GORM** - Go 最流行的 ORM 库
- 功能强大
- 自动迁移
- 关联支持
- 钩子函数

### 6.3 Redis 客户端
**go-redis/redis/v8** - Redis 客户端
- 支持 Redis Cluster
- Pipeline 支持
- 连接池
- Context 支持

### 6.4 JWT
**golang-jwt/jwt/v5** - JWT 实现
- 签名和验证
- Claims 自定义
- 多算法支持

### 6.5 密码哈希
**golang.org/x/crypto/bcrypt** - 密码哈希
- 安全可靠
- 自动加盐
- 成本因子可调

### 6.6 配置管理
**Viper** - 配置管理
- 支持多种格式（YAML/JSON/TOML）
- 环境变量支持
- 热重载

### 6.7 日志
**logrus** 或 **zap**
- 结构化日志
- 日志级别
- 日志轮转

### 6.8 数据验证
**go-playground/validator**
- 结构体验证
- 自定义验证规则
- 错误消息国际化

### 6.9 HTTP 客户端
**标准库 net/http** + **fasthttp**（可选）
- 模型 API 调用

---

## 7. 配置管理

### 7.1 配置结构
```go
type Config struct {
    Server   ServerConfig   `mapstructure:"server"`
    Database DatabaseConfig `mapstructure:"database"`
    Redis    RedisConfig    `mapstructure:"redis"`
    JWT      JWTConfig      `mapstructure:"jwt"`
    Admin    AdminConfig    `mapstructure:"admin"`
    CORS     CORSConfig     `mapstructure:"cors"`
}

type ServerConfig struct {
    Host           string `mapstructure:"host"`
    Port           int    `mapstructure:"port"`
    ProductionMode bool   `mapstructure:"production_mode"`
}

type DatabaseConfig struct {
    Path string `mapstructure:"path"`
}

type RedisConfig struct {
    Host            string `mapstructure:"host"`
    Port            int    `mapstructure:"port"`
    DB              int    `mapstructure:"db"`
    Password        string `mapstructure:"password"`
    MaxWaitTime     int    `mapstructure:"max_wait_time"`
    DefaultMaxConcurrency int `mapstructure:"default_max_concurrency"`
}

type JWTConfig struct {
    SecretKey     string `mapstructure:"secret_key"`
    Algorithm     string `mapstructure:"algorithm"`
    ExpireMinutes int    `mapstructure:"expire_minutes"`
}
```

### 7.2 配置文件 (config.yaml)
```yaml
server:
  host: "0.0.0.0"
  port: 8080
  production_mode: false

database:
  path: "./database/app.db"

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  max_wait_time: 300
  default_max_concurrency: 16

jwt:
  secret_key: "your-secret-key-here"
  algorithm: "HS256"
  expire_minutes: 43200

admin:
  username: "admin"
  # bcrypt hash of "admin123"
  password: "$2a$12$..."

cors:
  origins:
    - "http://localhost:3000"
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"
```

---

## 8. 中间件实现

### 8.1 CORS 中间件
```go
func CORSMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        c.Header("Access-Control-Allow-Origin", "*")
        c.Header("Access-Control-Allow-Credentials", "true")
        c.Header("Access-Control-Allow-Headers", "*")
        c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

        if c.Request.Method == "OPTIONS" {
            c.AbortWithStatus(204)
            return
        }

        c.Next()
    }
}
```

### 8.2 JWT 认证中间件
```go
func AuthMiddleware(jwtService *JWTService) gin.HandlerFunc {
    return func(c *gin.Context) {
        // 获取 Token
        token := c.GetHeader("Authorization")
        if token == "" {
            c.JSON(401, gin.H{"code": 401, "message": "未认证"})
            c.Abort()
            return
        }

        // 验证 Token
        claims, err := jwtService.ValidateToken(token)
        if err != nil {
            c.JSON(401, gin.H{"code": 401, "message": "Token 无效"})
            c.Abort()
            return
        }

        // 设置用户信息到上下文
        c.Set("user_id", claims.UserID)
        c.Set("username", claims.Username)
        c.Set("is_admin", claims.IsAdmin)

        c.Next()
    }
}
```

### 8.3 管理员权限中间件
```go
func AdminMiddleware() gin.HandlerFunc {
    return func(c *gin.Context) {
        isAdmin, exists := c.Get("is_admin")
        if !exists || !isAdmin.(bool) {
            c.JSON(403, gin.H{"code": 403, "message": "需要管理员权限"})
            c.Abort()
            return
        }
        c.Next()
    }
}
```

### 8.4 日志中间件
```go
func LoggerMiddleware(logger *logrus.Logger) gin.HandlerFunc {
    return func(c *gin.Context) {
        start := time.Now()

        c.Next()

        duration := time.Since(start)
        logger.WithFields(logrus.Fields{
            "method":     c.Request.Method,
            "path":       c.Request.URL.Path,
            "status":     c.Writer.Status(),
            "duration":   duration,
            "ip":         c.ClientIP(),
            "user_id":    c.GetString("user_id"),
        }).Info("HTTP Request")
    }
}
```

---

## 9. 错误处理

### 9.1 错误码定义
```go
const (
    CodeSuccess      = 200
    CodeBadRequest   = 400
    CodeUnauthorized = 401
    CodeForbidden    = 403
    CodeNotFound     = 404
    CodeInternalError = 500

    // 业务错误码
    CodeUserExists     = 1001
    CodeUserNotFound   = 1002
    CodePasswordWrong  = 1003
    CodeTaskNotFound   = 2001
    CodeFileNotFound   = 3001
)
```

### 9.2 错误响应
```go
type ErrorResponse struct {
    Code    int    `json:"code"`
    Message string `json:"message"`
    Detail  string `json:"detail,omitempty"`
}

func RespondError(c *gin.Context, code int, message string, detail string) {
    c.JSON(code, ErrorResponse{
        Code:    code,
        Message: message,
        Detail:  detail,
    })
}
```

---

## 10. 实施步骤

### 阶段一：基础框架搭建（1-2周）
1. **项目初始化**
   - 创建项目目录结构
   - 初始化 Go Module
   - 安装依赖包

2. **配置管理**
   - 实现 Config 结构和加载器
   - 配置 Viper
   - 环境变量支持

3. **数据库初始化**
   - 定义 GORM 模型
   - 实现数据库连接
   - 自动迁移
   - Repository 层实现

### 阶段二：认证系统（1周）
1. **JWT 实现**
   - Token 生成和验证
   - 中间件实现
   - 密码哈希

2. **用户管理**
   - 注册/登录接口
   - 用户信息获取
   - 管理员初始化

### 阶段三：核心业务功能（3-4周）
1. **数据文件管理**
   - 文件上传/下载
   - 文件列表/详情
   - 文件内容编辑

2. **模型管理**
   - 模型配置 CRUD
   - 模型调用客户端
   - 并发限流

3. **任务管理**
   - 任务创建/启动
   - 任务状态跟踪
   - SSE 实时进度推送
   - 任务停止/删除

4. **数据生成**
   - Pipeline 分布式生成器
   - 样本处理
   - 数据保存到数据库
   - Redis 进度同步

### 阶段四：辅助功能（1-2周）
1. **文件格式转换**
   - CSV/JSONL 互转
   - 批量转换

2. **生成数据管理**
   - 数据列表/查询
   - 数据编辑
   - 数据确认
   - 数据导出

3. **报告功能**
   - 报告生成
   - 报告下载

### 阶段五：管理员功能（1周）
1. **用户管理**
   - 用户列表
   - 删除用户
   - 用户数据查询

2. **全局任务管理**
   - 所有任务查询
   - 任务删除

### 阶段六：测试和优化（1-2周）
1. **单元测试**
   - Repository 层测试
   - Service 层测试
   - Handler 层测试

2. **集成测试**
   - API 测试
   - 端到端测试

3. **性能优化**
   - 数据库查询优化
   - 并发优化
   - 内存优化

4. **安全检查**
   - SQL 注入防护
   - XSS 防护
   - CSRF 防护
   - 权限验证

### 阶段七：部署（3-5天）
1. **构建和打包**
   - 编译二进制文件
   - Docker 镜像构建（可选）

2. **部署脚本**
   - 数据库迁移脚本
   - 配置文件模板
   - 启动/停止脚本

3. **文档**
   - API 文档
   - 部署文档
   - 运维文档

---

## 11. 测试计划

### 11.1 单元测试
- Repository 层：测试数据库 CRUD 操作
- Service 层：测试业务逻辑
- Utils：测试工具函数

**测试覆盖率目标**: ≥ 70%

### 11.2 集成测试
- API 接口测试
- 数据库集成测试
- Redis 集成测试

### 11.3 性能测试
- 并发请求测试
- 大文件上传/下载测试
- 任务生成性能测试
- 内存泄漏测试

### 11.4 压力测试
- 模拟多用户并发
- 任务并发执行
- 模型调用并发限流

---

## 12. 部署方案

### 12.1 开发环境
```bash
# 启动后端
go run cmd/server/main.go

# 或使用 air 热重载
air
```

### 12.2 生产环境

#### 方案一：直接部署
```bash
# 编译
go build -o gen-api cmd/server/main.go

# 运行
./gen-api
```

#### 方案二：Docker 部署
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o gen-api cmd/server/main.go

FROM alpine:latest
RUN apk add --no-cache ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/gen-api .
COPY config.yaml .
EXPOSE 8080
CMD ["./gen-api"]
```

#### 方案三：Systemd 服务
```ini
[Unit]
Description=Gen API Service
After=network.target

[Service]
Type=simple
User=gen
WorkingDirectory=/opt/gen-api
ExecStart=/opt/gen-api/gen-api
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 12.3 Nginx 反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 支持
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }

    location / {
        root /var/www/frontend;
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 13. 迁移数据方案

### 13.1 数据库迁移
由于使用相同的 SQLite 数据库和表结构，迁移时：
1. 备份现有数据库
2. Go 应用直接读取现有数据库
3. 无需数据导入/导出

### 13.2 Redis 数据迁移
Redis 中存储的任务进度数据是临时的，迁移时可以清空：
```bash
redis-cli FLUSHDB
```

---

## 14. 风险和挑战

### 14.1 技术风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Python asyncio → Go goroutine 转换 | 中 | 仔细理解并发模型差异，使用 channel 和 sync 包 |
| SQLAlchemy → GORM 差异 | 低 | 充分利用 GORM 文档，测试关联查询 |
| SSE 实现差异 | 低 | 使用 Gin 的流式响应 |
| Redis 库差异 | 低 | 参考官方文档 |

### 14.2 业务风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 任务进度同步问题 | 高 | 充分测试 Redis 进度更新逻辑 |
| 并发控制问题 | 高 | 使用 Redis 分布式锁，充分测试 |
| 文件处理性能 | 中 | 使用流式处理，避免大文件OOM |
| 数据库锁问题 | 中 | SQLite 限制，考虑事务优化 |

### 14.3 时间风险
- **预估时间**: 8-10周
- **缓冲时间**: +2周
- **总计**: 10-12周

---

## 15. 验收标准

### 15.1 功能验收
- ✅ 所有 API 接口正常工作
- ✅ 用户认证和授权正确
- ✅ 任务创建、执行、停止、删除正常
- ✅ 实时进度推送正常
- ✅ 文件上传下载正常
- ✅ 数据生成功能正常
- ✅ 管理员功能正常

### 15.2 性能验收
- ✅ API 响应时间 < 100ms (P95)
- ✅ 并发 100 用户无明显性能下降
- ✅ 内存占用稳定（无泄漏）
- ✅ 任务生成速度不低于 Python 版本

### 15.3 兼容性验收
- ✅ 前端无需修改即可对接
- ✅ 数据库与 Python 版本兼容
- ✅ API 接口完全兼容

### 15.4 安全验收
- ✅ 所有接口有正确的权限验证
- ✅ 密码正确哈希存储
- ✅ JWT Token 安全
- ✅ 无 SQL 注入、XSS 等漏洞

---

## 16. 后续优化

### 16.1 性能优化
- 数据库连接池
- Redis 连接池优化
- HTTP 客户端连接池
- 数据库索引优化

### 16.2 功能扩展
- 任务队列（使用消息队列）
- 任务调度（定时任务）
- 更多文件格式支持
- 更多模型格式支持

### 16.3 运维优化
- 健康检查接口
- 指标监控（Prometheus）
- 日志聚合（ELK）
- 链路追踪（Jaeger）

---

## 17. 参考资料

### 17.1 官方文档
- [Gin](https://gin-gonic.com/docs/)
- [GORM](https://gorm.io/docs/)
- [go-redis](https://redis.uptrace.dev/)
- [golang-jwt](https://github.com/golang-jwt/jwt)

### 17.2 最佳实践
- [Go Project Layout](https://github.com/golang-standards/project-layout)
- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)

---

## 附录

### A. 依赖包清单
```go
require (
    github.com/gin-gonic/gin v1.9.1
    github.com/go-redis/redis/v8 v8.11.5
    gorm.io/gorm v1.25.5
    gorm.io/driver/sqlite v1.5.4
    github.com/golang-jwt/jwt/v5 v5.2.0
    golang.org/x/crypto v0.17.0
    github.com/spf13/viper v1.18.2
    github.com/sirupsen/logrus v1.9.3
    github.com/go-playground/validator/v10 v10.16.0
)
```

### B. Git 提交规范
```
feat: 新功能
fix: 修复 bug
docs: 文档变更
style: 代码格式调整
refactor: 重构
test: 测试
chore: 构建/工具变更
```

### C. 代码审查清单
- [ ] 代码符合 Go 规范
- [ ] 有必要的注释
- [ ] 错误处理完善
- [ ] 无明显的性能问题
- [ ] 安全问题检查
- [ ] 测试覆盖足够

---

**文档版本**: v1.0
**创建日期**: 2025-01-28
**最后更新**: 2025-01-28
**文档状态**: 待评审
