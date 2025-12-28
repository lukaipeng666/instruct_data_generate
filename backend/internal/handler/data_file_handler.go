package handler

import (
	"io"
	"net/url"
	"strconv"

	"gen-go/internal/dto"
	"gen-go/internal/middleware"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// DataFileHandler 数据文件处理器
type DataFileHandler struct {
	dataFileService *service.DataFileService
}

// NewDataFileHandler 创建数据文件处理器
func NewDataFileHandler(dataFileService *service.DataFileService) *DataFileHandler {
	return &DataFileHandler{
		dataFileService: dataFileService,
	}
}

// UploadFile 上传文件
func (h *DataFileHandler) UploadFile(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	file, err := c.FormFile("file")
	if err != nil {
		utils.BadRequest(c, "文件上传失败: "+err.Error())
		return
	}

	// 读取文件内容
	src, err := file.Open()
	if err != nil {
		utils.BadRequest(c, "打开文件失败: "+err.Error())
		return
	}
	defer src.Close()

	content := make([]byte, file.Size)
	_, err = io.ReadFull(src, content)
	if err != nil && err != io.ErrUnexpectedEOF {
		utils.BadRequest(c, "读取文件失败: "+err.Error())
		return
	}

	// 上传文件
	dataFile, err := h.dataFileService.UploadFile(userID, file, content)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "文件上传成功", gin.H{
		"id":          dataFile.ID,
		"filename":    dataFile.Filename,
		"display_path": h.dataFileService.GetFileDisplayPath(dataFile.ID, dataFile.Filename),
		"file_size":   dataFile.FileSize,
	})
}

// ListFiles 获取文件列表
func (h *DataFileHandler) ListFiles(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	if page < 1 {
		page = 1
	}
	if perPage < 1 || perPage > 100 {
		perPage = 20
	}

	result, err := h.dataFileService.ListFiles(userID, page, perPage)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.PaginatedResponse(c, result.Items, result.Total, result.Page, result.PerPage)
}

// GetFile 获取文件详情
func (h *DataFileHandler) GetFile(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	file, err := h.dataFileService.GetFile(uint(fileID), userID)
	if err != nil {
		utils.NotFound(c, "文件不存在")
		return
	}

	utils.SuccessResponse(c, dto.DataFileResponse{
		ID:          file.ID,
		Filename:    file.Filename,
		FileSize:    file.FileSize,
		ContentType: file.ContentType,
		UserID:      file.UserID,
		CreatedAt:   file.CreatedAt.Format("2006-01-02 15:04:05"),
		UpdatedAt:   file.UpdatedAt.Format("2006-01-02 15:04:05"),
	})
}

// DeleteFile 删除文件
func (h *DataFileHandler) DeleteFile(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	if err := h.dataFileService.DeleteFile(uint(fileID), userID); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "文件已删除", gin.H{"success": true})
}

// BatchDeleteFiles 批量删除文件
func (h *DataFileHandler) BatchDeleteFiles(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req dto.BatchDeleteRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.dataFileService.BatchDeleteFiles(userID, req.IDs); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "批量删除成功", gin.H{"success": true})
}

// DownloadFile 下载文件
func (h *DataFileHandler) DownloadFile(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	file, err := h.dataFileService.GetFile(uint(fileID), userID)
	if err != nil {
		utils.NotFound(c, "文件不存在")
		return
	}

	// URL 编码文件名以支持中文和特殊字符（使用 QueryEscape，类似 Python 的 quote）
	encodedFilename := url.QueryEscape(file.Filename)

	// 设置正确的 Content-Disposition，支持 UTF-8 编码
	// 同时提供两种格式：fallback 的 ASCII 和 RFC 5987 的 UTF-8
	c.Header("Content-Disposition", "attachment; filename=\""+file.Filename+"\"; filename*=UTF-8''"+encodedFilename)
	c.Data(200, file.ContentType, file.FileContent)
}

// DownloadFileAsCSV 下载文件为CSV格式
func (h *DataFileHandler) DownloadFileAsCSV(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	content, filename, err := h.dataFileService.DownloadFileAsCSV(uint(fileID), userID)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	// URL 编码文件名以支持中文和特殊字符
	encodedFilename := url.QueryEscape(filename)

	// 设置正确的 Content-Disposition，支持 UTF-8 编码
	c.Header("Content-Disposition", "attachment; filename=\""+filename+"\"; filename*=UTF-8''"+encodedFilename)
	c.Data(200, "text/csv", content)
}

// GetFileContent 获取文件内容
func (h *DataFileHandler) GetFileContent(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	content, err := h.dataFileService.GetFileContent(uint(fileID), userID)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessResponse(c, content)
}

// GetTaskTypes 获取支持的任务类型列表
func (h *DataFileHandler) GetTaskTypes(c *gin.Context) {
	// 返回支持的任务类型（从 Python 版本迁移）
	taskTypes := []string{
		"entity_extraction",  // 实体提取
		"general",           // 通用
		"question_rewrite",  // 问句改写
		"calculation",       // 计算
	}

	utils.SuccessResponse(c, gin.H{
		"success": true,
		"types":    taskTypes,
	})
}

// GetFileContentEditable 获取文件内容（带索引，用于编辑）
func (h *DataFileHandler) GetFileContentEditable(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	content, err := h.dataFileService.GetFileContentEditable(uint(fileID), userID)
	if err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessResponse(c, content)
}

// UpdateFileContent 更新文件内容
func (h *DataFileHandler) UpdateFileContent(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)
	itemIndex, _ := strconv.Atoi(c.Param("item_index"))

	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.dataFileService.UpdateFileContent(uint(fileID), userID, itemIndex, req); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "更新成功", gin.H{"success": true})
}

// AddFileContent 添加文件内容
func (h *DataFileHandler) AddFileContent(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	var req dto.AddFileContentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.dataFileService.AddFileContent(uint(fileID), userID, req.Content, req.Index); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "添加成功", gin.H{"success": true})
}

// BatchDeleteContent 批量删除文件内容
func (h *DataFileHandler) BatchDeleteContent(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)
	fileID, _ := strconv.ParseUint(c.Param("file_id"), 10, 32)

	var req struct {
		Indices []int `json:"indices" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	if err := h.dataFileService.BatchDeleteContent(uint(fileID), userID, req.Indices); err != nil {
		utils.InternalError(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "批量删除成功", gin.H{"success": true})
}

// BatchDownloadFiles 批量下载文件
func (h *DataFileHandler) BatchDownloadFiles(c *gin.Context) {
	userID, _ := middleware.GetUserID(c)

	var req dto.BatchDownloadRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	// 简化实现:返回文件列表
	var files []gin.H
	for _, id := range req.IDs {
		file, err := h.dataFileService.GetFile(id, userID)
		if err == nil {
			files = append(files, gin.H{
				"id":           file.ID,
				"filename":     file.Filename,
				"display_path": h.dataFileService.GetFileDisplayPath(file.ID, file.Filename),
			})
		}
	}

	utils.SuccessResponse(c, gin.H{
		"files": files,
		"message": "请使用单独的下载接口下载每个文件",
	})
}
