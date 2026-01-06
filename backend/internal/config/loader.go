package config

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"github.com/spf13/viper"
)

var (
	globalConfig *Config
	once         sync.Once
	configPath   string
)

// LoadConfig 加载配置文件
func LoadConfig(configFile string) (*Config, error) {
	var err error
	var cfg *Config

	once.Do(func() {
		cfg, err = loadConfigFromFile(configFile)
		if err == nil {
			globalConfig = cfg
		}
		configPath = configFile
	})

	return globalConfig, err
}

// loadConfigFromFile 从文件加载配置
func loadConfigFromFile(configFile string) (*Config, error) {
	v := viper.New()

	// 设置配置文件路径
	if configFile != "" {
		v.SetConfigFile(configFile)
	} else {
		// 默认查找 config.yaml
		v.SetConfigName("config")
		v.SetConfigType("yaml")
		v.AddConfigPath(".")
		v.AddConfigPath("./config")
	}

	// 读取环境变量
	v.AutomaticEnv()

	// 读取配置文件
	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("读取配置文件失败: %w", err)
	}

	// 解析配置
	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("解析配置文件失败: %w", err)
	}

	// 设置默认值
	setDefaults(&cfg)

	// 验证配置
	if err := validateConfig(&cfg); err != nil {
		return nil, fmt.Errorf("配置验证失败: %w", err)
	}

	return &cfg, nil
}

// setDefaults 设置默认值
func setDefaults(cfg *Config) {
	if cfg.Server.Host == "" {
		cfg.Server.Host = "0.0.0.0"
	}
	if cfg.Server.Port == 0 {
		cfg.Server.Port = 18080
	}
	if cfg.Database.Path == "" {
		cfg.Database.Path = "./database/app.db"
	}
	// Redis Host 必须从配置文件读取，不设置硬编码默认值
	// if cfg.Redis.Host == "" {
	// 	cfg.Redis.Host = "localhost"
	// }
	if cfg.Redis.Port == 0 {
		cfg.Redis.Port = 6379 // 标准 Redis 端口
	}
	if cfg.Redis.DefaultMaxConcurrency == 0 {
		cfg.Redis.DefaultMaxConcurrency = 16
	}
	if cfg.JWT.Algorithm == "" {
		cfg.JWT.Algorithm = "HS256"
	}
	if cfg.JWT.ExpireMinutes == 0 {
		cfg.JWT.ExpireMinutes = 43200 // 30天
	}
	if cfg.Admin.Username == "" {
		cfg.Admin.Username = "admin"
	}
	// CORS Origins 必须从配置文件读取，不设置硬编码默认值
	// if len(cfg.CORS.Origins) == 0 {
	// 	cfg.CORS.Origins = []string{"http://localhost:13000"}
	// }
	if cfg.CORS.AllowMethods == nil {
		cfg.CORS.AllowMethods = []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"}
	}
	if cfg.CORS.AllowHeaders == nil {
		cfg.CORS.AllowHeaders = []string{"*"}
	}
	// Frontend URL 必须从配置文件读取，不设置硬编码默认值
	// if cfg.Frontend.URL == "" {
	// 	cfg.Frontend.URL = "http://localhost:13000"
	// }
	// Model Services 必须从配置文件读取，不设置硬编码默认值
	// if len(cfg.Model.DefaultServices) == 0 {
	// 	cfg.Model.DefaultServices = []string{"http://localhost:16466/v1"}
	// }
	if cfg.Model.DefaultModel == "" {
		cfg.Model.DefaultModel = "/data/models/Qwen3-32B"
	}
}

// validateConfig 验证配置
func validateConfig(cfg *Config) error {
	if cfg.Server.Port <= 0 || cfg.Server.Port > 65535 {
		return fmt.Errorf("无效的服务器端口: %d", cfg.Server.Port)
	}

	if cfg.JWT.SecretKey == "" {
		return fmt.Errorf("JWT密钥不能为空")
	}

	if cfg.Admin.Password == "" {
		return fmt.Errorf("管理员密码不能为空")
	}

	// 检查数据库目录是否存在
	dbDir := filepath.Dir(cfg.Database.Path)
	if _, err := os.Stat(dbDir); os.IsNotExist(err) {
		if err := os.MkdirAll(dbDir, 0755); err != nil {
			return fmt.Errorf("创建数据库目录失败: %w", err)
		}
	}

	return nil
}

// GetConfig 获取全局配置
func GetConfig() *Config {
	return globalConfig
}

// ReloadConfig 重新加载配置
func ReloadConfig() (*Config, error) {
	if configPath == "" {
		return nil, fmt.Errorf("未设置配置文件路径")
	}

	return LoadConfig(configPath)
}
