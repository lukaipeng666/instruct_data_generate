package handler

import (
	"strconv"

	"gen-go/internal/dto"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// ModelHandler 模型处理器
type ModelHandler struct {
	modelService *service.ModelService
}

// NewModelHandler 创建模型处理器
func NewModelHandler(modelService *service.ModelService) *ModelHandler {
	return &ModelHandler{modelService: modelService}
}

// GetModels 获取激活的模型列表
func (h *ModelHandler) GetModels(c *gin.Context) {
	models, err := h.modelService.GetActiveModels()
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessResponse(c, dto.ModelListResponse{
		Success: true,
		Models:  models,
		Total:   int64(len(models)),
	})
}

// GetAllModels 获取所有模型(管理员)
func (h *ModelHandler) GetAllModels(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	result, err := h.modelService.GetAllModels(page, perPage)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.PaginatedResponse(c, result.Items, result.Total, result.Page, result.PerPage)
}

// CreateModel 创建模型
func (h *ModelHandler) CreateModel(c *gin.Context) {
	var req dto.CreateModelConfigRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	model, err := h.modelService.CreateModel(&req)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "模型创建成功", model)
}

// UpdateModel 更新模型
func (h *ModelHandler) UpdateModel(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	var req dto.UpdateModelConfigRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.modelService.UpdateModel(uint(id), &req); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "模型更新成功", gin.H{"success": true})
}

// DeleteModel 删除模型
func (h *ModelHandler) DeleteModel(c *gin.Context) {
	id, _ := strconv.ParseUint(c.Param("id"), 10, 32)

	if err := h.modelService.DeleteModel(uint(id)); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "模型删除成功", gin.H{"success": true})
}

// ModelCall 模型调用代理
func (h *ModelHandler) ModelCall(c *gin.Context) {
	var req dto.ModelCallProxyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	// 调用模型服务
	resp, err := h.modelService.CallModel(&req)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// 返回响应
	c.JSON(200, resp)
}
