package dto

// StartTaskRequest 启动任务请求
type StartTaskRequest struct {
	InputFile         string   `json:"input_file" binding:"required"`
	ModelID           *uint    `json:"model_id"`
	Model             string   `json:"model"`
	Services          []string `json:"services"`
	BatchSize         int      `json:"batch_size"`
	MaxConcurrent     int      `json:"max_concurrent"`
	MinScore          int      `json:"min_score"`
	TaskType          string   `json:"task_type"`
	VariantsPerSample int      `json:"variants_per_sample"`
	DataRounds        int      `json:"data_rounds"`
	RetryTimes        int      `json:"retry_times"`
	SpecialPrompt     string   `json:"special_prompt"`
	Directions        string   `json:"directions"`
	APIKey            string   `json:"api_key"`
	IsVLLM            bool     `json:"is_vllm"`
	UseProxy          bool     `json:"use_proxy"`
	TopP              float64  `json:"top_p"`
	MaxTokens         int      `json:"max_tokens"`
	Timeout           int      `json:"timeout"`
}

// StartTaskResponse 启动任务响应
type StartTaskResponse struct {
	Success bool   `json:"success"`
	TaskID  string `json:"task_id"`
	Status  string `json:"status"`
}

// TaskStatusResponse 任务状态响应
type TaskStatusResponse struct {
	TaskID     string  `json:"task_id"`
	Status     string  `json:"status"`
	Finished   bool    `json:"finished"`
	ReturnCode *int    `json:"return_code,omitempty"`
	Progress   float64 `json:"progress_percent,omitempty"`
	Message    string  `json:"message,omitempty"`
}

// TaskInfo 任务信息
type TaskInfo struct {
	TaskID     string                 `json:"task_id"`
	Status     string                 `json:"status"`
	Params     map[string]interface{} `json:"params"`
	RunTime    float64                `json:"run_time"`
	Finished   bool                   `json:"finished"`
	ReturnCode *int                   `json:"return_code,omitempty"`
}

// TaskListResponse 任务列表响应
type TaskListResponse struct {
	Success bool       `json:"success"`
	Tasks   []TaskInfo `json:"tasks"`
}

// ProgressEvent 进度事件
type ProgressEvent struct {
	Type        string `json:"type"`         // output, heartbeat, finished
	Line        string `json:"line,omitempty"`
	ReturnCode  *int   `json:"return_code,omitempty"`
	Progress    *int   `json:"progress,omitempty"`
	Total       *int   `json:"total,omitempty"`
	Percent     float64 `json:"percent,omitempty"`
	Message     string `json:"message,omitempty"`
}

// RedisProgressData Redis进度数据
type RedisProgressData struct {
	TaskID            string  `json:"task_id"`
	Status            string  `json:"status"`
	CurrentRound      int     `json:"current_round"`
	TotalRounds       int     `json:"total_rounds"`
	TotalSamples      int     `json:"total_samples"`
	GeneratedCount    int     `json:"generated_count"`
	CompletionPercent float64 `json:"completion_percent"`
	ProgressPercent   float64 `json:"progress_percent"`
	RoundStatus       string  `json:"round_status,omitempty"`
	StartTime         float64 `json:"start_time"`
	EndTime           float64 `json:"end_time,omitempty"`
	Duration          float64 `json:"duration,omitempty"`
}
