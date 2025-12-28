# API接口完整清单

## 已实现接口 ✅

### 认证接口 (4/4)
- ✅ POST /api/register - 用户注册
- ✅ POST /api/login - 用户登录
- ✅ GET /api/me - 获取当前用户信息
- ✅ POST /api/logout - 用户登出

### 任务管理接口 (8/14)
- ✅ POST /api/start - 启动任务
- ✅ GET /api/progress/:task_id - SSE获取任务进度
- ✅ POST /api/stop/:task_id - 停止任务
- ✅ DELETE /api/task/:task_id - 删除任务
- ✅ GET /api/status/:task_id - 获取任务状态
- ✅ GET /api/active_task - 获取运行中的任务
- ✅ GET /api/tasks - 获取任务列表
- ⚠️ GET /api/task_progress/:task_id - 从Redis获取任务进度 (需补充)
- ⚠️ GET /api/progress_unified/:task_id - 统一获取任务进度 (需补充)
- ❌ GET /api/task_types - 获取任务类型列表 (缺失)

## 需要实现的接口 ❌

### 数据文件管理接口 (0/13)
- ❌ GET /api/data_files - 获取文件列表
- ❌ POST /api/data_files/upload - 上传文件
- ❌ GET /api/data_files/:file_id - 获取文件详情
- ❌ DELETE /api/data_files/:file_id - 删除文件
- ❌ POST /api/data_files/batch_delete - 批量删除文件
- ❌ GET /api/data_files/:file_id/download - 下载文件
- ❌ GET /api/data_files/:file_id/download_csv - 下载CSV格式
- ❌ GET /api/data_files/:file_id/content - 查看文件内容
- ❌ GET /api/data_files/:file_id/content/editable - 查看可编辑内容
- ❌ PUT /api/data_files/:file_id/content/:item_index - 更新单条数据
- ❌ POST /api/data_files/:file_id/content - 添加新数据
- ❌ DELETE /api/data_files/:file_id/content/batch - 批量删除数据
- ❌ POST /api/data_files/batch_download - 批量下载文件

### 文件转换接口 (0/2)
- ❌ POST /api/data_files/batch_convert - 批量转换格式
- ❌ POST /api/convert_files - 上传并转换

### 生成数据接口 (0/11)
- ❌ GET /api/generated_data - 获取生成数据列表
- ❌ POST /api/generated_data/batch_update - 批量更新数据
- ❌ POST /api/generated_data/batch_confirm - 批量确认数据
- ❌ GET /api/generated_data/export - 导出数据
- ❌ GET /api/generated_data/:task_id/download - 下载任务数据
- ❌ GET /api/generated_data/:task_id/info - 获取任务数据信息
- ❌ GET /api/generated_data/:task_id/download_csv - 下载CSV格式
- ❌ PUT /api/generated_data/:data_id - 更新单条数据
- ❌ POST /api/generated_data/:data_id/confirm - 确认单条数据
- ❌ POST /api/generated_data/:task_id - 向任务添加数据
- ❌ DELETE /api/generated_data/batch - 批量删除数据

### 报告接口 (0/5)
- ❌ GET /api/reports - 获取报告列表
- ❌ GET /api/reports/:task_id/data - 获取任务报告数据
- ❌ GET /api/reports/:task_id/data/editable - 获取可编辑报告
- ❌ DELETE /api/reports/:task_id - 删除报告
- ❌ POST /api/reports/batch_delete - 批量删除报告

### 模型接口 (0/2)
- ❌ GET /api/models - 获取激活的模型列表
- ❌ POST /api/model-call - 模型调用代理(带限流)

### 管理员接口 (0/9)
- ❌ GET /api/admin/users - 获取所有用户
- ❌ DELETE /api/admin/users/:id - 删除用户
- ❌ GET /api/admin/users/:id/reports - 获取用户报告
- ❌ GET /api/admin/users/:id/reports/:task_id/download - 下载用户报告
- ❌ GET /api/admin/models - 获取所有模型配置
- ❌ POST /api/admin/models - 创建模型配置
- ❌ PUT /api/admin/models/:id - 更新模型配置
- ❌ DELETE /api/admin/models/:id - 删除模型配置
- ❌ GET /api/admin/tasks - 获取所有任务
- ❌ DELETE /api/admin/tasks/:id - 删除任务记录

## 统计

- 总接口数: 61
- 已实现: 12 (19.7%)
- 需要实现: 49 (80.3%)
