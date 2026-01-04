package dto

// GeneratedDataResponse 生成数据响应
type GeneratedDataResponse struct {
	ID              uint    `json:"id"`
	TaskID          string  `json:"task_id"`
	UserID          uint    `json:"user_id"`
	DataContent     string  `json:"data_content"`
	ModelScore      *float64 `json:"model_score"`
	RuleScore       *int    `json:"rule_score"`
	RetryCount      int     `json:"retry_count"`
	GenerationModel string  `json:"generation_model"`
	TaskType        string  `json:"task_type"`
	IsConfirmed     bool    `json:"is_confirmed"`
	CreatedAt       string  `json:"created_at"`
	UpdatedAt       string  `json:"updated_at"`
}

// UpdateGeneratedDataRequest 更新生成数据请求
type UpdateGeneratedDataRequest struct {
	ID          uint                   `json:"id"`
	Content     map[string]interface{} `json:"content" binding:"required"`
	DataContent map[string]interface{} `json:"data_content"` // 别名，用于向后兼容
	ModelScore  *float64               `json:"model_score"`
	RuleScore   *int                   `json:"rule_score"`
}

// BatchUpdateRequest 批量更新请求
type BatchUpdateRequest struct {
	Updates []UpdateGeneratedDataRequest `json:"updates" binding:"required"`
}

// BatchConfirmRequest 批量确认请求
type BatchConfirmRequest struct {
	IDs []uint `json:"ids" binding:"required"`
}

// ConfirmDataRequest 确认单条数据请求
type ConfirmDataRequest struct {
	IsConfirmed bool `json:"is_confirmed"`
}

// ExportRequest 导出请求
type ExportRequest struct {
	TaskID     string   `json:"task_id"`
	Confirmed  bool     `json:"confirmed"`
	Format     string   `json:"format" binding:"required,oneof=jsonl csv"`
	DataIDs    []uint   `json:"data_ids"`
}
