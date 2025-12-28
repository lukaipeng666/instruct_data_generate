package models

import (
	"time"
)

// DataFile 数据文件模型
type DataFile struct {
	ID          uint      `gorm:"primarykey" json:"id"`
	Filename    string    `gorm:"size:255;not null" json:"filename"`
	FileContent []byte    `gorm:"type:blob;not null" json:"-"`
	FileSize    int       `gorm:"not null" json:"file_size"`
	ContentType string    `gorm:"size:100;default:'application/x-jsonlines'" json:"content_type"`
	UserID      uint      `gorm:"not null;index" json:"user_id"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`

	// 关联
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

// TableName 指定表名
func (DataFile) TableName() string {
	return "data_files"
}
