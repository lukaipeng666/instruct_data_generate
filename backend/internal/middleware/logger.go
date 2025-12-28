package middleware

import (
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"
)

// LoggerMiddleware 日志中间件
func LoggerMiddleware(logger *logrus.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery

		// 处理请求
		c.Next()

		// 记录日志
		end := time.Now()
		latency := end.Sub(start)

		entry := logger.WithFields(logrus.Fields{
			"status":     c.Writer.Status(),
			"method":     c.Request.Method,
			"path":       path,
			"query":      query,
			"ip":         c.ClientIP(),
			"user_agent": c.Request.UserAgent(),
			"latency":    latency,
			"length":     c.Writer.Size(),
		})

		userID, exists := GetUserID(c)
		if exists {
			entry = entry.WithField("user_id", userID)
		}

		if c.Writer.Status() >= 500 {
			entry.Error("HTTP Request")
		} else if c.Writer.Status() >= 400 {
			entry.Warn("HTTP Request")
		} else {
			entry.Info("HTTP Request")
		}
	}
}
