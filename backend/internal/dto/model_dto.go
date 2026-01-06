package dto

// CreateModelConfigRequest 创建模型配置请求
type CreateModelConfigRequest struct {
	Name          string  `json:"name" binding:"required"`
	APIURL        string  `json:"api_url" binding:"required"`
	APIKey        string  `json:"api_key"`
	ModelPath     string  `json:"model_path" binding:"required"`
	MaxConcurrent int     `json:"max_concurrent"`
	Temperature   float64 `json:"temperature"`
	TopP          float64 `json:"top_p"`
	MaxTokens     int     `json:"max_tokens"`
	IsVLLM        bool    `json:"is_vllm"`
	Timeout       int     `json:"timeout"`
	Description   string  `json:"description"`
	IsActive      bool    `json:"is_active"`
}

// UpdateModelConfigRequest 更新模型配置请求
type UpdateModelConfigRequest struct {
	Name          *string  `json:"name"`
	APIURL        *string  `json:"api_url"`
	APIKey        *string  `json:"api_key"`
	ModelPath     *string  `json:"model_path"`
	MaxConcurrent *int     `json:"max_concurrent"`
	Temperature   *float64 `json:"temperature"`
	TopP          *float64 `json:"top_p"`
	MaxTokens     *int     `json:"max_tokens"`
	IsVLLM        *bool    `json:"is_vllm"`
	Timeout       *int     `json:"timeout"`
	Description   *string  `json:"description"`
	IsActive      *bool    `json:"is_active"`
}

// ModelConfigResponse 模型配置响应
type ModelConfigResponse struct {
	ID            uint    `json:"id"`
	Name          string  `json:"name"`
	APIURL        string  `json:"api_url"`
	APIKey        string  `json:"api_key"`
	ModelPath     string  `json:"model_path"`
	MaxConcurrent int     `json:"max_concurrent"`
	Temperature   float64 `json:"temperature"`
	TopP          float64 `json:"top_p"`
	MaxTokens     int     `json:"max_tokens"`
	IsVLLM        bool    `json:"is_vllm"`
	Timeout       int     `json:"timeout"`
	Description   string  `json:"description"`
	IsActive      bool    `json:"is_active"`
	CreatedAt     string  `json:"created_at"`
	UpdatedAt     string  `json:"updated_at"`
}

// ModelCallRequest 模型调用请求
type ModelCallRequest struct {
	Messages    []Message `json:"messages" binding:"required"`
	MaxTokens   int       `json:"max_tokens"`
	Temperature float64   `json:"temperature"`
	TopP        float64   `json:"top_p"`
}

// Message 消息
type Message struct {
	Role    string `json:"role" binding:"required,oneof=system user assistant"`
	Content string `json:"content" binding:"required"`
}

// ModelCallResponse 模型调用响应
type ModelCallResponse struct {
	Choices []Choice `json:"choices"`
	Usage   Usage    `json:"usage,omitempty"`
}

// Choice 选择
type Choice struct {
	Message      Message `json:"message"`
	FinishReason string  `json:"finish_reason,omitempty"`
}

// Usage 使用量
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// ModelCallProxyRequest 模型调用代理请求（Python后端调用Go）
type ModelCallProxyRequest struct {
	APIUrl      string    `json:"api_url" binding:"required"`
	APIKey      string    `json:"api_key"`
	Messages    []Message `json:"messages" binding:"required"`
	Model       string    `json:"model" binding:"required"`
	Temperature float64   `json:"temperature"`
	MaxTokens   int       `json:"max_tokens"`
	Timeout     int       `json:"timeout"`
	IsVLLM      bool      `json:"is_vllm"`
	TopP        float64   `json:"top_p"`
	RetryTimes  int       `json:"retry_times"`
	TaskID      string    `json:"task_id,omitempty"`
}

// ModelCallProxyResponse 模型调用代理响应（返回给Python后端）
type ModelCallProxyResponse struct {
	Success     bool   `json:"success"`
	Content     string `json:"content,omitempty"`
	Error       string `json:"error,omitempty"`
	InputChars  int    `json:"input_chars,omitempty"`
	OutputChars int    `json:"output_chars,omitempty"`
}

// VLLMRequest vLLM API请求格式
type VLLMRequest struct {
	Model       string    `json:"model"`
	Messages    []Message `json:"messages"`
	Temperature float64   `json:"temperature,omitempty"`
	MaxTokens   int       `json:"max_tokens,omitempty"`
	TopP        float64   `json:"top_p,omitempty"`
}

// VLLMResponse vLLM API响应格式
type VLLMResponse struct {
	Choices []Choice `json:"choices"`
	Usage   Usage    `json:"usage,omitempty"`
}
