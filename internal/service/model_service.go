package service

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"
)

// ModelService 模型服务
type ModelService struct {
	modelRepo *repository.ModelConfigRepository
}

// NewModelService 创建模型服务
func NewModelService(modelRepo *repository.ModelConfigRepository) *ModelService {
	return &ModelService{
		modelRepo: modelRepo,
	}
}

// GetActiveModels 获取激活的模型列表
func (s *ModelService) GetActiveModels() ([]dto.ModelConfigResponse, error) {
	models, err := s.modelRepo.GetActiveModels()
	if err != nil {
		return nil, err
	}

	responses := make([]dto.ModelConfigResponse, len(models))
	for i, model := range models {
		responses[i] = dto.ModelConfigResponse{
			ID:            model.ID,
			Name:          model.Name,
			APIURL:        model.APIURL,
			APIKey:        model.APIKey,
			ModelPath:     model.ModelPath,
			MaxConcurrent: model.MaxConcurrent,
			Temperature:   model.Temperature,
			TopP:          model.TopP,
			MaxTokens:     model.MaxTokens,
			IsVLLM:        model.IsVLLM,
			Timeout:       model.Timeout,
			Description:   model.Description,
			IsActive:      model.IsActive,
			CreatedAt:     model.CreatedAt.Format("2006-01-02 15:04:05"),
			UpdatedAt:     model.UpdatedAt.Format("2006-01-02 15:04:05"),
		}
	}

	return responses, nil
}

// GetAllModels 获取所有模型(管理员)
func (s *ModelService) GetAllModels(page, perPage int) (*dto.PaginatedResponse, error) {
	offset := (page - 1) * perPage
	models, total, err := s.modelRepo.List(offset, perPage)
	if err != nil {
		return nil, err
	}

	responses := make([]dto.ModelConfigResponse, len(models))
	for i, model := range models {
		responses[i] = dto.ModelConfigResponse{
			ID:            model.ID,
			Name:          model.Name,
			APIURL:        model.APIURL,
			APIKey:        model.APIKey,
			ModelPath:     model.ModelPath,
			MaxConcurrent: model.MaxConcurrent,
			Temperature:   model.Temperature,
			TopP:          model.TopP,
			MaxTokens:     model.MaxTokens,
			IsVLLM:        model.IsVLLM,
			Timeout:       model.Timeout,
			Description:   model.Description,
			IsActive:      model.IsActive,
			CreatedAt:     model.CreatedAt.Format("2006-01-02 15:04:05"),
			UpdatedAt:     model.UpdatedAt.Format("2006-01-02 15:04:05"),
		}
	}

	return &dto.PaginatedResponse{
		Items:   responses,
		Total:   total,
		Page:    page,
		PerPage: perPage,
	}, nil
}

// GetModelByID 获取模型详情
func (s *ModelService) GetModelByID(id uint) (*models.ModelConfig, error) {
	return s.modelRepo.GetByID(id)
}

// CreateModel 创建模型
func (s *ModelService) CreateModel(req *dto.CreateModelConfigRequest) (*models.ModelConfig, error) {
	model := &models.ModelConfig{
		Name:          req.Name,
		APIURL:        req.APIURL,
		APIKey:        req.APIKey,
		ModelPath:     req.ModelPath,
		MaxConcurrent: req.MaxConcurrent,
		Temperature:   req.Temperature,
		TopP:          req.TopP,
		MaxTokens:     req.MaxTokens,
		IsVLLM:        req.IsVLLM,
		Timeout:       req.Timeout,
		Description:   req.Description,
		IsActive:      req.IsActive,
	}

	if err := s.modelRepo.Create(model); err != nil {
		return nil, err
	}

	return model, nil
}

// UpdateModel 更新模型
func (s *ModelService) UpdateModel(id uint, req *dto.UpdateModelConfigRequest) error {
	model, err := s.modelRepo.GetByID(id)
	if err != nil {
		return err
	}

	if req.Name != nil {
		model.Name = *req.Name
	}
	if req.APIURL != nil {
		model.APIURL = *req.APIURL
	}
	if req.APIKey != nil {
		model.APIKey = *req.APIKey
	}
	if req.ModelPath != nil {
		model.ModelPath = *req.ModelPath
	}
	if req.MaxConcurrent != nil {
		model.MaxConcurrent = *req.MaxConcurrent
	}
	if req.Temperature != nil {
		model.Temperature = *req.Temperature
	}
	if req.TopP != nil {
		model.TopP = *req.TopP
	}
	if req.MaxTokens != nil {
		model.MaxTokens = *req.MaxTokens
	}
	if req.IsVLLM != nil {
		model.IsVLLM = *req.IsVLLM
	}
	if req.Timeout != nil {
		model.Timeout = *req.Timeout
	}
	if req.Description != nil {
		model.Description = *req.Description
	}
	if req.IsActive != nil {
		model.IsActive = *req.IsActive
	}

	return s.modelRepo.Update(model)
}

// DeleteModel 删除模型
func (s *ModelService) DeleteModel(id uint) error {
	return s.modelRepo.Delete(id)
}

// CallModel 调用模型API（代理模式）
func (s *ModelService) CallModel(req *dto.ModelCallProxyRequest) (*dto.ModelCallProxyResponse, error) {
	log.Printf("[CallModel] 收到模型调用请求: API=%s, Model=%s", req.APIUrl, req.Model)

	// 构建vLLM API请求
	vllmReq := dto.VLLMRequest{
		Model:       req.Model,
		Messages:    req.Messages,
		Temperature: req.Temperature,
		MaxTokens:   req.MaxTokens,
		TopP:        req.TopP,
	}

	// 序列化请求体
	reqBody, err := json.Marshal(vllmReq)
	if err != nil {
		log.Printf("[CallModel] 序列化请求失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("序列化请求失败: %v", err),
		}, nil
	}

	// 构建API URL
	apiURL := req.APIUrl

	// 智能拼接路径，处理各种可能的输入格式
	// 可能的输入：
	// - http://localhost:58066/v1
	// - http://localhost:58066/v1/
	// - http://localhost:58066
	// - http://localhost:58066/

	// 标准化：确保末尾有斜杠
	if len(apiURL) > 0 && apiURL[len(apiURL)-1] != '/' {
		apiURL += "/"
	}

	// 检查是否已经包含 /v1/ 或以 /v1 结尾
	if strings.Contains(apiURL, "/v1/") || (len(apiURL) >= 4 && apiURL[len(apiURL)-4:] == "/v1/") {
		// 已经包含/v1，只需要添加 chat/completions
		apiURL += "chat/completions"
	} else if len(apiURL) >= 3 && apiURL[len(apiURL)-3:] == "v1/" {
		// 以 v1/ 结尾
		apiURL += "chat/completions"
	} else if len(apiURL) >= 3 && apiURL[len(apiURL)-3:] == "/v1" {
		// 以 /v1 结尾（加斜杠后）
		apiURL += "/chat/completions"
	} else {
		// 不包含/v1，需要添加完整路径
		apiURL += "v1/chat/completions"
	}

	log.Printf("[CallModel] 调用API: %s", apiURL)

	// 创建HTTP请求
	timeout := time.Duration(req.Timeout) * time.Second
	if timeout <= 0 {
		timeout = 300 * time.Second // 默认5分钟
	}

	client := &http.Client{
		Timeout: timeout,
	}

	httpReq, err := http.NewRequest("POST", apiURL, bytes.NewBuffer(reqBody))
	if err != nil {
		log.Printf("[CallModel] 创建请求失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("创建请求失败: %v", err),
		}, nil
	}

	// 设置请求头
	httpReq.Header.Set("Content-Type", "application/json")
	if req.APIKey != "" && req.APIKey != "sk-xxxxx" {
		httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	}

	// 发送请求
	resp, err := client.Do(httpReq)
	if err != nil {
		log.Printf("[CallModel] API调用失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("API调用失败: %v", err),
		}, nil
	}
	defer resp.Body.Close()

	// 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[CallModel] 读取响应失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("读取响应失败: %v", err),
		}, nil
	}

	log.Printf("[CallModel] API响应状态: %d, Body长度: %d", resp.StatusCode, len(body))

	// 检查HTTP状态码
	if resp.StatusCode != http.StatusOK {
		log.Printf("[CallModel] API返回错误状态: %d, Body: %s", resp.StatusCode, string(body))
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("API返回错误: status=%d, body=%s", resp.StatusCode, string(body)),
		}, nil
	}

	// 解析vLLM响应
	var vllmResp dto.VLLMResponse
	if err := json.Unmarshal(body, &vllmResp); err != nil {
		log.Printf("[CallModel] 解析响应失败: %v, Body: %s", err, string(body))
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("解析响应失败: %v", err),
		}, nil
	}

	// 提取生成的内容
	if len(vllmResp.Choices) == 0 {
		log.Printf("[CallModel] API返回空choices")
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   "API返回空响应",
		}, nil
	}

	content := vllmResp.Choices[0].Message.Content
	log.Printf("[CallModel] 调用成功，内容长度: %d", len(content))

	return &dto.ModelCallProxyResponse{
		Success: true,
		Content: content,
	}, nil
}
