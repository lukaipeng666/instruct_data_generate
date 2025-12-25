# 前端项目说明

这是一个使用主流前端技术栈构建的现代化前端应用：

- **React 18** - 用户界面库
- **TypeScript** - 类型安全
- **Vite** - 快速构建工具
- **Tailwind CSS** - 实用优先的CSS框架
- **React Router** - 路由管理
- **Axios** - HTTP客户端
- **Zustand** - 轻量级状态管理

## 安装依赖

```bash
cd frontend
npm install
```

## 开发模式

```bash
npm run dev
```

前端将在 `http://localhost:3000` 运行，并自动代理API请求到后端 `http://localhost:5000`

## 构建生产版本

```bash
npm run build
```

构建产物将输出到 `../static` 目录，供FastAPI后端服务。

## 项目结构

```
frontend/
├── src/
│   ├── components/     # 可复用组件
│   ├── pages/          # 页面组件
│   ├── services/       # API服务
│   ├── store/          # 状态管理
│   ├── types/          # TypeScript类型定义
│   ├── utils/          # 工具函数
│   ├── App.tsx         # 主应用组件
│   └── main.tsx        # 入口文件
├── public/             # 静态资源
└── package.json        # 依赖配置
```

