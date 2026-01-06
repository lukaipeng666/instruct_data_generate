package main

import (
	"log"
	"os"

	"gen-go/internal/config"
	"gen-go/internal/models"
	"gen-go/internal/repository"
	"gen-go/internal/router"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"
)

func main() {
	// 加载配置（从项目根目录读取）
	// 注意：start.sh 从项目根目录启动后端，所以使用相对路径 ./config/config.yaml
	cfg, err := config.LoadConfig("./config/config.yaml")
	if err != nil {
		log.Fatalf("加载配置失败: %v", err)
	}

	// 初始化日志
	logger := logrus.New()
	logger.SetFormatter(&logrus.JSONFormatter{})
	logger.SetOutput(os.Stdout)
	logger.SetLevel(logrus.InfoLevel)

	// 初始化数据库
	if err := models.InitDB(cfg); err != nil {
		log.Fatalf("初始化数据库失败: %v", err)
	}
	db := models.GetDB()

	// 初始化Redis
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.GetAddress(),
		DB:       cfg.Redis.DB,
		Password: cfg.Redis.Password,
	})

	// 初始化Repository
	userRepo := repository.NewUserRepository(db)
	taskRepo := repository.NewTaskRepository(db)
	fileRepo := repository.NewDataFileRepository(db)
	_ = repository.NewGeneratedDataRepository(db)
	modelRepo := repository.NewModelConfigRepository(db)

	// 初始化工具
	jwtManager := utils.NewJWTManager(
		cfg.JWT.SecretKey,
		cfg.JWT.Algorithm,
		cfg.JWT.GetExpireDuration(),
	)

	// 初始化Service
	authService := service.NewAuthService(userRepo, jwtManager, cfg)

	// 初始化管理员账户
	if err := authService.InitAdmin(); err != nil {
		logger.Warnf("初始化管理员失败: %v", err)
	}

	_ = service.NewTaskManager(taskRepo, userRepo, fileRepo, modelRepo, redisClient, cfg)

	// 设置路由
	r := router.SetupRouter(cfg, jwtManager, logger, db, redisClient)

	// 启动服务器
	addr := cfg.Server.GetAddress()
	logger.Infof("服务器启动在 %s", addr)

	if cfg.Server.ProductionMode {
		logger.Info("生产模式: API文档已禁用")
	} else {
		logger.Infof("开发模式: API文档已启用")
		logger.Infof("管理员账号: %s", cfg.Admin.Username)
		logger.Infof("管理员密码: %s", cfg.Admin.Password)
	}

	if err := r.Run(addr); err != nil {
		log.Fatalf("启动服务器失败: %v", err)
	}
}
