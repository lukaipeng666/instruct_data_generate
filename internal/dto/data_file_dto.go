package dto

// DataFileResponse 文件响应
type DataFileResponse struct {
	ID          uint   `json:"id"`
	Filename    string `json:"filename"`
	FileSize    int    `json:"file_size"`
	ContentType string `json:"content_type"`
	UserID      uint   `json:"user_id"`
	CreatedAt   string `json:"created_at"`
	UpdatedAt   string `json:"updated_at"`
}

// DataFileContentResponse 文件内容响应
type DataFileContentResponse struct {
	ID        uint                   `json:"id"`
	Filename  string                 `json:"filename"`
	Content   []map[string]interface{} `json:"content"`
	Total     int                    `json:"total"`
}

// DataFileItem 文件数据项（带索引）
type DataFileItem struct {
	Index int         `json:"index"`
	Data  interface{} `json:"data"`
}

// DataFileContentEditableResponse 可编辑文件内容响应（带索引）
type DataFileContentEditableResponse struct {
	FileID     uint           `json:"file_id"`
	Filename   string         `json:"filename"`
	TotalLines int            `json:"total_lines"`
	Items      []DataFileItem `json:"items"`
}

// UpdateFileContentRequest 更新文件内容请求
type UpdateFileContentRequest struct {
	Content map[string]interface{} `json:"content" binding:"required"`
}

// AddFileContentRequest 添加文件内容请求
type AddFileContentRequest struct {
	Content map[string]interface{} `json:"content" binding:"required"`
	Index   int                    `json:"index"`
}

// BatchDeleteRequest 批量删除请求
type BatchDeleteRequest struct {
	IDs []uint `json:"ids" binding:"required"`
}

// BatchDownloadRequest 批量下载请求
type BatchDownloadRequest struct {
	IDs []uint `json:"ids" binding:"required"`
}

// BatchConvertRequest 批量转换请求
type BatchConvertRequest struct {
	FileIDs      []uint `json:"file_ids" binding:"required"`
	TargetFormat string `json:"target_format" binding:"required,oneof=jsonl csv"`
}

// ConvertFilesRequest 上传并转换请求
type ConvertFilesRequest struct {
	Files        []string `json:"files" binding:"required"`
	TargetFormat string   `json:"target_format" binding:"required,oneof=jsonl csv"`
}
