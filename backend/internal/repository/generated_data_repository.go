package repository

import (
	"gen-go/internal/models"

	"gorm.io/gorm"
)

// GeneratedDataRepository 生成数据数据访问层
type GeneratedDataRepository struct {
	db *gorm.DB
}

// NewGeneratedDataRepository 创建生成数据Repository
func NewGeneratedDataRepository(db *gorm.DB) *GeneratedDataRepository {
	return &GeneratedDataRepository{db: db}
}

// Create 创建数据
func (r *GeneratedDataRepository) Create(data *models.GeneratedData) error {
	return r.db.Create(data).Error
}

// CreateBatch 批量创建数据
func (r *GeneratedDataRepository) CreateBatch(dataList []models.GeneratedData) error {
	if len(dataList) == 0 {
		return nil
	}
	return r.db.Create(&dataList).Error
}

// GetByID 根据ID获取数据
func (r *GeneratedDataRepository) GetByID(id uint) (*models.GeneratedData, error) {
	var data models.GeneratedData
	err := r.db.Preload("User").Preload("Task").First(&data, id).Error
	if err != nil {
		return nil, err
	}
	return &data, nil
}

// Update 更新数据
func (r *GeneratedDataRepository) Update(data *models.GeneratedData) error {
	return r.db.Save(data).Error
}

// UpdateBatch 批量更新数据
func (r *GeneratedDataRepository) UpdateBatch(dataList []models.GeneratedData) error {
	if len(dataList) == 0 {
		return nil
	}
	return r.db.Save(&dataList).Error
}

// Delete 删除数据
func (r *GeneratedDataRepository) Delete(id uint) error {
	return r.db.Delete(&models.GeneratedData{}, id).Error
}

// DeleteByIDs 批量删除数据
func (r *GeneratedDataRepository) DeleteByIDs(ids []uint) error {
	return r.db.Delete(&models.GeneratedData{}, ids).Error
}

// DeleteByTaskID 根据任务ID删除数据
func (r *GeneratedDataRepository) DeleteByTaskID(taskID string) error {
	return r.db.Where("task_id = ?", taskID).Delete(&models.GeneratedData{}).Error
}

// List 获取数据列表
func (r *GeneratedDataRepository) List(offset, limit int) ([]models.GeneratedData, int64, error) {
	var dataList []models.GeneratedData
	var total int64

	if err := r.db.Model(&models.GeneratedData{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := r.db.Preload("User").Order("created_at DESC").Offset(offset).Limit(limit).Find(&dataList).Error
	return dataList, total, err
}

// ListByUserID 获取用户的数据列表
func (r *GeneratedDataRepository) ListByUserID(userID uint, offset, limit int) ([]models.GeneratedData, int64, error) {
	var dataList []models.GeneratedData
	var total int64

	query := r.db.Model(&models.GeneratedData{}).Where("user_id = ?", userID)
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := query.Preload("Task").Order("created_at DESC").Offset(offset).Limit(limit).Find(&dataList).Error
	return dataList, total, err
}

// ListByTaskID 获取任务的数据列表
func (r *GeneratedDataRepository) ListByTaskID(taskID string, offset, limit int) ([]models.GeneratedData, int64, error) {
	var dataList []models.GeneratedData
	var total int64

	query := r.db.Model(&models.GeneratedData{}).Where("task_id = ?", taskID)
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := query.Order("created_at DESC").Offset(offset).Limit(limit).Find(&dataList).Error
	return dataList, total, err
}

// ListByIDs 根据ID列表获取数据
func (r *GeneratedDataRepository) ListByIDs(ids []uint) ([]models.GeneratedData, error) {
	var dataList []models.GeneratedData
	err := r.db.Where("id IN ?", ids).Find(&dataList).Error
	return dataList, err
}

// GetUnconfirmedCount 获取未确认数据数量
func (r *GeneratedDataRepository) GetUnconfirmedCount(taskID string) (int64, error) {
	var count int64
	err := r.db.Model(&models.GeneratedData{}).Where("task_id = ? AND is_confirmed = ?", taskID, false).Count(&count).Error
	return count, err
}

// ConfirmBatch 批量确认数据
func (r *GeneratedDataRepository) ConfirmBatch(ids []uint) error {
	return r.db.Model(&models.GeneratedData{}).Where("id IN ?", ids).Update("is_confirmed", true).Error
}
