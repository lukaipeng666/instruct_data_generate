package repository

import (
	"gen-go/internal/models"

	"gorm.io/gorm"
)

// DataFileRepository 数据文件数据访问层
type DataFileRepository struct {
	db *gorm.DB
}

// NewDataFileRepository 创建数据文件Repository
func NewDataFileRepository(db *gorm.DB) *DataFileRepository {
	return &DataFileRepository{db: db}
}

// Create 创建文件
func (r *DataFileRepository) Create(file *models.DataFile) error {
	return r.db.Create(file).Error
}

// GetByID 根据ID获取文件
func (r *DataFileRepository) GetByID(id uint) (*models.DataFile, error) {
	var file models.DataFile
	err := r.db.Preload("User").First(&file, id).Error
	if err != nil {
		return nil, err
	}
	return &file, nil
}

// GetByIDAndUserID 根据ID和用户ID获取文件
func (r *DataFileRepository) GetByIDAndUserID(id uint, userID uint) (*models.DataFile, error) {
	var file models.DataFile
	err := r.db.Where("id = ? AND user_id = ?", id, userID).First(&file).Error
	if err != nil {
		return nil, err
	}
	return &file, nil
}

// Update 更新文件
func (r *DataFileRepository) Update(file *models.DataFile) error {
	return r.db.Save(file).Error
}

// Delete 删除文件
func (r *DataFileRepository) Delete(id uint) error {
	return r.db.Delete(&models.DataFile{}, id).Error
}

// DeleteByIDs 批量删除文件
func (r *DataFileRepository) DeleteByIDs(ids []uint) error {
	return r.db.Delete(&models.DataFile{}, ids).Error
}

// List 获取文件列表
func (r *DataFileRepository) List(offset, limit int) ([]models.DataFile, int64, error) {
	var files []models.DataFile
	var total int64

	if err := r.db.Model(&models.DataFile{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := r.db.Preload("User").Order("created_at DESC").Offset(offset).Limit(limit).Find(&files).Error
	return files, total, err
}

// ListByUserID 获取用户的文件列表
func (r *DataFileRepository) ListByUserID(userID uint, offset, limit int) ([]models.DataFile, int64, error) {
	var files []models.DataFile
	var total int64

	query := r.db.Model(&models.DataFile{}).Where("user_id = ?", userID)
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := query.Order("created_at DESC").Offset(offset).Limit(limit).Find(&files).Error
	return files, total, err
}

// GetByIDs 根据ID列表获取文件
func (r *DataFileRepository) GetByIDs(ids []uint) ([]models.DataFile, error) {
	var files []models.DataFile
	err := r.db.Where("id IN ?", ids).Find(&files).Error
	return files, err
}
