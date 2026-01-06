package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"time"

	"gen-go/internal/dto"
	"gen-go/internal/middleware"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
)

// TaskHandler 任务处理器
type TaskHandler struct {
	taskManager *service.TaskManager
	redisClient *redis.Client
}

// NewTaskHandler 创建任务处理器
func NewTaskHandler(taskManager *service.TaskManager, redisClient *redis.Client) *TaskHandler {
	return &TaskHandler{
		taskManager: taskManager,
		redisClient: redisClient,
	}
}

// StartTask 启动任务
func (h *TaskHandler) StartTask(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req dto.StartTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	// 设置默认值
	if req.BatchSize == 0 {
		req.BatchSize = 16
	}
	if req.MaxConcurrent == 0 {
		req.MaxConcurrent = 5
	}
	if req.MinScore == 0 {
		req.MinScore = 10
	}
	if req.VariantsPerSample == 0 {
		req.VariantsPerSample = 3
	}
	if req.DataRounds == 0 {
		req.DataRounds = 3
	}
	if req.RetryTimes == 0 {
		req.RetryTimes = 3
	}
	if req.TaskType == "" {
		req.TaskType = "general"
	}

	resp, err := h.taskManager.StartTask(userID, &req)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "任务已启动", resp)
}

// GetProgress 获取任务进度(SSE)
func (h *TaskHandler) GetProgress(c *gin.Context) {
	taskID := c.Param("task_id")

	progressChan, history, unsubscribe, err := h.taskManager.GetProgress(taskID)
	if err != nil {
		utils.NotFound(c, err.Error())
		return
	}
	defer unsubscribe() // 确保断开连接时取消订阅

	// 设置SSE响应头
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("X-Accel-Buffering", "no")
	c.Header("Access-Control-Allow-Origin", "*")

	// 发送初始连接成功事件
	initEvent := map[string]interface{}{
		"type":    "connected",
		"message": "SSE连接已建立",
		"task_id": taskID,
	}
	initData, _ := json.Marshal(initEvent)
	fmt.Fprintf(c.Writer, "data: %s\n\n", string(initData))
	c.Writer.Flush()

	// 先发送历史事件
	finishedInHistory := false
	for _, event := range history {
		data, _ := json.Marshal(event)
		fmt.Fprintf(c.Writer, "data: %s\n\n", string(data))
		c.Writer.Flush()
		if event.Type == "finished" {
			finishedInHistory = true
		}
	}

	// 如果历史事件中已经包含 finished，直接返回
	if finishedInHistory {
		log.Printf("[GetProgress] 任务 %s 已完成（历史事件中包含 finished）", taskID)
		return
	}

	// 使用 context 来处理客户端断开连接
	ctx := c.Request.Context()

	for {
		select {
		case <-ctx.Done():
			// 客户端断开连接
			log.Printf("[GetProgress] 客户端断开连接: %s", taskID)
			return
		case event, ok := <-progressChan:
			if !ok {
				// 通道已关闭
				log.Printf("[GetProgress] 进度通道已关闭: %s", taskID)
				return
			}
			data, _ := json.Marshal(event)
			fmt.Fprintf(c.Writer, "data: %s\n\n", string(data))
			c.Writer.Flush()

			if event.Type == "finished" {
				return
			}
		}
	}
}

// StopTask 停止任务
func (h *TaskHandler) StopTask(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	taskID := c.Param("task_id")

	log.Printf("[StopTask Handler] 收到停止任务请求: taskID=%s, userID=%d", taskID, userID)

	if err := h.taskManager.StopTask(taskID, userID); err != nil {
		log.Printf("[StopTask Handler] 停止任务失败: %v", err)
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "任务已停止", gin.H{
		"success": true,
	})
}

// DeleteTask 删除任务
func (h *TaskHandler) DeleteTask(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	taskID := c.Param("task_id")

	if err := h.taskManager.DeleteTask(taskID, userID); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "任务已删除", gin.H{
		"success": true,
	})
}

// GetTaskStatus 获取任务状态
func (h *TaskHandler) GetTaskStatus(c *gin.Context) {
	taskID := c.Param("task_id")

	taskCtx, exists := h.taskManager.GetTask(taskID)
	if !exists {
		utils.NotFound(c, "任务不存在")
		return
	}

	resp := dto.TaskStatusResponse{
		TaskID:   taskID,
		Status:   taskCtx.Status,
		Finished: taskCtx.Finished,
	}

	if taskCtx.ReturnCode != nil {
		resp.ReturnCode = taskCtx.ReturnCode
	}

	utils.SuccessResponse(c, resp)
}

// GetAllTasks 获取所有任务列表（从内存）
func (h *TaskHandler) GetAllTasks(c *gin.Context) {
	tasks := h.taskManager.GetAllTasks()

	taskList := make([]dto.TaskInfo, 0, len(tasks))
	for _, task := range tasks {
		runTime := float64(0)
		if task.EndTime != nil && !task.EndTime.IsZero() {
			runTime = task.EndTime.Sub(task.StartTime).Seconds()
		} else {
			runTime = time.Since(task.StartTime).Seconds()
		}

		info := dto.TaskInfo{
			TaskID:   task.TaskID,
			Status:   task.Status,
			Params:   task.Params,
			RunTime:  runTime,
			Finished: task.Finished,
		}

		if task.ReturnCode != nil {
			info.ReturnCode = task.ReturnCode
		}

		taskList = append(taskList, info)
	}

	utils.SuccessResponse(c, dto.TaskListResponse{
		Success: true,
		Tasks:   taskList,
	})
}

// GetActiveTask 获取运行中的任务（从内存）
func (h *TaskHandler) GetActiveTask(c *gin.Context) {
	tasks := h.taskManager.GetAllTasks()

	for _, task := range tasks {
		if !task.Finished {
			runTime := time.Since(task.StartTime).Seconds()
			utils.SuccessResponse(c, gin.H{
				"success":  true,
				"task_id":  task.TaskID,
				"params":   task.Params,
				"run_time": runTime,
			})
			return
		}
	}

	utils.SuccessResponse(c, gin.H{
		"success": false,
		"message": "没有运行中的任务",
	})
}

// GetProgressUnified 获取任务进度（从Redis）
// 用于前端轮询显示进度条
func (h *TaskHandler) GetProgressUnified(c *gin.Context) {
	taskID := c.Param("task_id")

	// 从Redis读取进度
	ctx := context.Background()
	redisKey := "task_progress:" + taskID

	// 先尝试从Redis Hash中读取（支持字符数统计）
	hashData, hashErr := h.redisClient.HGetAll(ctx, redisKey).Result()

	if hashErr == nil && len(hashData) > 0 {
		// Hash数据存在，使用Hash数据
		progressData := make(map[string]interface{})

		// 转换所有字段
		for key, val := range hashData {
			// 尝试解析为JSON值
			var jsonVal interface{}
			if err := json.Unmarshal([]byte(val), &jsonVal); err == nil {
				progressData[key] = jsonVal
			} else {
				// 如果不是JSON，尝试解析为数字
				if intVal, err := strconv.ParseInt(val, 10, 64); err == nil {
					progressData[key] = intVal
				} else {
					// 否则作为字符串
					progressData[key] = val
				}
			}
		}

		// 确保有task_id字段
		if _, ok := progressData["task_id"]; !ok {
			progressData["task_id"] = taskID
		}

		// 计算进度百分比
		progressPercent := 0.0
		if cp, ok := progressData["completion_percent"].(float64); ok {
			progressPercent = cp
		} else {
			// 回退：使用轮次计算进度
			if totalRounds, ok := progressData["total_rounds"].(float64); ok && totalRounds > 0 {
				if currentRound, ok := progressData["current_round"].(float64); ok {
					progressPercent = (currentRound / totalRounds) * 100
				}
			}
		}

		// 确保进度不超过100%
		if progressPercent > 100 {
			progressPercent = 100
		}

		// 添加进度百分比到响应
		progressData["progress_percent"] = progressPercent
		progressData["source"] = "redis"

		utils.SuccessResponse(c, gin.H{
			"success":  true,
			"progress": progressData,
		})
		return
	}

	// 如果Hash不存在，尝试读取字符串格式（兼容旧版本）
	val, err := h.redisClient.Get(ctx, redisKey).Result()
	if err != nil {
		if err == redis.Nil {
			// Redis中没有进度数据，检查任务是否在内存中
			taskCtx, exists := h.taskManager.GetTask(taskID)
			if exists {
				// 任务在内存中，返回基本信息
				runTime := time.Since(taskCtx.StartTime).Seconds()
				// 确定status字段：将Go的状态转换为前端期望的格式
				status := "running"
				if taskCtx.Finished {
					if taskCtx.ReturnCode != nil && *taskCtx.ReturnCode == 0 {
						status = "completed"
					} else {
						status = "failed"
					}
				}

				// 从params中获取total_rounds
				totalRounds := int64(3)
				if tr, ok := taskCtx.Params["total_rounds"].(float64); ok {
					totalRounds = int64(tr)
				}

				utils.SuccessResponse(c, gin.H{
					"success": true,
					"progress": gin.H{
						"task_id":          taskID,
						"status":           status,
						"current_round":    0,
						"total_rounds":     totalRounds,
						"total_samples":    0,
						"generated_count":  0,
						"progress_percent": float64(0),
						"run_time":         runTime,
						"source":           "memory",
					},
				})
				return
			}
			// 任务不存在
			utils.NotFound(c, "任务不存在")
			return
		}
		log.Printf("[GetProgressUnified] Redis错误: %v", err)
		utils.InternalError(c, "读取进度失败")
		return
	}

	// 解析JSON（字符串格式）
	var progressData map[string]interface{}
	if err := json.Unmarshal([]byte(val), &progressData); err != nil {
		log.Printf("[GetProgressUnified] 解析进度数据失败: %v", err)
		utils.InternalError(c, "解析进度数据失败")
		return
	}

	// 计算进度百分比
	// 优先使用 Python 计算的 completion_percent 字段（基于轮次完成比例，更准确）
	progressPercent := 0.0
	if cp, ok := progressData["completion_percent"].(float64); ok {
		progressPercent = cp
	} else {
		// 回退：使用轮次计算进度
		if totalRounds, ok := progressData["total_rounds"].(float64); ok && totalRounds > 0 {
			if currentRound, ok := progressData["current_round"].(float64); ok {
				progressPercent = (currentRound / totalRounds) * 100
			}
		}
	}

	// 确保进度不超过100%
	if progressPercent > 100 {
		progressPercent = 100
	}

	// 添加进度百分比到响应
	progressData["progress_percent"] = progressPercent
	progressData["source"] = "redis"

	utils.SuccessResponse(c, gin.H{
		"success":  true,
		"progress": progressData,
	})
}
