package service

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"time"

	"gen-go/internal/config"
	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"

	"github.com/go-redis/redis/v8"
)

// TaskManager 任务管理器
type TaskManager struct {
	taskRepo    *repository.TaskRepository
	userRepo    *repository.UserRepository
	fileRepo    *repository.DataFileRepository
	modelRepo   *repository.ModelConfigRepository
	redisClient *redis.Client
	cfg         *config.Config

	// 内存中的任务状态
	tasks     map[string]*TaskContext
	tasksLock sync.RWMutex
}

// TaskContext 任务上下文
type TaskContext struct {
	TaskID       string
	UserID       uint
	Status       string
	Params       map[string]interface{}
	FileID       uint
	ModelConfig  *models.ModelConfig
	ModelPath    string
	APIServices  []string
	StartTime    time.Time
	EndTime      *time.Time
	ReturnCode   *int
	CancelFunc   context.CancelFunc
	Progress     chan *dto.ProgressEvent
	Finished     bool

	// 用于广播的事件历史和订阅者管理
	EventHistory     []*dto.ProgressEvent
	EventHistoryLock sync.RWMutex
	subscribers      map[chan *dto.ProgressEvent]bool
	subscribersLock  sync.RWMutex
}

// AddEvent 添加事件到历史并广播给所有订阅者
func (tc *TaskContext) AddEvent(event *dto.ProgressEvent) {
	// 添加到历史
	tc.EventHistoryLock.Lock()
	tc.EventHistory = append(tc.EventHistory, event)
	tc.EventHistoryLock.Unlock()

	// 广播给所有订阅者
	tc.subscribersLock.RLock()
	for ch := range tc.subscribers {
		select {
		case ch <- event:
		default:
			// 通道满了，跳过（避免阻塞）
		}
	}
	tc.subscribersLock.RUnlock()
}

// Subscribe 订阅事件（返回一个接收事件的通道）
func (tc *TaskContext) Subscribe() chan *dto.ProgressEvent {
	ch := make(chan *dto.ProgressEvent, 200)

	tc.subscribersLock.Lock()
	if tc.subscribers == nil {
		tc.subscribers = make(map[chan *dto.ProgressEvent]bool)
	}
	tc.subscribers[ch] = true
	tc.subscribersLock.Unlock()

	return ch
}

// Unsubscribe 取消订阅
func (tc *TaskContext) Unsubscribe(ch chan *dto.ProgressEvent) {
	tc.subscribersLock.Lock()
	delete(tc.subscribers, ch)
	tc.subscribersLock.Unlock()
	// 注意：不关闭通道，因为可能有竞态条件
	// SSE handler 通过 context.Done() 来检测断开连接
}

// GetEventHistory 获取事件历史的副本
func (tc *TaskContext) GetEventHistory() []*dto.ProgressEvent {
	tc.EventHistoryLock.RLock()
	defer tc.EventHistoryLock.RUnlock()

	history := make([]*dto.ProgressEvent, len(tc.EventHistory))
	copy(history, tc.EventHistory)
	return history
}

// NewTaskManager 创建任务管理器
func NewTaskManager(
	taskRepo *repository.TaskRepository,
	userRepo *repository.UserRepository,
	fileRepo *repository.DataFileRepository,
	modelRepo *repository.ModelConfigRepository,
	redisClient *redis.Client,
	cfg *config.Config,
) *TaskManager {
	return &TaskManager{
		taskRepo:    taskRepo,
		userRepo:    userRepo,
		fileRepo:    fileRepo,
		modelRepo:   modelRepo,
		redisClient: redisClient,
		cfg:         cfg,
		tasks:       make(map[string]*TaskContext),
	}
}

// StartTask 启动任务
func (tm *TaskManager) StartTask(userID uint, req *dto.StartTaskRequest) (*dto.StartTaskResponse, error) {
	log.Printf("[StartTask] 用户 %d 请求启动任务", userID)
	log.Printf("[StartTask] InputFile: %s", req.InputFile)
	log.Printf("[StartTask] ModelID: %v, TaskType: %s", req.ModelID, req.TaskType)
	log.Printf("[StartTask] BatchSize: %d, MaxConcurrent: %d", req.BatchSize, req.MaxConcurrent)

	// 获取模型配置
	var modelConfig *models.ModelConfig
	var modelPath string
	var apiServices []string

	if req.ModelID != nil {
		// 从数据库获取模型配置
		model, err := tm.modelRepo.GetByIDAndActive(*req.ModelID)
		if err != nil {
			log.Printf("[StartTask] 错误: 获取模型配置失败: %v", err)
			return nil, fmt.Errorf("获取模型配置失败: %w", err)
		}
		modelConfig = model
		modelPath = model.ModelPath
		apiServices = []string{model.APIURL}
		log.Printf("[StartTask] 使用数据库模型配置: %s, API: %s", model.Name, model.APIURL)
	} else if req.Services != nil && len(req.Services) > 0 {
		// 使用前端提供的服务地址列表
		apiServices = req.Services
		modelPath = req.Model
		log.Printf("[StartTask] 使用前端提供的服务地址: %v", apiServices)
	} else {
		// 使用配置文件中的默认服务地址
		apiServices = tm.cfg.GetModelServices()
		modelPath = req.Model
		log.Printf("[StartTask] 使用配置文件中的默认服务地址")
	}

	// 解析input_file: db://file_id/filename
	if len(req.InputFile) < 5 || req.InputFile[:5] != "db://" {
		log.Printf("[StartTask] 错误: 无效的输入文件格式: %s", req.InputFile)
		return nil, fmt.Errorf("无效的输入文件格式")
	}

	var fileID uint
	_, err := fmt.Sscanf(req.InputFile, "db://%d", &fileID)
	if err != nil {
		log.Printf("[StartTask] 错误: 解析文件ID失败: %v", err)
		return nil, fmt.Errorf("解析文件ID失败: %w", err)
	}

	log.Printf("[StartTask] 解析到文件ID: %d", fileID)

	// 验证文件是否存在
	file, err := tm.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		log.Printf("[StartTask] 错误: 文件不存在或无权访问: %v", err)
		return nil, fmt.Errorf("文件不存在或无权访问")
	}

	log.Printf("[StartTask] 文件验证成功: %s (大小: %d bytes)", file.Filename, file.FileSize)

	// 生成任务ID
	taskIDBase := file.Filename
	if len(taskIDBase) > 50 {
		taskIDBase = taskIDBase[:50]
	}
	taskID := tm.generateUniqueTaskID(taskIDBase)

	log.Printf("[StartTask] 生成任务ID: %s", taskID)

	// 准备参数
	params := map[string]interface{}{
		"file_id":             fileID,
		"user_id":             userID,
		"task_type":           req.TaskType,
		"batch_size":          req.BatchSize,
		"max_concurrent":      req.MaxConcurrent,
		"min_score":           req.MinScore,
		"variants_per_sample": req.VariantsPerSample,
		"data_rounds":         req.DataRounds,
		"retry_times":         req.RetryTimes,
		"special_prompt":      req.SpecialPrompt,
		"directions":          req.Directions,
		"model_id":            req.ModelID,
		"model_path":          modelPath,
		"api_services":        apiServices,
	}

	// 如果有模型配置，添加更多参数
	if modelConfig != nil {
		params["api_key"] = modelConfig.APIKey
		params["is_vllm"] = modelConfig.IsVLLM
		params["temperature"] = modelConfig.Temperature
		params["top_p"] = modelConfig.TopP
		params["max_tokens"] = modelConfig.MaxTokens
		params["timeout"] = modelConfig.Timeout
	}

	// 创建数据库任务记录
	task := &models.Task{
		TaskID:       taskID,
		UserID:       userID,
		Status:       "running",
		Params:       params,
		StartedAt:    time.Now(),
	}

	if err := tm.taskRepo.Create(task); err != nil {
		log.Printf("[StartTask] 错误: 创建任务记录失败: %v", err)
		return nil, fmt.Errorf("创建任务记录失败: %w", err)
	}

	log.Printf("[StartTask] 数据库任务记录创建成功")

	// 创建内存任务上下文
	ctx, cancel := context.WithCancel(context.Background())
	taskCtx := &TaskContext{
		TaskID:      taskID,
		UserID:      userID,
		Status:      "running",
		Params:      params,
		FileID:      fileID,
		ModelConfig: modelConfig,
		ModelPath:   modelPath,
		APIServices: apiServices,
		StartTime:   time.Now(),
		CancelFunc:  cancel,
		Progress:    make(chan *dto.ProgressEvent, 100),
		Finished:    false,
	}

	tm.tasksLock.Lock()
	tm.tasks[taskID] = taskCtx
	tm.tasksLock.Unlock()

	log.Printf("[StartTask] 任务上下文创建成功，准备启动后台执行")

	// 在后台goroutine中执行任务
	go tm.runTask(ctx, taskCtx)

	return &dto.StartTaskResponse{
		Success: true,
		TaskID:  taskID,
		Status:  "running",
	}, nil
}

// runTask 执行任务(真实实现)
func (tm *TaskManager) runTask(ctx context.Context, taskCtx *TaskContext) {
	defer close(taskCtx.Progress)

	log.Printf("[runTask] 任务 %s 开始执行", taskCtx.TaskID)

	// 发送开始事件
	taskCtx.AddEvent(&dto.ProgressEvent{
		Type:    "output",
		Line:    "任务开始执行...",
		Message: "任务开始执行",
	})

	// 使用任务上下文中的服务地址
	services := taskCtx.APIServices
	log.Printf("[runTask] 使用 %d 个模型服务地址", len(services))
	for i, svc := range services {
		log.Printf("[runTask]   服务 %d: %s", i+1, svc)
	}

	if len(services) == 0 {
		log.Printf("[runTask] 错误: 未找到可用的模型服务")
		taskCtx.Error("未找到可用的模型服务")
		return
	}

	// 模型限流：使用模型路径作为key
	modelLimiterKey := fmt.Sprintf("model_limit:%s", taskCtx.ModelPath)
	maxConcurrent := 5 // 默认并发数
	if taskCtx.ModelConfig != nil {
		maxConcurrent = taskCtx.ModelConfig.MaxConcurrent
	} else if maxConcurrent <= 0 {
		maxConcurrent = 5
	}

	log.Printf("[runTask] 模型限流: %s, 最大并发: %d", modelLimiterKey, maxConcurrent)

	// 从 Redis 获取令牌
	acquired, err := tm.acquireModelToken(ctx, modelLimiterKey, maxConcurrent)
	if err != nil {
		log.Printf("[runTask] 错误: 获取模型令牌失败: %v", err)
		taskCtx.Error(fmt.Sprintf("获取模型令牌失败: %v", err))
		return
	}
	if !acquired {
		log.Printf("[runTask] 错误: 模型服务繁忙，未获取到令牌")
		taskCtx.Error("模型服务繁忙，请稍后重试")
		return
	}

	log.Printf("[runTask] 成功获取模型令牌")
	defer tm.releaseModelToken(ctx, modelLimiterKey)

	// 构建Python命令
	args := tm.buildPythonArgs(taskCtx, services)

	log.Printf("[runTask] Python命令: python3 %v", args)

	// 启动Python进程
	cmd := exec.CommandContext(ctx, "python3", args...)

	// 设置环境变量，禁用Python输出缓冲
	cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1")

	// 设置工作目录为项目根目录
	cmd.Dir = tm.cfg.ProjectRoot
	log.Printf("[runTask] 工作目录: %s", cmd.Dir)

	// 获取标准输出和错误输出管道
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		log.Printf("[runTask] 错误: 创建输出管道失败: %v", err)
		taskCtx.Error(fmt.Sprintf("创建输出管道失败: %v", err))
		return
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		log.Printf("[runTask] 错误: 创建错误管道失败: %v", err)
		taskCtx.Error(fmt.Sprintf("创建错误管道失败: %v", err))
		return
	}

	// 启动进程
	log.Printf("[runTask] 准备启动Python进程...")
	if err := cmd.Start(); err != nil {
		log.Printf("[runTask] 错误: 启动Python进程失败: %v", err)
		taskCtx.Error(fmt.Sprintf("启动Python进程失败: %v", err))
		return
	}

	log.Printf("[runTask] Python进程已启动，PID: %d", cmd.Process.Pid)

	// 读取输出
	done := make(chan error, 2)

	// 读取标准输出
	go func() {
		log.Printf("[runTask] 开始读取标准输出...")
		scanner := bufio.NewScanner(stdout)
		lineCount := 0
		for scanner.Scan() {
			line := scanner.Text()
			lineCount++
			log.Printf("[Python STDOUT] %s", line)
			tm.handlePythonOutput(taskCtx, line)
		}
		log.Printf("[runTask] 标准输出读取完成，共 %d 行", lineCount)
		done <- scanner.Err()
	}()

	// 读取错误输出
	go func() {
		log.Printf("[runTask] 开始读取错误输出...")
		scanner := bufio.NewScanner(stderr)
		lineCount := 0
		for scanner.Scan() {
			line := scanner.Text()
			lineCount++
			log.Printf("[Python STDERR] %s", line)
			taskCtx.AddEvent(&dto.ProgressEvent{
				Type:    "error",
				Line:    line,
				Message: "错误",
			})
		}
		log.Printf("[runTask] 错误输出读取完成，共 %d 行", lineCount)
		done <- scanner.Err()
	}()

	// 等待进程完成
	log.Printf("[runTask] 等待Python进程完成...")
	err = cmd.Wait()

	// 等待所有goroutine完成
	for i := 0; i < 2; i++ {
		<-done
	}

	log.Printf("[runTask] Python进程已结束，错误: %v", err)

	// 标记任务完成
	code := 0
	if err != nil {
		code = 1
		log.Printf("[runTask] 任务执行失败")
		taskCtx.AddEvent(&dto.ProgressEvent{
			Type:    "error",
			Line:    fmt.Sprintf("任务执行失败: %v", err),
			Message: "错误",
		})
	}

	taskCtx.Finished = true
	taskCtx.ReturnCode = &code
	now := time.Now()
	taskCtx.EndTime = &now

	// 更新数据库
	status := "finished"
	if err != nil {
		status = "error"
	}

	log.Printf("[runTask] 更新任务状态为: %s", status)
	tm.taskRepo.UpdateStatusWithTime(taskCtx.TaskID, status)

	// 发送完成事件
	taskCtx.AddEvent(&dto.ProgressEvent{
		Type:       "finished",
		ReturnCode: &code,
	})

	log.Printf("[runTask] 任务 %s 执行完成，退出码: %d", taskCtx.TaskID, code)
}

// getModelServices 获取模型服务地址列表
func (tm *TaskManager) getModelServices(modelName string) []string {
	// 从配置获取模型服务地址
	return tm.cfg.GetModelServices()
}

// acquireModelToken 获取模型限流令牌
func (tm *TaskManager) acquireModelToken(ctx context.Context, key string, maxConcurrent int) (bool, error) {
	if tm.redisClient == nil {
		// 如果没有Redis，直接允许
		return true, nil
	}

	// 使用Redis实现简单的计数器限流
	current, err := tm.redisClient.Incr(ctx, key).Result()
	if err != nil {
		return false, err
	}

	if current == 1 {
		// 设置过期时间（1小时）
		tm.redisClient.Expire(ctx, key, time.Hour)
	}

	if current > int64(maxConcurrent) {
		// 超过限制，释放令牌
		tm.redisClient.Decr(ctx, key)
		return false, nil
	}

	return true, nil
}

// releaseModelToken 释放模型限流令牌
func (tm *TaskManager) releaseModelToken(ctx context.Context, key string) {
	if tm.redisClient == nil {
		return
	}
	tm.redisClient.Decr(ctx, key)
}

// buildPythonArgs 构建Python命令参数
func (tm *TaskManager) buildPythonArgs(taskCtx *TaskContext, services []string) []string {
	// 从taskCtx.Params中获取参数（处理int和float64两种类型）
	getIntParam := func(key string, defaultVal int) int {
		if val, ok := taskCtx.Params[key]; ok {
			switch v := val.(type) {
			case int:
				return v
			case float64:
				return int(v)
			}
		}
		return defaultVal
	}

	getStringParam := func(key string, defaultVal string) string {
		if val, ok := taskCtx.Params[key]; ok {
			if s, ok := val.(string); ok {
				return s
			}
		}
		return defaultVal
	}

	batchSize := getIntParam("batch_size", 16)
	maxConcurrent := getIntParam("max_concurrent", 16)
	minScore := getIntParam("min_score", 10)
	taskType := getStringParam("task_type", "general")
	variantsPerSample := getIntParam("variants_per_sample", 3)
	dataRounds := getIntParam("data_rounds", 10)
	retryTimes := getIntParam("retry_times", 3)
	specialPrompt := getStringParam("special_prompt", "")
	directions := getStringParam("directions", "")

	args := []string{
		"main.py",
		"--file-id", strconv.FormatUint(uint64(taskCtx.FileID), 10),
		"--user-id", strconv.FormatUint(uint64(taskCtx.UserID), 10),
		"--task-id", taskCtx.TaskID,
		"--model", taskCtx.ModelPath,
		"--batch-size", strconv.Itoa(batchSize),
		"--max-concurrent", strconv.Itoa(maxConcurrent),
		"--min-score", strconv.Itoa(minScore),
		"--task-type", taskType,
		"--variants-per-sample", strconv.Itoa(variantsPerSample),
		"--data-rounds", strconv.Itoa(dataRounds),
		"--retry-times", strconv.Itoa(retryTimes),
	}

	// 添加服务地址
	for _, svc := range services {
		args = append(args, "--services", svc)
	}

	// 如果有模型配置，添加API相关参数
	if taskCtx.ModelConfig != nil {
		if taskCtx.ModelConfig.APIKey != "" && taskCtx.ModelConfig.APIKey != "sk-xxxxx" {
			args = append(args, "--api-key", taskCtx.ModelConfig.APIKey)
		}
		if taskCtx.ModelConfig.IsVLLM {
			args = append(args, "--is-vllm")
		}
		args = append(args, "--top-p", fmt.Sprintf("%.1f", taskCtx.ModelConfig.TopP))
		args = append(args, "--max-tokens", strconv.Itoa(taskCtx.ModelConfig.MaxTokens))
		args = append(args, "--timeout", strconv.Itoa(taskCtx.ModelConfig.Timeout))
	}

	// 可选参数
	if specialPrompt != "" {
		args = append(args, "--special-prompt", specialPrompt)
	}

	if directions != "" {
		// Directions 是一个字符串，需要传递给 Python
		args = append(args, "--directions", directions)
	}

	return args
}

// handlePythonOutput 处理Python输出并转换为进度事件
func (tm *TaskManager) handlePythonOutput(taskCtx *TaskContext, line string) {
	// 尝试解析JSON格式的输出
	var output map[string]interface{}
	if err := json.Unmarshal([]byte(line), &output); err == nil {
		// JSON格式输出
		if progress, ok := output["progress"].(map[string]interface{}); ok {
			taskCtx.AddEvent(&dto.ProgressEvent{
				Type:    "progress",
				Message: fmt.Sprintf("进度: %v", progress),
			})
		} else if result, ok := output["result"].(map[string]interface{}); ok {
			taskCtx.AddEvent(&dto.ProgressEvent{
				Type:    "result",
				Message: fmt.Sprintf("生成结果: %v", result),
			})
		} else {
			taskCtx.AddEvent(&dto.ProgressEvent{
				Type:    "output",
				Line:    line,
				Message: "输出",
			})
		}
	} else {
		// 普通文本输出
		taskCtx.AddEvent(&dto.ProgressEvent{
			Type:    "output",
			Line:    line,
			Message: "输出",
		})
	}
}

// Error 发送错误事件
func (tc *TaskContext) Error(message string) {
	tc.Progress <- &dto.ProgressEvent{
		Type:    "error",
		Line:    message,
		Message: "错误",
	}

	// 标记任务失败
	code := 1
	tc.Finished = true
	tc.ReturnCode = &code
	tc.Status = "error"
	now := time.Now()
	tc.EndTime = &now
}

// StopTask 停止任务
func (tm *TaskManager) StopTask(taskID string, userID uint) error {
	// 先检查内存中的任务
	tm.tasksLock.RLock()
	taskCtx, exists := tm.tasks[taskID]
	tm.tasksLock.RUnlock()

	if exists {
		// 验证用户权限
		if taskCtx.UserID != userID {
			return fmt.Errorf("无权停止此任务")
		}

		// 取消任务
		if taskCtx.CancelFunc != nil {
			taskCtx.CancelFunc()
		}

		// 更新状态
		taskCtx.Status = "stopped"
		taskCtx.Finished = true
		code := -1
		taskCtx.ReturnCode = &code

		tm.taskRepo.UpdateStatusWithTime(taskID, "stopped")

		// 清理Redis中的进度数据
		tm.clearTaskProgress(taskID)

		return nil
	}

	// 如果内存中不存在，说明Go后端可能重启过
	// 检查数据库中是否有这个任务
	task, err := tm.taskRepo.GetByTaskID(taskID)
	if err != nil {
		return fmt.Errorf("任务不存在")
	}

	// 关键：验证用户权限 - 只能停止自己的任务
	if task.UserID != userID {
		return fmt.Errorf("无权停止此任务")
	}

	// 只有当任务状态为running时，才允许停止
	if task.Status != "running" {
		return fmt.Errorf("任务状态为 %s，无法停止", task.Status)
	}

	// 任务在内存中不存在，可能是Go后端重启导致的
	// 此时Python进程可能已经失去了控制，直接更新数据库状态即可
	log.Printf("[StopTask] 任务 %s 在内存中不存在（可能是后端重启），更新数据库状态为stopped", taskID)
	tm.taskRepo.UpdateStatusWithTime(taskID, "stopped")

	// 清理Redis中的进度数据
	tm.clearTaskProgress(taskID)

	return nil
}

// clearTaskProgress 清理Redis中的任务进度数据
func (tm *TaskManager) clearTaskProgress(taskID string) {
	if tm.redisClient == nil {
		return
	}

	ctx := context.Background()
	redisKey := "task_progress:" + taskID

	// 删除Redis中的进度数据
	err := tm.redisClient.Del(ctx, redisKey).Err()
	if err != nil {
		log.Printf("[clearTaskProgress] 清理Redis进度失败: %v", err)
	} else {
		log.Printf("[clearTaskProgress] 已清理任务 %s 的Redis进度数据", taskID)
	}
}

// GetTask 获取任务信息
func (tm *TaskManager) GetTask(taskID string) (*TaskContext, bool) {
	tm.tasksLock.RLock()
	defer tm.tasksLock.RUnlock()
	taskCtx, exists := tm.tasks[taskID]
	return taskCtx, exists
}

// GetAllTasks 获取所有任务
func (tm *TaskManager) GetAllTasks() []*TaskContext {
	tm.tasksLock.RLock()
	defer tm.tasksLock.RUnlock()

	tasks := make([]*TaskContext, 0, len(tm.tasks))
	for _, task := range tm.tasks {
		tasks = append(tasks, task)
	}
	return tasks
}

// GetProgress 获取任务进度通道（为每个订阅者创建独立的通道）
func (tm *TaskManager) GetProgress(taskID string) (<-chan *dto.ProgressEvent, []*dto.ProgressEvent, func(), error) {
	tm.tasksLock.RLock()
	taskCtx, exists := tm.tasks[taskID]
	tm.tasksLock.RUnlock()

	if !exists {
		return nil, nil, nil, fmt.Errorf("任务不存在")
	}

	// 订阅新事件
	subscriberChan := taskCtx.Subscribe()

	// 获取历史事件（直接返回，让调用者处理）
	history := taskCtx.GetEventHistory()
	log.Printf("[GetProgress] 任务 %s 有 %d 条历史事件", taskID, len(history))

	// 返回取消订阅的函数
	unsubscribe := func() {
		taskCtx.Unsubscribe(subscriberChan)
	}

	return subscriberChan, history, unsubscribe, nil
}

// DeleteTask 删除任务
func (tm *TaskManager) DeleteTask(taskID string, userID uint) error {
	tm.tasksLock.RLock()
	taskCtx, exists := tm.tasks[taskID]
	tm.tasksLock.RUnlock()

	if !exists {
		return fmt.Errorf("任务不存在")
	}

	if taskCtx.UserID != userID {
		return fmt.Errorf("无权删除此任务")
	}

	if !taskCtx.Finished {
		return fmt.Errorf("只能删除已完成的任务")
	}

	// 从内存中删除
	tm.tasksLock.Lock()
	delete(tm.tasks, taskID)
	tm.tasksLock.Unlock()

	// 从数据库中删除
	tm.taskRepo.DeleteByTaskID(taskID)

	return nil
}

// generateUniqueTaskID 生成唯一任务ID
func (tm *TaskManager) generateUniqueTaskID(base string) string {
	taskID := base
	counter := 1

	for {
		exists, _ := tm.taskRepo.ExistsByTaskID(taskID)
		if !exists {
			break
		}
		taskID = fmt.Sprintf("%s_%d", base, counter)
		counter++
	}

	return taskID
}

// GetTasksFromDB 从数据库获取用户的任务列表
func (tm *TaskManager) GetTasksFromDB(userID uint) ([]*models.Task, error) {
	return tm.taskRepo.GetByUserID(userID)
}

