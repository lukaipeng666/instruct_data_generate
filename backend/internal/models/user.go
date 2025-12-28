package models

import (
	"time"
)

// User 用户模型
type User struct {
	ID           uint      `gorm:"primarykey" json:"id"`
	Username     string    `gorm:"uniqueIndex;size:50;not null" json:"username"`
	PasswordHash string    `gorm:"size:255;not null" json:"-"`
	IsActive     bool      `gorm:"default:true" json:"is_active"`
	IsAdmin      bool      `gorm:"default:false" json:"is_admin"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`

	// 关联
	Tasks         []Task         `gorm:"foreignKey:UserID;constraint:OnDelete:CASCADE" json:"tasks,omitempty"`
	DataFiles     []DataFile     `gorm:"foreignKey:UserID;constraint:OnDelete:CASCADE" json:"data_files,omitempty"`
	GeneratedData []GeneratedData `gorm:"foreignKey:UserID" json:"generated_data,omitempty"`
}

// TableName 指定表名
func (User) TableName() string {
	return "users"
}
