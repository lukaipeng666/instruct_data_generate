package utils

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

// ParseJSONL 解析JSONL格式
func ParseJSONL(data []byte) ([]map[string]interface{}, error) {
	lines := strings.Split(string(data), "\n")
	var results []map[string]interface{}

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		var item map[string]interface{}
		if err := json.Unmarshal([]byte(line), &item); err != nil {
			return nil, fmt.Errorf("解析失败: %w", err)
		}
		results = append(results, item)
	}

	return results, nil
}

// ParseJSONString 解析单个JSON字符串
func ParseJSONString(data string, v interface{}) error {
	return json.Unmarshal([]byte(data), v)
}

// ParseCSV 解析CSV格式
func ParseCSV(data []byte) ([]map[string]interface{}, error) {
	reader := csv.NewReader(bytes.NewReader(data))
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("解析CSV失败: %w", err)
	}

	if len(records) == 0 {
		return []map[string]interface{}{}, nil
	}

	// 第一行是标题
	headers := records[0]
	var results []map[string]interface{}

	for _, record := range records[1:] {
		if len(record) == 0 {
			continue
		}

		item := make(map[string]interface{})
		for j, value := range record {
			if j < len(headers) {
				item[headers[j]] = value
			}
		}
		results = append(results, item)
	}

	return results, nil
}

// ConvertToJSONL 转换为JSONL格式
func ConvertToJSONL(data []map[string]interface{}) ([]byte, error) {
	var buf bytes.Buffer

	for _, item := range data {
		jsonData, err := json.Marshal(item)
		if err != nil {
			return nil, fmt.Errorf("序列化失败: %w", err)
		}
		buf.Write(jsonData)
		buf.WriteByte('\n')
	}

	return buf.Bytes(), nil
}

// ConvertToCSV 转换为CSV格式
func ConvertToCSV(data []map[string]interface{}) ([]byte, error) {
	if len(data) == 0 {
		return []byte{}, nil
	}

	// 收集所有字段
	headersSet := make(map[string]bool)
	for _, item := range data {
		for key := range item {
			headersSet[key] = true
		}
	}

	var headers []string
	for key := range headersSet {
		headers = append(headers, key)
	}

	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)

	// 写入标题
	if err := writer.Write(headers); err != nil {
		return nil, fmt.Errorf("写入CSV标题失败: %w", err)
	}

	// 写入数据
	for _, item := range data {
		var record []string
		for _, header := range headers {
			value := fmt.Sprintf("%v", item[header])
			record = append(record, value)
		}
		if err := writer.Write(record); err != nil {
			return nil, fmt.Errorf("写入CSV数据失败: %w", err)
		}
	}

	writer.Flush()
	if err := writer.Error(); err != nil {
		return nil, fmt.Errorf("CSV写入失败: %w", err)
	}

	return buf.Bytes(), nil
}

// DetectContentType 检测内容类型
func DetectContentType(data []byte) string {
	trimmed := strings.TrimSpace(string(data))

	if strings.HasPrefix(trimmed, "{") || strings.HasPrefix(trimmed, "[") {
		return "application/json"
	}

	// 检查是否为CSV
	lines := strings.Split(trimmed, "\n")
	if len(lines) > 1 && strings.Contains(lines[0], ",") {
		return "text/csv"
	}

	// 默认为JSONL
	return "application/x-jsonlines"
}

// ReadJSONLines 读取JSONL格式的数据
func ReadJSONLines(r io.Reader) ([]map[string]interface{}, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	return ParseJSONL(data)
}

// WriteJSONLines 写入JSONL格式的数据
func WriteJSONLines(w io.Writer, data []map[string]interface{}) error {
	for _, item := range data {
		jsonData, err := json.Marshal(item)
		if err != nil {
			return err
		}
		if _, err := fmt.Fprintln(w, string(jsonData)); err != nil {
			return err
		}
	}
	return nil
}
