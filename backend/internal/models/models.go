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
		Logger: logger.Default.LogMode(logger.Silent), // 使用静默模式
		DisableForeignKeyConstraintWhenMigrating: true,
	})
	if err != nil {
		return err
	}

	// 不进行自动迁移,直接使用现有数据库表结构
	// AutoMigrate() // 注释掉自动迁移

	return nil
}

// AutoMigrate 自动迁移数据库表(仅在新数据库时使用)
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
