package models

import (
	"gen-go/internal/config"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// DB 全局数据库实例
var DB *gorm.DB

// InitDB 初始化数据库
func InitDB(cfg *config.Config) error {
	var err error

	// 配置GORM
	DB, err = gorm.Open(sqlite.Open(cfg.Database.Path), &gorm.Config{
		Logger:                                   logger.Default.LogMode(logger.Silent), // 使用静默模式
		DisableForeignKeyConstraintWhenMigrating: true,
	})
	if err != nil {
		return err
	}

	// 自动迁移数据库表结构
	if err := AutoMigrate(); err != nil {
		return err
	}

	return nil
}

// AutoMigrate 自动迁移数据库表
func AutoMigrate() error {
	return DB.AutoMigrate(
		&User{},
		&ModelConfig{},
		&Task{},
		&DataFile{},
		&GeneratedData{},
	)
}

// GetDB 获取数据库实例
func GetDB() *gorm.DB {
	return DB
}
