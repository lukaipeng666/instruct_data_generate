package router

import (
	"gen-go/internal/config"
	"gen-go/internal/handler"
	"gen-go/internal/middleware"
	"gen-go/internal/repository"
	"gen-go/internal/service"
	"gen-go/internal/utils"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/sirupsen/logrus"
	"gorm.io/gorm"
)

// SetupRouter 设置路由
func SetupRouter(
	cfg *config.Config,
	jwtManager *utils.JWTManager,
	logger *logrus.Logger,
	db *gorm.DB,
	redisClient *redis.Client,
) *gin.Engine {
	// 设置Gin模式
	if cfg.Server.ProductionMode {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.New()

	// 全局中间件
	r.Use(middleware.LoggerMiddleware(logger))
	r.Use(gin.Recovery())
	r.Use(middleware.CORS(cfg))

	// 健康检查
	r.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"message": "数据生成任务管理系统 API",
			"version": "1.0.0",
		})
	})

	// 初始化Repository
	userRepo := repository.NewUserRepository(db)
	taskRepo := repository.NewTaskRepository(db)
	fileRepo := repository.NewDataFileRepository(db)
	generatedDataRepo := repository.NewGeneratedDataRepository(db)
	modelConfigRepo := repository.NewModelConfigRepository(db)

	// 初始化Service
	authService := service.NewAuthService(userRepo, jwtManager, cfg)
	taskManager := service.NewTaskManager(taskRepo, userRepo, fileRepo, modelConfigRepo, redisClient, cfg)
	dataFileService := service.NewDataFileService(fileRepo)
	modelService := service.NewModelService(modelConfigRepo, redisClient)
	generatedDataService := service.NewGeneratedDataService(generatedDataRepo)
	_ = service.NewFileConversionService()

	// 初始化Handler
	authHandler := handler.NewAuthHandler(authService)
	taskHandler := handler.NewTaskHandler(taskManager, redisClient)
	dataFileHandler := handler.NewDataFileHandler(dataFileService)
	modelHandler := handler.NewModelHandler(modelService)
	generatedDataHandler := handler.NewGeneratedDataHandler(generatedDataService)
	reportHandler := handler.NewReportHandler(generatedDataRepo, taskRepo)
	adminHandler := handler.NewAdminHandler(userRepo, taskRepo, modelService)
	fileConversionHandler := handler.NewFileConversionHandler()

	// API路由组
	api := r.Group("/api")
	{
		// 公开路由
		api.POST("/register", authHandler.Register)
		api.POST("/login", authHandler.Login)

		// 内部API（用于Python子进程调用，使用内部密钥认证）
		api.POST("/model-call", middleware.InternalAPIAuth(), modelHandler.ModelCall)

		// 认证路由
		authorized := api.Group("")
		authorized.Use(middleware.AuthMiddleware(jwtManager))
		{
			// 用户信息
			authorized.GET("/me", authHandler.GetMe)
			authorized.POST("/logout", authHandler.Logout)

			// 任务类型
			authorized.GET("/task_types", dataFileHandler.GetTaskTypes)

			// 任务管理
			authorized.POST("/start", taskHandler.StartTask)
			authorized.GET("/progress/:task_id", taskHandler.GetProgress)
			authorized.GET("/progress_unified/:task_id", taskHandler.GetProgressUnified)
			authorized.POST("/stop/:task_id", taskHandler.StopTask)
			authorized.DELETE("/task/:task_id", taskHandler.DeleteTask)
			authorized.GET("/status/:task_id", taskHandler.GetTaskStatus)
			authorized.GET("/tasks", taskHandler.GetAllTasks)
			authorized.GET("/active_task", taskHandler.GetActiveTask)

			// 数据文件管理
			authorized.GET("/data_files", dataFileHandler.ListFiles)
			authorized.POST("/data_files/upload", dataFileHandler.UploadFile)
			authorized.GET("/data_files/:file_id", dataFileHandler.GetFile)
			authorized.DELETE("/data_files/:file_id", dataFileHandler.DeleteFile)
			authorized.POST("/data_files/batch_delete", dataFileHandler.BatchDeleteFiles)
			authorized.GET("/data_files/:file_id/download", dataFileHandler.DownloadFile)
			authorized.GET("/data_files/:file_id/download_csv", dataFileHandler.DownloadFileAsCSV)
			authorized.GET("/data_files/:file_id/content", dataFileHandler.GetFileContent)
			authorized.GET("/data_files/:file_id/content/editable", dataFileHandler.GetFileContentEditable)
			authorized.PUT("/data_files/:file_id/content/:item_index", dataFileHandler.UpdateFileContent)
			authorized.POST("/data_files/:file_id/content", dataFileHandler.AddFileContent)
			authorized.DELETE("/data_files/:file_id/content/batch", dataFileHandler.BatchDeleteContent)
			authorized.POST("/data_files/batch_download", dataFileHandler.BatchDownloadFiles)

			// 文件转换
			authorized.POST("/data_files/batch_convert", fileConversionHandler.BatchConvertFiles)
			authorized.POST("/convert_files", fileConversionHandler.ConvertFilesDirect)

			// 模型接口
			authorized.GET("/models", modelHandler.GetModels)

			// 生成数据接口
			authorized.GET("/generated_data", generatedDataHandler.ListData)
			authorized.POST("/generated_data/batch_update", generatedDataHandler.BatchUpdate)
			authorized.POST("/generated_data/batch_confirm", generatedDataHandler.BatchConfirm)
			authorized.GET("/generated_data/export", generatedDataHandler.ExportData)
			authorized.GET("/generated_data/:task_id/download", generatedDataHandler.DownloadTaskData)
			authorized.GET("/generated_data/:task_id/info", generatedDataHandler.GetTaskInfo)
			authorized.GET("/generated_data/:task_id/download_csv", func(c *gin.Context) {
				c.Request.URL.RawQuery = "format=csv"
				generatedDataHandler.DownloadTaskData(c)
			})
			authorized.PUT("/generated_data/:data_id", generatedDataHandler.UpdateData)
			authorized.POST("/generated_data/:data_id/confirm", generatedDataHandler.ConfirmData)
			authorized.DELETE("/generated_data/batch", generatedDataHandler.DeleteBatch)

			// 报告接口
			authorized.GET("/reports", reportHandler.ListReports)
			authorized.GET("/reports/:task_id/data", reportHandler.GetReportData)
			authorized.GET("/reports/:task_id/data/editable", reportHandler.GetReportDataEditable)
			authorized.DELETE("/reports/:task_id", reportHandler.DeleteReport)
			authorized.POST("/reports/batch_delete", reportHandler.BatchDeleteReports)

			// 管理员接口
			adminGroup := authorized.Group("/admin")
			adminGroup.Use(middleware.AdminMiddleware())
			{
				adminGroup.GET("/users", adminHandler.ListUsers)
				adminGroup.DELETE("/users/:id", adminHandler.DeleteUser)
				adminGroup.GET("/users/:id/reports", adminHandler.GetUserReports)
				adminGroup.GET("/users/:id/reports/:task_id/download", adminHandler.DownloadUserReport)

				adminGroup.GET("/models", modelHandler.GetAllModels)
				adminGroup.POST("/models", modelHandler.CreateModel)
				adminGroup.PUT("/models/:id", modelHandler.UpdateModel)
				adminGroup.DELETE("/models/:id", modelHandler.DeleteModel)

				adminGroup.GET("/tasks", adminHandler.ListAllTasks)
				adminGroup.DELETE("/tasks/:id", adminHandler.DeleteTask)
			}
		}
	}

	return r
}
