package config

import (
	"fmt"
	"time"
)

// Config 应用配置结构
type Config struct {
	Server      ServerConfig   `mapstructure:"server"`
	Database    DatabaseConfig `mapstructure:"database"`
	Redis       RedisConfig    `mapstructure:"redis_service"`
	JWT         JWTConfig      `mapstructure:"jwt"`
	Admin       AdminConfig    `mapstructure:"admin"`
	CORS        CORSConfig     `mapstructure:"cors"`
	Frontend    FrontendConfig `mapstructure:"frontend"`
	Model       ModelConfig    `mapstructure:"model_services"`
	ProjectRoot string         `mapstructure:"project_root"`
}

// GetModelServices 获取模型服务地址列表
func (c *Config) GetModelServices() []string {
	// 返回配置文件中的服务地址列表
	// 如果为空，返回空切片，由调用方决定如何处理
	return c.Model.DefaultServices
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Host           string `mapstructure:"host"`
	Port           int    `mapstructure:"port"`
	ProductionMode bool   `mapstructure:"production_mode"`
}

// GetAddress 获取服务器地址
func (s *ServerConfig) GetAddress() string {
	return fmt.Sprintf("%s:%d", s.Host, s.Port)
}

// DatabaseConfig 数据库配置
type DatabaseConfig struct {
	Path string `mapstructure:"path"`
}

// RedisConfig Redis配置
type RedisConfig struct {
	Host                  string `mapstructure:"host"`
	Port                  int    `mapstructure:"port"`
	DB                    int    `mapstructure:"db"`
	Password              string `mapstructure:"password"`
	MaxWaitTime           int    `mapstructure:"max_wait_time"`
	DefaultMaxConcurrency int    `mapstructure:"default_max_concurrency"`
}

// GetAddress 获取Redis地址
func (r *RedisConfig) GetAddress() string {
	return fmt.Sprintf("%s:%d", r.Host, r.Port)
}

// GetMaxWaitDuration 获取最大等待时间
func (r *RedisConfig) GetMaxWaitDuration() time.Duration {
	return time.Duration(r.MaxWaitTime) * time.Second
}

// JWTConfig JWT配置
type JWTConfig struct {
	SecretKey     string `mapstructure:"secret_key"`
	Algorithm     string `mapstructure:"algorithm"`
	ExpireMinutes int    `mapstructure:"expire_minutes"`
}

// GetExpireDuration 获取过期时间
func (j *JWTConfig) GetExpireDuration() time.Duration {
	return time.Duration(j.ExpireMinutes) * time.Minute
}

// AdminConfig 管理员配置
type AdminConfig struct {
	Username string `mapstructure:"username"`
	Password string `mapstructure:"password"`
}

// CORSConfig CORS配置
type CORSConfig struct {
	Origins          []string `mapstructure:"origins"`
	AllowCredentials bool     `mapstructure:"allow_credentials"`
	AllowMethods     []string `mapstructure:"allow_methods"`
	AllowHeaders     []string `mapstructure:"allow_headers"`
}

// FrontendConfig 前端配置
type FrontendConfig struct {
	URL string `mapstructure:"url"`
}

// ModelConfig 模型服务配置
type ModelConfig struct {
	DefaultServices []string `mapstructure:"default_services"`
	DefaultModel    string   `mapstructure:"default_model"`
	DefaultAPIKey   string   `mapstructure:"default_api_key"`
}
