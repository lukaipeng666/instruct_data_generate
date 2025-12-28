package handler

import (
	"gen-go/internal/dto"
	"gen-go/internal/middleware"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// AuthHandler 认证处理器
type AuthHandler struct {
	authService *service.AuthService
}

// NewAuthHandler 创建认证处理器
func NewAuthHandler(authService *service.AuthService) *AuthHandler {
	return &AuthHandler{
		authService: authService,
	}
}

// Register 用户注册
// @Summary 用户注册
// @Tags 认证
// @Accept json
// @Produce json
// @Param request body dto.RegisterRequest true "注册信息"
// @Success 200 {object} utils.Response{data=dto.UserInfo}
// @Router /api/register [post]
func (h *AuthHandler) Register(c *gin.Context) {
	var req dto.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	user, err := h.authService.Register(&req)
	if err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "注册成功", dto.UserInfo{
		ID:       user.ID,
		Username: user.Username,
		IsActive: user.IsActive,
		IsAdmin:  user.IsAdmin,
	})
}

// Login 用户登录
// @Summary 用户登录
// @Tags 认证
// @Accept json
// @Produce json
// @Param request body dto.LoginRequest true "登录信息"
// @Success 200 {object} utils.Response{data=dto.LoginResponse}
// @Router /api/login [post]
func (h *AuthHandler) Login(c *gin.Context) {
	var req dto.LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, err.Error())
		return
	}

	resp, err := h.authService.Login(&req)
	if err != nil {
		utils.Unauthorized(c, err.Error())
		return
	}

	utils.SuccessWithMessage(c, "登录成功", resp)
}

// GetMe 获取当前用户信息
// @Summary 获取当前用户信息
// @Tags 认证
// @Accept json
// @Produce json
// @Security BearerAuth
// @Success 200 {object} utils.Response{data=dto.UserInfo}
// @Router /api/me [get]
func (h *AuthHandler) GetMe(c *gin.Context) {
	userID, exists := middleware.GetUserID(c)
	if !exists {
		utils.Unauthorized(c, "未认证")
		return
	}

	userInfo, err := h.authService.GetMe(userID)
	if err != nil {
		utils.NotFound(c, err.Error())
		return
	}

	utils.SuccessResponse(c, userInfo)
}

// Logout 用户登出
// @Summary 用户登出
// @Tags 认证
// @Accept json
// @Produce json
// @Security BearerAuth
// @Success 200 {object} utils.Response
// @Router /api/logout [post]
func (h *AuthHandler) Logout(c *gin.Context) {
	// JWT是无状态的,登出只需客户端删除Token
	utils.SuccessWithMessage(c, "登出成功", nil)
}
