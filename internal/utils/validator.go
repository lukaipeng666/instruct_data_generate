package utils

import (
	"fmt"
	"reflect"
	"regexp"
	"strings"

	"github.com/go-playground/validator/v10"
)

var validate *validator.Validate

// InitValidator 初始化验证器
func InitValidator() {
	validate = validator.New()

	// 注册自定义验证函数
	validate.RegisterValidation("username", validateUsername)
}

// GetValidator 获取验证器实例
func GetValidator() *validator.Validate {
	if validate == nil {
		InitValidator()
	}
	return validate
}

// validateUsername 验证用户名
func validateUsername(fl validator.FieldLevel) bool {
	username := fl.Field().String()
	if len(username) < 3 || len(username) > 50 {
		return false
	}
	matched, _ := regexp.MatchString("^[a-zA-Z0-9_]+$", username)
	return matched
}

// ValidateStruct 验证结构体
func ValidateStruct(s interface{}) error {
	v := GetValidator()
	if err := v.Struct(s); err != nil {
		return formatValidationError(err)
	}
	return nil
}

// formatValidationError 格式化验证错误
func formatValidationError(err error) error {
	var errors []string

	if validationErrors, ok := err.(validator.ValidationErrors); ok {
		for _, e := range validationErrors {
			field := e.Field()
			tag := e.Tag()
			param := e.Param()

			var message string
			switch tag {
			case "required":
				message = fmt.Sprintf("%s是必填字段", field)
			case "min":
				message = fmt.Sprintf("%s长度不能小于%s", field, param)
			case "max":
				message = fmt.Sprintf("%s长度不能大于%s", field, param)
			case "email":
				message = fmt.Sprintf("%s必须是有效的邮箱地址", field)
			case "username":
				message = fmt.Sprintf("%s只能包含字母、数字和下划线，长度3-50", field)
			default:
				message = fmt.Sprintf("%s验证失败: %s", field, tag)
			}

			errors = append(errors, message)
		}
	}

	if len(errors) > 0 {
		return fmt.Errorf(strings.Join(errors, "; "))
	}

	return err
}

// GetStructFieldName 获取结构体JSON字段名
func GetStructFieldName(s interface{}, field string) string {
	t := reflect.TypeOf(s)
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}

	f, ok := t.FieldByName(field)
	if !ok {
		return field
	}

	tag := f.Tag.Get("json")
	if tag == "" || tag == "-" {
		return field
	}

	return strings.Split(tag, ",")[0]
}
