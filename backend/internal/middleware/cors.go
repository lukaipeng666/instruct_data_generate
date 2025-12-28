package middleware

import (
	"gen-go/internal/config"

	"github.com/gin-gonic/gin"
)

// CORS 跨域中间件
func CORS(cfg *config.Config) gin.HandlerFunc {
	return func(c *gin.Context) {
		origins := cfg.CORS.Origins
		origin := c.Request.Header.Get("Origin")

		// 检查origin是否在允许列表中
		allowed := false
		for _, o := range origins {
			if o == "*" || o == origin {
				allowed = true
				break
			}
		}

		if allowed {
			c.Header("Access-Control-Allow-Origin", origin)
		}

		if cfg.CORS.AllowCredentials {
			c.Header("Access-Control-Allow-Credentials", "true")
		}

		methods := cfg.CORS.AllowMethods
		if len(methods) > 0 {
			c.Header("Access-Control-Allow-Methods", joinStrings(methods, ", "))
		}

		headers := cfg.CORS.AllowHeaders
		if len(headers) > 0 {
			c.Header("Access-Control-Allow-Headers", joinStrings(headers, ", "))
		}

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

func joinStrings(strs []string, sep string) string {
	if len(strs) == 0 {
		return ""
	}
	result := strs[0]
	for i := 1; i < len(strs); i++ {
		result += sep + strs[i]
	}
	return result
}
