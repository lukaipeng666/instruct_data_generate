package handler

import (
	"net/url"
	"strconv"

	"gen-go/internal/dto"
	"gen-go/internal/middleware"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// GeneratedDataHandler 生成数据处理器
type GeneratedDataHandler struct {
	generatedDataService *service.GeneratedDataService
}

// NewGeneratedDataHandler 创建生成数据处理器
func NewGeneratedDataHandler(generatedDataService *service.GeneratedDataService) *GeneratedDataHandler {
	return &GeneratedDataHandler{
		generatedDataService: generatedDataService,
	}
}

// ListData 获取生成数据列表
func (h *GeneratedDataHandler) ListData(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	taskID := c.Query("task_id")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	if taskID == "" {
		utils.BadRequest(c, "缺少task_id参数")
		return
	}

	result, err := h.generatedDataService.ListData(taskID, userID, page, perPage)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.PaginatedResponse(c, result.Items, result.Total, result.Page, result.PerPage)
}

// BatchUpdate 批量更新数据
func (h *GeneratedDataHandler) BatchUpdate(c *gin.Context) {
	var req dto.BatchUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.generatedDataService.BatchUpdate(req.Updates); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "批量更新成功", gin.H{"success": true})
}

// BatchConfirm 批量确认数据
func (h *GeneratedDataHandler) BatchConfirm(c *gin.Context) {
	var req dto.BatchConfirmRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.generatedDataService.BatchConfirm(req.IDs); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "批量确认成功", gin.H{"success": true})
}

// ExportData 导出数据
func (h *GeneratedDataHandler) ExportData(c *gin.Context) {
	taskID := c.Query("task_id")
	format := c.DefaultQuery("format", "jsonl")

	if taskID == "" {
		utils.BadRequest(c, "缺少task_id参数")
		return
	}

	data, filename, err := h.generatedDataService.ExportData(taskID, format)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	c.Header("Content-Disposition", "attachment; filename=\""+filename+"\"")
	c.Data(200, "application/octet-stream", data)
}

// DownloadTaskData 下载任务数据
func (h *GeneratedDataHandler) DownloadTaskData(c *gin.Context) {
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

// GetTaskInfo 获取任务数据信息
func (h *GeneratedDataHandler) GetTaskInfo(c *gin.Context) {
	taskID := c.Param("task_id")

	info, err := h.generatedDataService.GetTaskInfo(taskID)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessResponse(c, info)
}

// UpdateData 更新单条数据
func (h *GeneratedDataHandler) UpdateData(c *gin.Context) {
	dataID, _ := strconv.ParseUint(c.Param("data_id"), 10, 32)

	var req dto.UpdateGeneratedDataRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	req.ID = uint(dataID)
	if err := h.generatedDataService.BatchUpdate([]dto.UpdateGeneratedDataRequest{req}); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "更新成功", gin.H{"success": true})
}

// ConfirmData 确认单条数据（支持切换确认状态）
func (h *GeneratedDataHandler) ConfirmData(c *gin.Context) {
	dataID, _ := strconv.ParseUint(c.Param("data_id"), 10, 32)

	var req dto.ConfirmDataRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		// 如果请求体为空或解析失败，默认为确认
		req.IsConfirmed = true
	}

	if err := h.generatedDataService.ConfirmData(uint(dataID), req.IsConfirmed); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	message := "已取消确认"
	if req.IsConfirmed {
		message = "确认成功"
	}
	utils.SuccessWithMessage(c, message, gin.H{"success": true})
}

// DeleteBatch 批量删除数据
func (h *GeneratedDataHandler) DeleteBatch(c *gin.Context) {
	var req dto.BatchDeleteRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.generatedDataService.DeleteBatch(req.IDs); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "批量删除成功", gin.H{"success": true})
}
