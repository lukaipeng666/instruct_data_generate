package handler

import (
	"net/url"
	"strconv"

	"gen-go/internal/repository"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// AdminHandler 管理员处理器
type AdminHandler struct {
	userRepo              *repository.UserRepository
	taskRepo              *repository.TaskRepository
	generatedDataRepo     *repository.GeneratedDataRepository
	generatedDataService  *service.GeneratedDataService
	modelService          *service.ModelService
}

// NewAdminHandler 创建管理员处理器
func NewAdminHandler(
	userRepo *repository.UserRepository,
	taskRepo *repository.TaskRepository,
	generatedDataRepo *repository.GeneratedDataRepository,
	generatedDataService *service.GeneratedDataService,
	modelService *service.ModelService,
) *AdminHandler {
	return &AdminHandler{
		userRepo:              userRepo,
		taskRepo:              taskRepo,
		generatedDataRepo:     generatedDataRepo,
		generatedDataService:  generatedDataService,
		modelService:          modelService,
	}
}

// ListUsers 获取所有用户
func (h *AdminHandler) ListUsers(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	offset := (page - 1) * perPage
	users, total, err := h.userRepo.List(offset, perPage)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.PaginatedResponse(c, users, total, page, perPage)
}

// DeleteUser 删除用户
func (h *AdminHandler) DeleteUser(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	if err := h.userRepo.Delete(uint(id)); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "用户已删除", gin.H{"success": true})
}

// GetUserReports 获取用户报告
func (h *AdminHandler) GetUserReports(c *gin.Context) {
	// 获取路径参数中的用户ID
	userID, err := strconv.ParseUint(c.Param("id"), 10, 32)
	if err != nil {
		utils.BadRequest(c, "无效的用户ID")
		return
	}

	// 获取用户的所有任务（不限制数量）
	tasks, _, err := h.taskRepo.ListByUserID(uint(userID), 0, 1000)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// 构建报告列表
	reports := make([]map[string]interface{}, 0, len(tasks))
	for _, task := range tasks {
		// 获取生成数据条数
		_, dataCount, err := h.generatedDataRepo.ListByTaskID(task.TaskID, 0, 1)
		if err != nil {
			dataCount = 0
		}

		// 获取已确认数据条数
		confirmedCount, _ := h.generatedDataRepo.GetConfirmedCount(task.TaskID)

		// 解析参数
		var params interface{}
		if task.Params != nil {
			params = task.Params
		}

		reports = append(reports, map[string]interface{}{
			"id":               task.ID,
			"task_id":          task.TaskID,
			"status":           task.Status,
			"started_at":       task.StartedAt,
			"finished_at":      task.FinishedAt,
			"data_count":       int(dataCount),
			"has_data":         dataCount > 0,
			"confirmed_count":  int(confirmedCount),
			"is_fully_reviewed": dataCount > 0 && confirmedCount == dataCount,
			"input_chars":       task.InputChars,
			"output_chars":      task.OutputChars,
			"params":           params,
			"error_message":    task.ErrorMessage,
		})
	}

	utils.SuccessResponse(c, gin.H{
		"success": true,
		"reports": reports,
		"total":   len(reports),
	})
}

// DownloadUserReport 下载用户报告
func (h *AdminHandler) DownloadUserReport(c *gin.Context) {
	taskID := c.Param("task_id")
	format := c.DefaultQuery("format", "jsonl")

	data, filename, err := h.generatedDataService.ExportData(taskID, format)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// URL 编码文件名以支持中文和特殊字符
	encodedFilename := url.QueryEscape(filename)

	// 设置正确的 Content-Disposition，支持 UTF-8 编码
	c.Header("Content-Disposition", "attachment; filename=\""+filename+"\"; filename*=UTF-8''"+encodedFilename)
	c.Data(200, "application/octet-stream", data)
}

// ListAllTasks 获取所有任务
func (h *AdminHandler) ListAllTasks(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	offset := (page - 1) * perPage
	tasks, total, err := h.taskRepo.List(offset, perPage)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.PaginatedResponse(c, tasks, total, page, perPage)
}

// DeleteTask 删除任务记录
func (h *AdminHandler) DeleteTask(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	if err := h.taskRepo.Delete(uint(id)); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "任务已删除", gin.H{"success": true})
}

// ListAllModels (已由ModelHandler实现)
// CreateModel (已由ModelHandler实现)
// UpdateModel (已由ModelHandler实现)
// DeleteModel (已由ModelHandler实现)
