package handler

import (
	"gen-go/internal/dto"
	"gen-go/internal/middleware"
	"gen-go/internal/repository"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// ReportHandler 报告处理器
type ReportHandler struct {
	generatedDataRepo *repository.GeneratedDataRepository
	taskRepo          *repository.TaskRepository
}

// NewReportHandler 创建报告处理器
func NewReportHandler(generatedDataRepo *repository.GeneratedDataRepository, taskRepo *repository.TaskRepository) *ReportHandler {
	return &ReportHandler{
		generatedDataRepo: generatedDataRepo,
		taskRepo:          taskRepo,
	}
}

// ListReports 获取报告列表
func (h *ReportHandler) ListReports(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	// 获取用户的所有任务（不限制数量）
	tasks, _, err := h.taskRepo.ListByUserID(userID, 0, 1000)
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
			"params":           params,
			"error_message":    task.ErrorMessage,
		})
	}

	utils.SuccessResponse(c, gin.H{
		"success": true,
		"reports": reports,
	})
}

// GetReportData 获取任务报告数据
func (h *ReportHandler) GetReportData(c *gin.Context) {
	taskID := c.Param("task_id")

	offset := 0
	limit := 10000
	dataList, total, err := h.generatedDataRepo.ListByTaskID(taskID, offset, limit)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// 转换为map格式
	data := make([]map[string]interface{}, len(dataList))
	for i, item := range dataList {
		data[i] = map[string]interface{}{
			"id":               item.ID,
			"task_id":          item.TaskID,
			"user_id":          item.UserID,
			"data_content":     item.DataContent,
			"model_score":      item.ModelScore,
			"rule_score":       item.RuleScore,
			"retry_count":      item.RetryCount,
			"generation_model": item.GenerationModel,
			"task_type":        item.TaskType,
			"is_confirmed":     item.IsConfirmed,
			"created_at":       item.CreatedAt,
			"updated_at":       item.UpdatedAt,
		}
	}

	utils.SuccessResponse(c, dto.ReportDataResponse{
		TaskID: taskID,
		Data:   data,
		Total: int(total),
	})
}

// DeleteReport 删除报告
func (h *ReportHandler) DeleteReport(c *gin.Context) {
	taskID := c.Param("task_id")

	// 删除任务的所有生成数据
	if err := h.generatedDataRepo.DeleteByTaskID(taskID); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// 同时删除任务记录
	if err := h.taskRepo.DeleteByTaskID(taskID); err != nil {
		// 生成数据已删除，任务记录删除失败只记录日志，不影响响应
		// 因为主要目的是删除数据
	}

	utils.SuccessWithMessage(c, "报告已删除", gin.H{"success": true})
}

// GetReportDataEditable 获取任务报告数据（可编辑格式）
func (h *ReportHandler) GetReportDataEditable(c *gin.Context) {
	taskID := c.Param("task_id")

	offset := 0
	limit := 10000
	dataList, total, err := h.generatedDataRepo.ListByTaskID(taskID, offset, limit)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// 转换为可编辑格式（包含解析后的 data 对象）
	data := make([]map[string]interface{}, len(dataList))
	for i, item := range dataList {
		// 解析 JSON data_content
		var dataContent interface{}
		if err := utils.ParseJSONString(item.DataContent, &dataContent); err != nil {
			dataContent = map[string]interface{}{}
		}

		data[i] = map[string]interface{}{
			"id":           item.ID,
			"data":         dataContent,
			"is_confirmed": item.IsConfirmed,
			"created_at":   item.CreatedAt,
			"updated_at":   item.UpdatedAt,
		}
	}

	utils.SuccessResponse(c, gin.H{
		"data":   data,
		"count":  int(total),
		"success": true,
	})
}

// BatchDeleteReports 批量删除报告
func (h *ReportHandler) BatchDeleteReports(c *gin.Context) {
	var req struct {
		TaskIDs []string `json:"task_ids" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	for _, taskID := range req.TaskIDs {
		// 删除生成数据
		h.generatedDataRepo.DeleteByTaskID(taskID)
		// 同时删除任务记录
		h.taskRepo.DeleteByTaskID(taskID)
	}

	utils.SuccessWithMessage(c, "批量删除成功", gin.H{"success": true})
}
