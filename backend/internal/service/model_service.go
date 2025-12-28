package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"
	"gen-go/pkg/redis_limiter"

	"github.com/go-redis/redis/v8"
)

// ModelService 模型服务
type ModelService struct {
	modelRepo   *repository.ModelConfigRepository
	redisClient *redis.Client
	// 并发限制器映射，每个模型一个限制器
	concurrencyLimiters map[string]*redis_limiter.RedisLimiter
	limitersMu          sync.RWMutex
}

// NewModelService 创建模型服务
func NewModelService(modelRepo *repository.ModelConfigRepository, redisClient *redis.Client) *ModelService {
	s := &ModelService{
		modelRepo:           modelRepo,
		redisClient:         redisClient,
		concurrencyLimiters: make(map[string]*redis_limiter.RedisLimiter),
	}
	return s
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
	// 根据模型名称查找模型配置以获取最大并发数
	modelConfig, err := s.getModelConfigByName(req.Model)
	if err != nil {
		log.Printf("[CallModel] 获取模型配置失败: %v", err)
		// 如果获取失败，使用默认并发数
		modelConfig = &models.ModelConfig{MaxConcurrent: 10} // 默认值
	}

	// 获取或创建Redis并发限制器
	limiter := s.getOrCreateLimiter(req.Model, modelConfig.MaxConcurrent)

	// 获取并发槽位
	ctx := context.Background()
	if err := limiter.Acquire(ctx, req.Model); err != nil {
		log.Printf("[CallModel] 获取并发槽位失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("获取并发槽位失败: %v", err),
		}, nil
	}
	defer limiter.Release(ctx, req.Model)

	// 构建消息
	messages := make([]dto.Message, len(req.Messages))
	for i, msg := range req.Messages {
		messages[i] = dto.Message{
			Role:    msg.Role,
			Content: msg.Content,
		}
	}

	// 构建请求体
	reqBody := map[string]interface{}{
		"model":    req.Model,
		"messages": messages,
	}

	if !req.IsVLLM {
		// OpenAI格式
		reqBody["max_tokens"] = req.MaxTokens
	} else {
		// vLLM格式
		reqBody["max_tokens"] = req.MaxTokens
	}

	reqBody["temperature"] = req.Temperature
	reqBody["top_p"] = req.TopP

	// 转换请求体为JSON
	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		log.Printf("[CallModel] 序列化请求失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("序列化请求失败: %v", err),
		}, nil
	}

	// 构建HTTP请求
	url := req.APIUrl + "/chat/completions"
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonBody))
	if err != nil {
		log.Printf("[CallModel] 创建请求失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("创建请求失败: %v", err),
		}, nil
	}

	// 设置请求头
	httpReq.Header.Set("Content-Type", "application/json")
	if req.APIKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	}

	// 创建HTTP客户端
	client := &http.Client{
		Timeout: time.Duration(req.Timeout) * time.Second,
	}

	// 发送请求
	resp, err := client.Do(httpReq)
	if err != nil {
		log.Printf("[CallModel] 请求失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("请求失败: %v", err),
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

	// 检查HTTP状态码
	if resp.StatusCode != http.StatusOK {
		log.Printf("[CallModel] API返回错误: status=%d, body=%s", resp.StatusCode, string(body))
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("API返回错误: status=%d, body=%s", resp.StatusCode, string(body)),
		}, nil
	}

	// 解析响应
	var result dto.ModelCallResponse
	if err := json.Unmarshal(body, &result); err != nil {
		log.Printf("[CallModel] 解析响应失败: %v", err)
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   fmt.Sprintf("解析响应失败: %v", err),
		}, nil
	}

	// 提取内容
	if len(result.Choices) == 0 {
		return &dto.ModelCallProxyResponse{
			Success: false,
			Error:   "API返回空响应",
		}, nil
	}

	content := result.Choices[0].Message.Content

	return &dto.ModelCallProxyResponse{
		Success: true,
		Content: content,
	}, nil
}

// getOrCreateLimiter 获取或创建并发限制器
func (s *ModelService) getOrCreateLimiter(modelKey string, maxConcurrent int) *redis_limiter.RedisLimiter {
	s.limitersMu.Lock()
	defer s.limitersMu.Unlock()

	// 检查是否已存在限制器
	if limiter, exists := s.concurrencyLimiters[modelKey]; exists {
		// 检查当前限制器的最大并发数是否与配置一致
		if limiter.GetMaxConcurrent() == maxConcurrent {
			return limiter
		}
		// 如果配置发生变化，创建新的限制器
	}

	// 创建新的Redis限制器
	limiter := redis_limiter.NewRedisLimiter(s.redisClient, maxConcurrent, "model_concurrent:", time.Duration(300)*time.Second)

	// 记录创建的限制器信息
	log.Printf("[RedisLimiter] 创建新的限制器, 模型: %s, 最大并发数: %d", modelKey, maxConcurrent)

	s.concurrencyLimiters[modelKey] = limiter
	return limiter
}

// getModelConfigByName 根据模型名称查找模型配置
func (s *ModelService) getModelConfigByName(modelName string) (*models.ModelConfig, error) {
	// 通过模型名称查询模型配置，这里使用ModelPath字段匹配
	modelConfig, err := s.modelRepo.GetByModelPathOrName(modelName)
	if err != nil {
		return nil, err
	}
	return modelConfig, nil
}
