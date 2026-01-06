package service

import (
	"encoding/json"

	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"
	"gen-go/internal/utils"
)

// GeneratedDataService 生成数据服务
type GeneratedDataService struct {
	generatedDataRepo *repository.GeneratedDataRepository
}

// NewGeneratedDataService 创建生成数据服务
func NewGeneratedDataService(generatedDataRepo *repository.GeneratedDataRepository) *GeneratedDataService {
	return &GeneratedDataService{
		generatedDataRepo: generatedDataRepo,
	}
}

// ListData 获取生成数据列表
func (s *GeneratedDataService) ListData(taskID string, userID uint, page, perPage int) (*dto.PaginatedResponse, error) {
	offset := (page - 1) * perPage
	dataList, total, err := s.generatedDataRepo.ListByTaskID(taskID, offset, perPage)
	if err != nil {
		return nil, err
	}

	responses := make([]dto.GeneratedDataResponse, len(dataList))
	for i, data := range dataList {
		var dataContent map[string]interface{}
		json.Unmarshal([]byte(data.DataContent), &dataContent)

		responses[i] = dto.GeneratedDataResponse{
			ID:              data.ID,
			TaskID:          data.TaskID,
			UserID:          data.UserID,
			DataContent:     data.DataContent,
			ModelScore:      data.ModelScore,
			RuleScore:       data.RuleScore,
			RetryCount:      data.RetryCount,
			GenerationModel: data.GenerationModel,
			TaskType:        data.TaskType,
			IsConfirmed:     data.IsConfirmed,
			CreatedAt:       data.CreatedAt.Format("2006-01-02 15:04:05"),
			UpdatedAt:       data.UpdatedAt.Format("2006-01-02 15:04:05"),
		}
	}

	return &dto.PaginatedResponse{
		Items:   responses,
		Total:   total,
		Page:    page,
		PerPage: perPage,
	}, nil
}

// BatchUpdate 批量更新数据
func (s *GeneratedDataService) BatchUpdate(updates []dto.UpdateGeneratedDataRequest) error {
	for _, update := range updates {
		data, err := s.generatedDataRepo.GetByID(update.ID)
		if err != nil {
			continue
		}

		// 优先使用 Content 字段，如果没有则使用 DataContent（向后兼容）
		content := update.Content
		if content == nil && update.DataContent != nil {
			content = update.DataContent
		}

		// 更新内容
		contentJSON, _ := json.Marshal(content)
		data.DataContent = string(contentJSON)

		if update.ModelScore != nil {
			data.ModelScore = update.ModelScore
		}
		if update.RuleScore != nil {
			data.RuleScore = update.RuleScore
		}

		s.generatedDataRepo.Update(data)
	}
	return nil
}

// ConfirmData 确认或取消确认单条数据
func (s *GeneratedDataService) ConfirmData(dataID uint, isConfirmed bool) error {
	data, err := s.generatedDataRepo.GetByID(dataID)
	if err != nil {
		return err
	}

	data.IsConfirmed = isConfirmed
	return s.generatedDataRepo.Update(data)
}

// BatchConfirm 批量确认数据
func (s *GeneratedDataService) BatchConfirm(ids []uint) error {
	return s.generatedDataRepo.ConfirmBatch(ids)
}

// ExportData 导出数据
func (s *GeneratedDataService) ExportData(taskID string, format string) ([]byte, string, error) {
	offset := 0
	limit := 100000 // 大批量
	dataList, _, err := s.generatedDataRepo.ListByTaskID(taskID, offset, limit)
	if err != nil {
		return nil, "", err
	}

	if format == "csv" {
		// 将所有JSONL数据合并为一个字符串，然后使用正确的对话格式转换为CSV
		var jsonlData []byte
		for _, data := range dataList {
			jsonlData = append(jsonlData, []byte(data.DataContent)...)
			jsonlData = append(jsonlData, '\n')
		}

		// 使用专门的 JSONL 到 CSV 转换方法（支持 meta、Human、Assistant 格式）
		csvContent, err := utils.ConvertJSONLToCSV(jsonlData)
		if err != nil {
			return nil, "", err
		}
		filename := taskID + ".csv"
		return csvContent, filename, nil
	}

	// 默认JSONL
	var result []byte
	for _, data := range dataList {
		result = append(result, []byte(data.DataContent)...)
		result = append(result, '\n')
	}
	filename := taskID + ".jsonl"
	return result, filename, nil
}

// DeleteBatch 批量删除数据
func (s *GeneratedDataService) DeleteBatch(ids []uint) (int64, error) {
	return s.generatedDataRepo.DeleteByIDs(ids)
}

// GetTaskInfo 获取任务数据信息
func (s *GeneratedDataService) GetTaskInfo(taskID string) (map[string]interface{}, error) {
	offset := 0
	limit := 1
	dataList, total, err := s.generatedDataRepo.ListByTaskID(taskID, offset, limit)
	if err != nil {
		return nil, err
	}

	unconfirmed, _ := s.generatedDataRepo.GetUnconfirmedCount(taskID)

	return map[string]interface{}{
		"task_id":           taskID,
		"total_count":       total,
		"unconfirmed_count": unconfirmed,
		"confirmed_count":   total - unconfirmed,
		"sample":            dataList,
	}, nil
}

// AddData 添加单条数据
func (s *GeneratedDataService) AddData(taskID string, userID uint, content map[string]interface{}) (uint, error) {
	// 将 content 转换为 JSON 字符串
	contentJSON, err := json.Marshal(content)
	if err != nil {
		return 0, err
	}

	data := &models.GeneratedData{
		TaskID:          taskID,
		UserID:          userID,
		DataContent:     string(contentJSON),
		IsConfirmed:     false,
		RetryCount:      0,
		TaskType:        "manual", // 手动添加的数据
		GenerationModel: "manual", // 手动添加的数据
	}

	err = s.generatedDataRepo.Create(data)
	if err != nil {
		return 0, err
	}

	return data.ID, nil
}
