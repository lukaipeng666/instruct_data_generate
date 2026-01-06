package repository

import (
	"gen-go/internal/models"
	"time"

	"gorm.io/gorm"
)

// TaskRepository 任务数据访问层
type TaskRepository struct {
	db *gorm.DB
}

// NewTaskRepository 创建任务Repository
func NewTaskRepository(db *gorm.DB) *TaskRepository {
	return &TaskRepository{db: db}
}

// Create 创建任务
func (r *TaskRepository) Create(task *models.Task) error {
	return r.db.Create(task).Error
}

// GetByID 根据ID获取任务
func (r *TaskRepository) GetByID(id uint) (*models.Task, error) {
	var task models.Task
	err := r.db.Preload("User").First(&task, id).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// GetByTaskID 根据任务ID获取任务
func (r *TaskRepository) GetByTaskID(taskID string) (*models.Task, error) {
	var task models.Task
	err := r.db.Preload("User").Where("task_id = ?", taskID).First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// Update 更新任务
func (r *TaskRepository) Update(task *models.Task) error {
	return r.db.Save(task).Error
}

// UpdateStatus 更新任务状态
func (r *TaskRepository) UpdateStatus(taskID string, status string) error {
	return r.db.Model(&models.Task{}).Where("task_id = ?", taskID).Update("status", status).Error
}

// UpdateStatusWithTime 更新任务状态和完成时间
func (r *TaskRepository) UpdateStatusWithTime(taskID string, status string) error {
	updates := map[string]interface{}{
		"status": status,
	}

	if status == "finished" || status == "error" || status == "stopped" {
		updates["finished_at"] = time.Now()
	}

	return r.db.Model(&models.Task{}).Where("task_id = ?", taskID).Updates(updates).Error
}

// Delete 删除任务
func (r *TaskRepository) Delete(id uint) error {
	return r.db.Delete(&models.Task{}, id).Error
}

// DeleteByTaskID 根据任务ID删除任务
func (r *TaskRepository) DeleteByTaskID(taskID string) error {
	return r.db.Where("task_id = ?", taskID).Delete(&models.Task{}).Error
}

// List 获取任务列表
func (r *TaskRepository) List(offset, limit int) ([]models.Task, int64, error) {
	var tasks []models.Task
	var total int64

	if err := r.db.Model(&models.Task{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := r.db.Preload("User").Order("started_at DESC").Offset(offset).Limit(limit).Find(&tasks).Error
	return tasks, total, err
}

// ListByUserID 获取用户的任务列表
func (r *TaskRepository) ListByUserID(userID uint, offset, limit int) ([]models.Task, int64, error) {
	var tasks []models.Task
	var total int64

	query := r.db.Model(&models.Task{}).Where("user_id = ?", userID)
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	err := query.Preload("User").Order("started_at DESC").Offset(offset).Limit(limit).Find(&tasks).Error
	return tasks, total, err
}

// GetByUserID 获取用户的所有任务（指针版本）
func (r *TaskRepository) GetByUserID(userID uint) ([]*models.Task, error) {
	var tasks []*models.Task
	err := r.db.Where("user_id = ?", userID).Order("started_at DESC").Find(&tasks).Error
	return tasks, err
}

// GetActiveTasks 获取运行中的任务
func (r *TaskRepository) GetActiveTasks() ([]models.Task, error) {
	var tasks []models.Task
	err := r.db.Where("status = ?", "running").Find(&tasks).Error
	return tasks, err
}

// GetActiveTaskByUserID 获取用户的运行中任务
func (r *TaskRepository) GetActiveTaskByUserID(userID uint) (*models.Task, error) {
	var task models.Task
	err := r.db.Where("user_id = ? AND status = ?", userID, "running").First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// ExistsByTaskID 检查任务ID是否存在
func (r *TaskRepository) ExistsByTaskID(taskID string) (bool, error) {
	var count int64
	err := r.db.Model(&models.Task{}).Where("task_id = ?", taskID).Count(&count).Error
	return count > 0, err
}

// UpdateInputOutputChars 更新任务的输入输出字符数
func (r *TaskRepository) UpdateInputOutputChars(taskID string, inputChars, outputChars int64) error {
	return r.db.Model(&models.Task{}).Where("task_id = ?", taskID).Updates(map[string]interface{}{
		"input_chars":  inputChars,
		"output_chars": outputChars,
	}).Error
}

// UpdateStatusWithTimeAndChars 更新任务状态、完成时间和字符数
func (r *TaskRepository) UpdateStatusWithTimeAndChars(taskID string, status string, inputChars, outputChars int64) error {
	updates := map[string]interface{}{
		"status":      status,
		"input_chars":  inputChars,
		"output_chars": outputChars,
	}

	if status == "finished" || status == "error" || status == "stopped" {
		updates["finished_at"] = time.Now()
	}

	return r.db.Model(&models.Task{}).Where("task_id = ?", taskID).Updates(updates).Error
}
