package handler

import (
	"archive/zip"
	"bytes"
	"gen-go/internal/utils"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

type FileConversionHandler struct {
	// 可以添加 service 依赖
}

func NewFileConversionHandler() *FileConversionHandler {
	return &FileConversionHandler{}
}

// ConvertFilesDirect 直接上传文件并转换格式（CSV<->JSONL）
func (h *FileConversionHandler) ConvertFilesDirect(c *gin.Context) {
	form, err := c.MultipartForm()
	if err != nil {
		utils.BadRequest(c, "请选择要转换的文件")
		return
	}

	files := form.File["files"]
	if len(files) == 0 {
		utils.BadRequest(c, "请选择要转换的文件")
		return
	}

	// 创建ZIP缓冲区
	zipBuffer := new(bytes.Buffer)
	zipWriter := zip.NewWriter(zipBuffer)

	convertedFiles := []map[string]string{}
	errors := []map[string]interface{}{}

	for index, fileHeader := range files {
		func() {
			// 使用defer确保文件关闭
			file, err := fileHeader.Open()
			if err != nil {
				errors = append(errors, map[string]interface{}{
					"index": index,
					"error": "无法打开文件",
				})
				return
			}
			defer file.Close()

			// 读取文件内容
			buf := new(bytes.Buffer)
			if _, err := buf.ReadFrom(file); err != nil {
				errors = append(errors, map[string]interface{}{
					"index": index,
					"error": "读取文件失败",
				})
				return
			}
			content := buf.Bytes()

			filename := fileHeader.Filename
			if filename == "" {
				errors = append(errors, map[string]interface{}{
					"index": index,
					"error": "文件名为空",
				})
				return
			}

			var convertedContent []byte
			var newFilename string
			var conversionType string

			// 判断文件格式并转换
			if strings.HasSuffix(filename, ".csv") {
				// CSV -> JSONL
				convertedContent, err = utils.ConvertCSVToJSONL(content)
				if err != nil {
					errors = append(errors, map[string]interface{}{
						"index":    index,
						"filename": filename,
						"error":    err.Error(),
					})
					return
				}
				newFilename = filename[:len(filename)-4] + ".jsonl"
				conversionType = "csv_to_jsonl"
			} else if strings.HasSuffix(filename, ".jsonl") {
				// JSONL -> CSV
				convertedContent, err = utils.ConvertJSONLToCSV(content)
				if err != nil {
					errors = append(errors, map[string]interface{}{
						"index":    index,
						"filename": filename,
						"error":    err.Error(),
					})
					return
				}
				newFilename = filename[:len(filename)-6] + ".csv"
				conversionType = "jsonl_to_csv"
			} else {
				errors = append(errors, map[string]interface{}{
					"index":    index,
					"filename": filename,
					"error":    "不支持的文件格式，仅支持.csv和.jsonl",
				})
				return
			}

			// 添加转换后的文件到ZIP
			writer, err := zipWriter.Create(newFilename)
			if err != nil {
				errors = append(errors, map[string]interface{}{
					"index":    index,
					"filename": filename,
					"error":    "创建ZIP文件条目失败",
				})
				return
			}

			if _, err := writer.Write(convertedContent); err != nil {
				errors = append(errors, map[string]interface{}{
					"index":    index,
					"filename": filename,
					"error":    "写入ZIP文件失败",
				})
				return
			}

			convertedFiles = append(convertedFiles, map[string]string{
				"original_filename":   filename,
				"converted_filename":  newFilename,
				"conversion_type":     conversionType,
			})
		}()
	}

	// 关闭ZIP写入器
	zipWriter.Close()

	// 检查是否有成功转换的文件
	if len(convertedFiles) == 0 {
		utils.InternalError(c, "没有成功转换任何文件")
		return
	}

	// 生成ZIP文件名
	timestamp := time.Now().Format("20060102_150405")
	zipFilename := filepath.Join("converted_files_"+timestamp+".zip")

	// 设置响应头
	c.Header("Content-Type", "application/zip")
	c.Header("Content-Disposition", "attachment; filename=\""+zipFilename+"\"")
	c.Data(http.StatusOK, "application/zip", zipBuffer.Bytes())
}

// BatchConvertFiles 批量转换数据库中的文件
func (h *FileConversionHandler) BatchConvertFiles(c *gin.Context) {
	var req struct {
		FileIDs []uint `json:"file_ids" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		utils.BadRequest(c, "请提供要转换的文件ID列表")
		return
	}

	// TODO: 实现从数据库读取文件并转换的逻辑
	// 这个需要注入 repository/service 来获取文件内容
	utils.InternalError(c, "批量转换功能开发中，请使用直接上传转换功能")
}
