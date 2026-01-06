package service

import (
	"fmt"
	"mime/multipart"
	"strconv"
	"strings"

	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"
	"gen-go/internal/utils"
)

// DataFileService 数据文件服务
type DataFileService struct {
	fileRepo *repository.DataFileRepository
}

// NewDataFileService 创建数据文件服务
func NewDataFileService(fileRepo *repository.DataFileRepository) *DataFileService {
	return &DataFileService{
		fileRepo: fileRepo,
	}
}

// UploadFile 上传文件
func (s *DataFileService) UploadFile(userID uint, header *multipart.FileHeader, content []byte) (*models.DataFile, error) {
	// 检测内容类型
	contentType := utils.DetectContentType(content)

	// 如果是CSV,转换为JSONL
	var finalContent []byte
	var err error

	if strings.Contains(contentType, "csv") || strings.HasSuffix(header.Filename, ".csv") {
		// 使用专门的 CSV 到 JSONL 转换方法（支持 meta、Human、Assistant 格式）
		finalContent, err = utils.ConvertCSVToJSONL(content)
		if err != nil {
			return nil, fmt.Errorf("CSV转JSONL失败: %w", err)
		}
		contentType = "application/x-jsonlines"
	} else {
		finalContent = content
	}

	file := &models.DataFile{
		Filename:    header.Filename,
		FileContent: finalContent,
		FileSize:    len(finalContent),
		ContentType: contentType,
		UserID:      userID,
	}

	if err := s.fileRepo.Create(file); err != nil {
		return nil, fmt.Errorf("保存文件失败: %w", err)
	}

	return file, nil
}

// GetFile 获取文件
func (s *DataFileService) GetFile(fileID uint, userID uint) (*models.DataFile, error) {
	return s.fileRepo.GetByIDAndUserID(fileID, userID)
}

// ListFiles 获取文件列表
func (s *DataFileService) ListFiles(userID uint, page, perPage int) (*dto.PaginatedResponse, error) {
	offset := (page - 1) * perPage
	files, total, err := s.fileRepo.ListByUserID(userID, offset, perPage)
	if err != nil {
		return nil, err
	}

	fileResponses := make([]dto.DataFileResponse, len(files))
	for i, file := range files {
		fileResponses[i] = dto.DataFileResponse{
			ID:          file.ID,
			Filename:    file.Filename,
			FileSize:    file.FileSize,
			ContentType: file.ContentType,
			UserID:      file.UserID,
			CreatedAt:   file.CreatedAt.Format("2006-01-02 15:04:05"),
			UpdatedAt:   file.UpdatedAt.Format("2006-01-02 15:04:05"),
		}
	}

	return &dto.PaginatedResponse{
		Items: fileResponses,
		Total: total,
		Page:  page,
		PerPage: perPage,
	}, nil
}

// DeleteFile 删除文件
func (s *DataFileService) DeleteFile(fileID uint, userID uint) error {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return fmt.Errorf("文件不存在或无权访问")
	}

	return s.fileRepo.Delete(file.ID)
}

// BatchDeleteFiles 批量删除文件
func (s *DataFileService) BatchDeleteFiles(userID uint, ids []uint) error {
	for _, id := range ids {
		file, err := s.fileRepo.GetByIDAndUserID(id, userID)
		if err != nil {
			continue // 跳过不存在的文件
		}
		s.fileRepo.Delete(file.ID)
	}
	return nil
}

// GetFileContent 获取文件内容
func (s *DataFileService) GetFileContent(fileID uint, userID uint) (*dto.DataFileContentResponse, error) {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return nil, fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return nil, fmt.Errorf("解析文件内容失败: %w", err)
	}

	return &dto.DataFileContentResponse{
		ID:       file.ID,
		Filename: file.Filename,
		Content:  data,
		Total:    len(data),
	}, nil
}

// GetFileContentEditable 获取文件内容（带索引，用于编辑）
func (s *DataFileService) GetFileContentEditable(fileID uint, userID uint) (*dto.DataFileContentEditableResponse, error) {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return nil, fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return nil, fmt.Errorf("解析文件内容失败: %w", err)
	}

	// 构建带索引的数据项
	items := make([]dto.DataFileItem, len(data))
	for i, d := range data {
		items[i] = dto.DataFileItem{
			Index: i,
			Data:  d,
		}
	}

	return &dto.DataFileContentEditableResponse{
		FileID:     file.ID,
		Filename:   file.Filename,
		TotalLines: len(data),
		Items:      items,
	}, nil
}

// UpdateFileContent 更新文件内容中的某一项
func (s *DataFileService) UpdateFileContent(fileID uint, userID uint, itemIndex int, content map[string]interface{}) error {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return fmt.Errorf("解析文件内容失败: %w", err)
	}

	if itemIndex < 0 || itemIndex >= len(data) {
		return fmt.Errorf("索引越界")
	}

	data[itemIndex] = content

	// 转换回JSONL
	newContent, err := utils.ConvertToJSONL(data)
	if err != nil {
		return fmt.Errorf("序列化内容失败: %w", err)
	}

	file.FileContent = newContent
	return s.fileRepo.Update(file)
}

// AddFileContent 添加新内容到文件
func (s *DataFileService) AddFileContent(fileID uint, userID uint, content map[string]interface{}, index int) error {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return fmt.Errorf("解析文件内容失败: %w", err)
	}

	if index < 0 || index >= len(data) {
		// 添加到末尾
		data = append(data, content)
	} else {
		// 插入到指定位置
		data = append(data[:index+1], data[index:]...)
		data[index] = content
	}

	// 转换回JSONL
	newContent, err := utils.ConvertToJSONL(data)
	if err != nil {
		return fmt.Errorf("序列化内容失败: %w", err)
	}

	file.FileContent = newContent
	return s.fileRepo.Update(file)
}

// BatchDeleteContent 批量删除文件内容
func (s *DataFileService) BatchDeleteContent(fileID uint, userID uint, indices []int) (int, error) {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return 0, fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return 0, fmt.Errorf("解析文件内容失败: %w", err)
	}

	// 创建索引map用于快速查找
	indexMap := make(map[int]bool)
	for _, idx := range indices {
		indexMap[idx] = true
	}

	// 过滤掉要删除的项
	newData := make([]map[string]interface{}, 0, len(data))
	for i, item := range data {
		if !indexMap[i] {
			newData = append(newData, item)
		}
	}

	// 计算实际删除的数量（原始长度 - 新长度）
	deletedCount := len(data) - len(newData)

	// 转换回JSONL
	newContent, err := utils.ConvertToJSONL(newData)
	if err != nil {
		return 0, fmt.Errorf("序列化内容失败: %w", err)
	}

	file.FileContent = newContent
	if err := s.fileRepo.Update(file); err != nil {
		return 0, err
	}

	return deletedCount, nil
}

// DownloadFile 下载文件
func (s *DataFileService) DownloadFile(fileID uint, userID uint) (*models.DataFile, error) {
	return s.fileRepo.GetByIDAndUserID(fileID, userID)
}

// DownloadFileAsCSV 下载文件为CSV格式
func (s *DataFileService) DownloadFileAsCSV(fileID uint, userID uint) ([]byte, string, error) {
	file, err := s.fileRepo.GetByIDAndUserID(fileID, userID)
	if err != nil {
		return nil, "", fmt.Errorf("文件不存在或无权访问")
	}

	data, err := utils.ParseJSONL(file.FileContent)
	if err != nil {
		return nil, "", fmt.Errorf("解析文件内容失败: %w", err)
	}

	csvContent, err := utils.ConvertToCSV(data)
	if err != nil {
		return nil, "", fmt.Errorf("转换为CSV失败: %w", err)
	}

	// 生成文件名
	csvFilename := strings.TrimSuffix(file.Filename, ".jsonl") + ".csv"
	if !strings.HasSuffix(file.Filename, ".jsonl") {
		csvFilename = file.Filename + ".csv"
	}

	return csvContent, csvFilename, nil
}

// GetFileDisplayPath 获取文件显示路径(db://file_id/filename)
func (s *DataFileService) GetFileDisplayPath(fileID uint, filename string) string {
	return fmt.Sprintf("db://%d/%s", fileID, filename)
}

// ParseFileDisplayPath 解析文件显示路径
func (s *DataFileService) ParseFileDisplayPath(path string) (uint, string, error) {
	if !strings.HasPrefix(path, "db://") {
		return 0, "", fmt.Errorf("无效的文件路径格式")
	}

	parts := strings.SplitN(path[5:], "/", 2)
	if len(parts) != 2 {
		return 0, "", fmt.Errorf("无效的文件路径格式")
	}

	fileID, err := strconv.ParseUint(parts[0], 10, 32)
	if err != nil {
		return 0, "", fmt.Errorf("无效的文件ID: %w", err)
	}

	return uint(fileID), parts[1], nil
}
