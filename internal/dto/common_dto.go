package dto

// PaginatedResponse 分页响应
type PaginatedResponse struct {
	Items  interface{} `json:"data"`
	Total  int64       `json:"total"`
	Page   int         `json:"page"`
	PerPage int        `json:"per_page"`
}

// FileListResponse 文件列表响应
type FileListResponse struct {
	Success bool                `json:"success"`
	Files   []DataFileResponse  `json:"files"`
	Total   int64               `json:"total"`
}

// ModelListResponse 模型列表响应
type ModelListResponse struct {
	Success bool                 `json:"success"`
	Models  []ModelConfigResponse `json:"models"`
	Total   int64                `json:"total"`
}

// GeneratedDataListResponse 生成数据列表响应
type GeneratedDataListResponse struct {
	Success bool                    `json:"success"`
	Data    []GeneratedDataResponse `json:"data"`
	Total   int64                   `json:"total"`
}

// ReportListResponse 报告列表响应
type ReportListResponse struct {
	Success bool     `json:"success"`
	Reports []Report `json:"reports"`
	Total   int64    `json:"total"`
}

// Report 报告
type Report struct {
	TaskID      string `json:"task_id"`
	UserID      uint   `json:"user_id"`
	Status      string `json:"status"`
	TotalCount  int    `json:"total_count"`
	ConfirmedCount int `json:"confirmed_count"`
	CreatedAt   string `json:"created_at"`
}

// ReportDataResponse 报告数据响应
type ReportDataResponse struct {
	TaskID      string                   `json:"task_id"`
	Data        []map[string]interface{} `json:"data"`
	Total       int                      `json:"total"`
}

// ConvertFilesResponse 转换文件响应
type ConvertFilesResponse struct {
	Success bool               `json:"success"`
	Files   []DataFileResponse `json:"files"`
	Message string             `json:"message"`
}
