package service

import (
	"errors"
	"fmt"

	"gen-go/internal/config"
	"gen-go/internal/dto"
	"gen-go/internal/models"
	"gen-go/internal/repository"
	"gen-go/internal/utils"
)

// AuthService 认证服务
type AuthService struct {
	userRepo   *repository.UserRepository
	jwtManager *utils.JWTManager
	cfg        *config.Config
}

// NewAuthService 创建认证服务
func NewAuthService(userRepo *repository.UserRepository, jwtManager *utils.JWTManager, cfg *config.Config) *AuthService {
	return &AuthService{
		userRepo:   userRepo,
		jwtManager: jwtManager,
		cfg:        cfg,
	}
}

// Register 用户注册
func (s *AuthService) Register(req *dto.RegisterRequest) (*models.User, error) {
	// 验证用户名是否已存在
	exists, err := s.userRepo.ExistsByUsername(req.Username)
	if err != nil {
		return nil, fmt.Errorf("检查用户名失败: %w", err)
	}
	if exists {
		return nil, errors.New("用户名已存在")
	}

	// 哈希密码
	hashedPassword, err := utils.HashPassword(req.Password)
	if err != nil {
		return nil, fmt.Errorf("密码哈希失败: %w", err)
	}

	// 创建用户
	user := &models.User{
		Username:     req.Username,
		PasswordHash: hashedPassword,
		IsActive:     true,
		IsAdmin:      false,
	}

	if err := s.userRepo.Create(user); err != nil {
		return nil, fmt.Errorf("创建用户失败: %w", err)
	}

	return user, nil
}

// Login 用户登录
func (s *AuthService) Login(req *dto.LoginRequest) (*dto.LoginResponse, error) {
	// 获取用户
	user, err := s.userRepo.GetByUsername(req.Username)
	if err != nil {
		return nil, errors.New("用户名或密码错误")
	}

	// 验证密码
	if err := utils.CheckPassword(req.Password, user.PasswordHash); err != nil {
		return nil, errors.New("用户名或密码错误")
	}

	// 检查用户是否激活
	if !user.IsActive {
		return nil, errors.New("用户已被禁用")
	}

	// 生成Token
	token, err := s.jwtManager.GenerateToken(user.ID, user.Username, user.IsAdmin)
	if err != nil {
		return nil, fmt.Errorf("生成Token失败: %w", err)
	}

	return &dto.LoginResponse{
		AccessToken: token,
		TokenType:   "bearer",
		User: dto.UserInfo{
			ID:       user.ID,
			Username: user.Username,
			IsActive: user.IsActive,
			IsAdmin:  user.IsAdmin,
		},
	}, nil
}

// GetMe 获取当前用户信息
func (s *AuthService) GetMe(userID uint) (*dto.UserInfo, error) {
	user, err := s.userRepo.GetByID(userID)
	if err != nil {
		return nil, errors.New("用户不存在")
	}

	return &dto.UserInfo{
		ID:       user.ID,
		Username: user.Username,
		IsActive: user.IsActive,
		IsAdmin:  user.IsAdmin,
	}, nil
}

// InitAdmin 初始化管理员账户
func (s *AuthService) InitAdmin() error {
	// 检查是否已有管理员
	admin, err := s.userRepo.GetAdmin()
	if err == nil && admin != nil {
		return nil // 已存在管理员
	}

	// 检查密码是否已经是bcrypt哈希格式(以$2a$或$2b$开头)
	passwordHash := s.cfg.Admin.Password
	if len(passwordHash) < 4 || (passwordHash[:4] != "$2a$" && passwordHash[:4] != "$2b$") {
		// 密码不是bcrypt哈希格式,需要哈希
		hashedPassword, err := utils.HashPassword(s.cfg.Admin.Password)
		if err != nil {
			return fmt.Errorf("密码哈希失败: %w", err)
		}
		passwordHash = hashedPassword
	}

	// 创建管理员
	user := &models.User{
		Username:     s.cfg.Admin.Username,
		PasswordHash: passwordHash,
		IsActive:     true,
		IsAdmin:      true,
	}

	if err := s.userRepo.Create(user); err != nil {
		return fmt.Errorf("创建管理员失败: %w", err)
	}

	return nil
}
