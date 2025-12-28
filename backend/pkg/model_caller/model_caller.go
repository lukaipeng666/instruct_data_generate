package model_caller

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"gen-go/internal/dto"
)

// ModelCaller 模型调用客户端
type ModelCaller struct {
	client     *http.Client
	apiBase    string
	apiKey      string
	model      string
	timeout     time.Duration
	isVLLM      bool
}

// CallOptions 调用选项
type CallOptions struct {
	MaxTokens   int
	Temperature float64
	TopP        float64
}

// NewModelCaller 创建模型调用客户端
func NewModelCaller(apiBase, apiKey, model string, isVLLM bool, timeout time.Duration) *ModelCaller {
	return &ModelCaller{
		client: &http.Client{
			Timeout: timeout,
		},
		apiBase: apiBase,
		apiKey:   apiKey,
		model:    model,
		timeout:  timeout,
		isVLLM:   isVLLM,
	}
}

// Call 调用模型
func (mc *ModelCaller) Call(ctx context.Context, messages []dto.Message, options *CallOptions) (*dto.ModelCallResponse, error) {
	if options == nil {
		options = &CallOptions{
			MaxTokens:   2048,
			Temperature: 1.0,
			TopP:        1.0,
		}
	}

	// 构建请求体
	reqBody := map[string]interface{}{
		"model":    mc.model,
		"messages": messages,
	}

	if !mc.isVLLM {
		// OpenAI格式
		reqBody["max_tokens"] = options.MaxTokens
	} else {
		// vLLM格式
		reqBody["max_tokens"] = options.MaxTokens
	}

	reqBody["temperature"] = options.Temperature
	reqBody["top_p"] = options.TopP

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	// 构建HTTP请求
	url := mc.apiBase + "/chat/completions"
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %w", err)
	}

	// 设置请求头
	req.Header.Set("Content-Type", "application/json")
	if mc.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+mc.apiKey)
	}

	// 发送请求
	resp, err := mc.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("请求失败: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	// 检查HTTP状态码
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API返回错误: status=%d, body=%s", resp.StatusCode, string(body))
	}

	// 解析响应
	var result dto.ModelCallResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("解析响应失败: %w", err)
	}

	return &result, nil
}

// CallWithConcurrencyLimit 带并发限制的调用
func (mc *ModelCaller) CallWithConcurrencyLimit(ctx context.Context, limiter *ConcurrencyLimiter, key string, messages []dto.Message, options *CallOptions) (*dto.ModelCallResponse, error) {
	// 获取并发槽位
	if err := limiter.Acquire(ctx, key); err != nil {
		return nil, fmt.Errorf("获取并发槽位失败: %w", err)
	}
	defer limiter.Release(ctx, key)

	return mc.Call(ctx, messages, options)
}

// ConcurrencyLimiter 并发限制器
type ConcurrencyLimiter struct {
	maxConcurrent int
	semaphore     chan struct{}
}

// NewConcurrencyLimiter 创建并发限制器
func NewConcurrencyLimiter(maxConcurrent int) *ConcurrencyLimiter {
	return &ConcurrencyLimiter{
		maxConcurrent: maxConcurrent,
		semaphore:     make(chan struct{}, maxConcurrent),
	}
}

// Acquire 获取并发槽位
func (cl *ConcurrencyLimiter) Acquire(ctx context.Context, key string) error {
	select {
	case cl.semaphore <- struct{}{}:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Release 释放并发槽位
func (cl *ConcurrencyLimiter) Release(ctx context.Context, key string) {
	select {
	case <-cl.semaphore:
	default:
	}
}
