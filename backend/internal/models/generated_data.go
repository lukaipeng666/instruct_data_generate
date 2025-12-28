package models

import (
	"time"
)

// GeneratedData 生成数据模型
type GeneratedData struct {
	ID              uint      `gorm:"primarykey" json:"id"`
	TaskID          string    `gorm:"size:100;not null;index" json:"task_id"`
	UserID          uint      `gorm:"not null;index" json:"user_id"`
	DataContent     string    `gorm:"type:text;not null" json:"data_content"`
	ModelScore      *float64  `json:"model_score"`
	RuleScore       *int      `json:"rule_score"`
	RetryCount      int       `gorm:"default:0" json:"retry_count"`
	GenerationModel string    `gorm:"size:255" json:"generation_model"`
	TaskType        string    `gorm:"size:50" json:"task_type"`
	IsConfirmed     bool      `gorm:"default:false" json:"is_confirmed"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`

	// 关联
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
	Task Task `gorm:"foreignKey:TaskID;references:TaskID" json:"task,omitempty"`
}

// TableName 指定表名
func (GeneratedData) TableName() string {
	return "generated_data"
}
