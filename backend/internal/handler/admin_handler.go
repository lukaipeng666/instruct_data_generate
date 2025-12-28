package handler

import (
	"strconv"

	"gen-go/internal/dto"
	"gen-go/internal/repository"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// AdminHandler 管理员处理器
type AdminHandler struct {
	userRepo    *repository.UserRepository
	taskRepo    *repository.TaskRepository
	modelService *service.ModelService
}

// NewAdminHandler 创建管理员处理器
func NewAdminHandler(
	userRepo *repository.UserRepository,
	taskRepo *repository.TaskRepository,
	modelService *service.ModelService,
) *AdminHandler {
	return &AdminHandler{
		userRepo:    userRepo,
		taskRepo:    taskRepo,
		modelService: modelService,
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
	// 简化实现
	utils.SuccessResponse(c, gin.H{
		"reports": []dto.Report{},
		"total":   0,
	})
}

// DownloadUserReport 下载用户报告
func (h *AdminHandler) DownloadUserReport(c *gin.Context) {
	// 简化实现
	utils.BadRequest(c, "功能开发中")
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
