package utils

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

// Turn 对话轮次
type Turn struct {
	Role string `json:"role"`
	Text string `json:"text"`
}

// JSONLData JSONL数据结构
type JSONLData struct {
	Meta  map[string]interface{} `json:"meta"`
	Turns []Turn                 `json:"turns"`
}

// ConvertCSVToJSONL 将CSV内容转换为JSONL格式
func ConvertCSVToJSONL(csvContent []byte) ([]byte, error) {
	// 解码CSV内容
	csvText := string(csvContent)
	if strings.HasPrefix(csvText, "\xEF\xBB\xBF") {
		csvText = strings.TrimPrefix(csvText, "\xEF\xBB\xBF")
	}

	reader := csv.NewReader(strings.NewReader(csvText))

	// 读取列名
	headers, err := reader.Read()
	if err != nil {
		return nil, fmt.Errorf("读取CSV表头失败: %w", err)
	}

	// 验证第一列是否为 meta
	if len(headers) == 0 || headers[0] != "meta" {
		return nil, fmt.Errorf("CSV 第一列必须命名为 'meta'")
	}

	// 提取所有 Human 和 Assistant 列的索引
	var humanIndices, assistantIndices []int
	for i, col := range headers {
		if col == "Human" {
			humanIndices = append(humanIndices, i)
		} else if col == "Assistant" {
			assistantIndices = append(assistantIndices, i)
		}
	}

	if len(humanIndices) != len(assistantIndices) {
		return nil, fmt.Errorf("Human 和 Assistant 列数量不匹配")
	}

	// 记录当前活跃的 meta
	currentActiveMeta := ""
	var jsonlLines []string

	for {
		row, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("读取CSV行失败: %w", err)
		}

		// 跳过空行
		if len(row) == 0 {
			continue
		}

		// 处理当前行的 meta（支持共享逻辑）
		rowMeta := ""
		if len(row) > 0 {
			rowMeta = strings.TrimSpace(row[0])
		}
		if rowMeta != "" {
			currentActiveMeta = rowMeta
		}

		// 提取多轮对话内容
		var turns []Turn
		for i := 0; i < len(humanIndices) && i < len(assistantIndices); i++ {
			hIdx := humanIndices[i]
			aIdx := assistantIndices[i]

			// 添加 Human 内容（非空才添加）
			if hIdx < len(row) && strings.TrimSpace(row[hIdx]) != "" {
				turns = append(turns, Turn{
					Role: "Human",
					Text: strings.TrimSpace(row[hIdx]),
				})
			}

			// 添加 Assistant 内容（非空才添加）
			if aIdx < len(row) && strings.TrimSpace(row[aIdx]) != "" {
				turns = append(turns, Turn{
					Role: "Assistant",
					Text: strings.TrimSpace(row[aIdx]),
				})
			}
		}

		// 构造输出对象
		outputObj := JSONLData{
			Meta: map[string]interface{}{
				"meta_description": currentActiveMeta,
			},
			Turns: turns,
		}

		// 转换为JSON
		jsonBytes, err := json.Marshal(outputObj)
		if err != nil {
			return nil, fmt.Errorf("JSON序列化失败: %w", err)
		}

		jsonlLines = append(jsonlLines, string(jsonBytes))
	}

	// 合并为JSONL内容
	jsonlContent := strings.Join(jsonlLines, "\n") + "\n"
	return []byte(jsonlContent), nil
}

// ConvertJSONLToCSV 将JSONL内容转换为CSV格式
func ConvertJSONLToCSV(jsonlContent []byte) ([]byte, error) {
	// 解码JSONL内容
	jsonlText := string(jsonlContent)

	// 用字典归类：key=meta值，value=该meta对应的所有行数据
	type Conversation struct {
		Meta         string
		HumanTexts   []string
		AssistantTexts []string
	}

	metaGroups := make(map[string][]*Conversation)

	lines := strings.Split(strings.TrimSpace(jsonlText), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		var data JSONLData
		if err := json.Unmarshal([]byte(line), &data); err != nil {
			return nil, fmt.Errorf("解析JSONL失败: %w", err)
		}

		// 提取meta
		meta := ""
		if data.Meta != nil {
			if desc, ok := data.Meta["meta_description"].(string); ok {
				meta = strings.TrimSpace(desc)
			}
		}
		if meta == "" {
			meta = "__empty_meta__"
		}

		// 提取对话内容
		var humanTexts, assistantTexts []string
		for _, msg := range data.Turns {
			role := strings.TrimSpace(msg.Role)
			text := strings.TrimSpace(msg.Text)
			if role == "Human" {
				humanTexts = append(humanTexts, text)
			} else if role == "Assistant" {
				assistantTexts = append(assistantTexts, text)
			}
		}

		// 补齐对话轮次
		maxTurns := len(humanTexts)
		if len(assistantTexts) > maxTurns {
			maxTurns = len(assistantTexts)
		}
		for len(humanTexts) < maxTurns {
			humanTexts = append(humanTexts, "")
		}
		for len(assistantTexts) < maxTurns {
			assistantTexts = append(assistantTexts, "")
		}

		// 合并为对话对列表
		var conversation []string
		for i := 0; i < maxTurns; i++ {
			conversation = append(conversation, humanTexts[i])
			conversation = append(conversation, assistantTexts[i])
		}

		// 加入对应meta的分组
		conv := &Conversation{
			Meta:           meta,
			HumanTexts:     humanTexts,
			AssistantTexts: assistantTexts,
		}
		if _, exists := metaGroups[meta]; !exists {
			metaGroups[meta] = []*Conversation{}
		}
		metaGroups[meta] = append(metaGroups[meta], conv)
	}

	// 整理所有行数据
	var allRows [][]string
	for _, conversations := range metaGroups {
		for i, conv := range conversations {
			var row []string
			if i == 0 {
				metaValue := conv.Meta
				if metaValue == "__empty_meta__" {
					metaValue = ""
				}
				row = []string{metaValue}
			} else {
				row = []string{""}
			}

			// 添加对话内容
			for j := 0; j < len(conv.HumanTexts) || j < len(conv.AssistantTexts); j++ {
				if j < len(conv.HumanTexts) {
					row = append(row, conv.HumanTexts[j])
				} else {
					row = append(row, "")
				}
				if j < len(conv.AssistantTexts) {
					row = append(row, conv.AssistantTexts[j])
				} else {
					row = append(row, "")
				}
			}

			allRows = append(allRows, row)
		}
	}

	if len(allRows) == 0 {
		return nil, fmt.Errorf("没有有效的数据")
	}

	// 生成表头
	maxConvLength := 0
	for _, row := range allRows {
		if len(row)-1 > maxConvLength {
			maxConvLength = len(row) - 1
		}
	}

	numTurns := maxConvLength / 2
	headers := []string{"meta"}
	for i := 0; i < numTurns; i++ {
		headers = append(headers, "Human", "Assistant")
	}

	// 补齐所有行的长度
	for _, row := range allRows {
		for len(row) < len(headers) {
			row = append(row, "")
		}
	}

	// 写入CSV
	var buf bytes.Buffer
	writer := csv.NewWriter(&buf)
	if err := writer.Write(headers); err != nil {
		return nil, fmt.Errorf("写入CSV表头失败: %w", err)
	}
	if err := writer.WriteAll(allRows); err != nil {
		return nil, fmt.Errorf("写入CSV数据失败: %w", err)
	}
	writer.Flush()

	if err := writer.Error(); err != nil {
		return nil, fmt.Errorf("CSV写入错误: %w", err)
	}

	// 添加 UTF-8 BOM
	output := buf.Bytes()
	return append([]byte{0xEF, 0xBB, 0xBF}, output...), nil
}
