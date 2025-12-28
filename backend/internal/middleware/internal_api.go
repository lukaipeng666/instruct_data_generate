package middleware

import (
	"os"

	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
)

// InternalAPIAuth 内部API认证中间件
// 用于Python子进程调用Go后端API，使用内部密钥认证
func InternalAPIAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 从环境变量或配置获取内部API密钥
		internalKey := os.Getenv("INTERNAL_API_KEY")
		if internalKey == "" {
			// 默认密钥（生产环境应该从环境变量设置）
			internalKey = "gen-internal-api-key-2024"
		}

		// 获取请求头中的密钥
		requestKey := c.GetHeader("X-Internal-API-Key")

		// 验证密钥
		if requestKey != internalKey {
			utils.Unauthorized(c, "无效的内部API密钥")
			c.Abort()
			return
		}

		c.Next()
	}
}
