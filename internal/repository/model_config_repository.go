package repository

import (
	"gen-go/internal/models"

	"gorm.io/gorm"
)

// ModelConfigRepository 模型配置数据访问层
type ModelConfigRepository struct {
	db *gorm.DB
}

// NewModelConfigRepository 创建模型配置Repository
func NewModelConfigRepository(db *gorm.DB) *ModelConfigRepository {
	return &ModelConfigRepository{db: db}
}

// Create 创建模型配置
func (r *ModelConfigRepository) Create(config *models.ModelConfig) error {
	return r.db.Create(config).Error
}

// GetByID 根据ID获取模型配置
func (r *ModelConfigRepository) GetByID(id uint) (*models.ModelConfig, error) {
	var config models.ModelConfig
	err := r.db.First(&config, id).Error
	if err != nil {
		return nil, err
	}
	return &config, nil
}

// Update 更新模型配置
func (r *ModelConfigRepository) Update(config *models.ModelConfig) error {
	return r.db.Save(config).Error
}

// Delete 删除模型配置
func (r *ModelConfigRepository) Delete(id uint) error {
	return r.db.Delete(&models.ModelConfig{}, id).Error
}

// List 获取模型配置列表
func (r *ModelConfigRepository) List(offset, limit int) ([]models.ModelConfig, int64, error) {
	var configs []models.ModelConfig
	var total int64

	if err := r.db.Model(&models.ModelConfig{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := r.db.Order("created_at DESC").Offset(offset).Limit(limit).Find(&configs).Error
	return configs, total, err
}

// GetActiveModels 获取启用的模型列表
func (r *ModelConfigRepository) GetActiveModels() ([]models.ModelConfig, error) {
	var configs []models.ModelConfig
	err := r.db.Where("is_active = ?", true).Find(&configs).Error
	return configs, err
}

// GetByIDAndActive 根据ID获取启用的模型
func (r *ModelConfigRepository) GetByIDAndActive(id uint) (*models.ModelConfig, error) {
	var config models.ModelConfig
	err := r.db.Where("id = ? AND is_active = ?", id, true).First(&config).Error
	if err != nil {
		return nil, err
	}
	return &config, nil
}
