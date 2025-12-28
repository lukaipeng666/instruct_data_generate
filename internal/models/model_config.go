package models

import (
	"time"
)

// ModelConfig 模型配置
type ModelConfig struct {
	ID            uint      `gorm:"primarykey" json:"id"`
	Name          string    `gorm:"uniqueIndex;size:100;not null" json:"name"`
	APIURL        string    `gorm:"size:255;not null" json:"api_url"`
	APIKey        string    `gorm:"size:255;default:'sk-xxxxx'" json:"api_key"`
	ModelPath     string    `gorm:"size:500;not null" json:"model_path"`
	MaxConcurrent int       `gorm:"default:16" json:"max_concurrent"`
	Temperature   float64   `gorm:"default:1.0" json:"temperature"`
	TopP          float64   `gorm:"default:1.0" json:"top_p"`
	MaxTokens     int       `gorm:"default:2048" json:"max_tokens"`
	IsVLLM        bool      `gorm:"default:true" json:"is_vllm"`
	Timeout       int       `gorm:"default:600" json:"timeout"`
	Description   string    `gorm:"type:text" json:"description"`
	IsActive      bool      `gorm:"default:true" json:"is_active"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// TableName 指定表名
func (ModelConfig) TableName() string {
	return "model_configs"
}
