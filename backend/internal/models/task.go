package models

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

// Task 任务模型
type Task struct {
	ID           uint       `gorm:"primarykey" json:"id"`
	TaskID       string     `gorm:"uniqueIndex;size:100;not null" json:"task_id"`
	UserID       uint       `gorm:"not null;index" json:"user_id"`
	Status       string     `gorm:"size:20;default:'running'" json:"status"` // running, finished, error, stopped
	Params       JSONMap    `gorm:"type:text" json:"params"`
	Result       JSONMap    `gorm:"type:text" json:"result"`
	ErrorMessage string     `gorm:"type:text" json:"error_message"`
	StartedAt    time.Time  `json:"started_at"`
	FinishedAt   *time.Time `json:"finished_at"`
	InputChars   int64      `gorm:"default:0" json:"input_chars"`  // 输入字符总数
	OutputChars  int64      `gorm:"default:0" json:"output_chars"` // 输出字符总数

	// 关联
	User          User            `gorm:"foreignKey:UserID" json:"user,omitempty"`
	GeneratedData []GeneratedData `gorm:"foreignKey:TaskID;references:TaskID" json:"generated_data,omitempty"`
}

// TableName 指定表名
func (Task) TableName() string {
	return "tasks"
}

// JSONMap 自定义JSON类型
type JSONMap map[string]interface{}

// Scan 实现sql.Scanner接口
func (j *JSONMap) Scan(value interface{}) error {
	if value == nil {
		*j = make(JSONMap)
		return nil
	}

	bytes, ok := value.([]byte)
	if !ok {
		return nil
	}

	return json.Unmarshal(bytes, j)
}

// Value 实现driver.Valuer接口
func (j JSONMap) Value() (driver.Value, error) {
	if len(j) == 0 {
		return nil, nil
	}
	return json.Marshal(j)
}
