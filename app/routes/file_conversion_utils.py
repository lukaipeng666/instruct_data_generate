#!/usr/bin/env python3
"""
文件格式转换工具函数
提供CSV和JSONL之间的相互转换功能
"""

import csv
import io
import json
from typing import List, Dict


def convert_csv_to_jsonl_content(csv_content: bytes) -> bytes:
    """
    将CSV内容转换为JSONL格式
    
    Args:
        csv_content: CSV文件的字节内容
        
    Returns:
        JSONL格式的字节内容
    """
    # 解码CSV内容
    try:
        csv_text = csv_content.decode('utf-8-sig')
    except UnicodeDecodeError:
        csv_text = csv_content.decode('utf-8')
    
    csv_reader = csv.reader(io.StringIO(csv_text))
    
    # 读取列名
    headers = next(csv_reader)
    
    # 提取所有 Human 和 Assistant 列的索引
    human_indices = [i for i, col in enumerate(headers) if col == "Human"]
    assistant_indices = [i for i, col in enumerate(headers) if col == "Assistant"]
    
    # 验证第一列是否为 meta
    if headers[0] != "meta":
        raise ValueError("CSV 第一列必须命名为 'meta'")
    
    # 记录当前活跃的 meta（用于共享逻辑）
    current_active_meta = ""
    
    jsonl_lines = []
    for row in csv_reader:
        if not row:  # 跳过空行
            continue
        
        # 处理当前行的 meta（支持共享逻辑）
        row_meta = row[0].strip() if len(row) > 0 else ""
        if row_meta:  # 如果当前行 meta 非空，更新活跃 meta
            current_active_meta = row_meta
        # 若当前行 meta 为空，则沿用之前的活跃 meta
        
        # 提取多轮对话内容
        turns = []
        for h_idx, a_idx in zip(human_indices, assistant_indices):
            # 添加 Human 内容（非空才添加）
            if h_idx < len(row) and row[h_idx].strip():
                turns.append({
                    "role": "Human",
                    "text": row[h_idx].strip()
                })
            # 添加 Assistant 内容（非空才添加）
            if a_idx < len(row) and row[a_idx].strip():
                turns.append({
                    "role": "Assistant",
                    "text": row[a_idx].strip()
                })
        
        # 构造输出对象
        output_obj = {
            "meta": {"meta_description": current_active_meta},
            "turns": turns
        }
        # 添加到JSONL行
        jsonl_lines.append(json.dumps(output_obj, ensure_ascii=False))
    
    # 合并为JSONL内容
    jsonl_content = '\n'.join(jsonl_lines) + '\n'
    return jsonl_content.encode('utf-8')


def convert_jsonl_to_csv_content(jsonl_content: bytes) -> bytes:
    """
    将JSONL内容转换为CSV格式
    
    Args:
        jsonl_content: JSONL文件的字节内容
        
    Returns:
        CSV格式的字节内容
    """
    # 解码JSONL内容
    try:
        jsonl_text = jsonl_content.decode('utf-8')
    except UnicodeDecodeError:
        jsonl_text = jsonl_content.decode('utf-8-sig')
    
    # 用字典归类：key=meta值，value=该meta对应的所有行数据
    meta_groups: Dict[str, List[List[str]]] = {}
    
    for line in jsonl_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        
        # 提取meta
        meta = (((obj.get("meta") or {}).get("meta_description")) or "").strip() or "__empty_meta__"
        
        # 提取对话内容
        turns = obj.get("turns") or []
        human_texts: List[str] = []
        assistant_texts: List[str] = []
        for msg in turns:
            role = (msg.get("role") or "").strip()
            text = (msg.get("text") or "").strip()
            if role == "Human":
                human_texts.append(text)
            elif role == "Assistant":
                assistant_texts.append(text)
        
        # 补齐对话轮次
        max_turns = max(len(human_texts), len(assistant_texts))
        human_texts += [""] * (max_turns - len(human_texts))
        assistant_texts += [""] * (max_turns - len(assistant_texts))
        
        # 合并为对话对列表
        conversation: List[str] = []
        for h, a in zip(human_texts, assistant_texts):
            conversation.extend([h, a])
        
        # 加入对应meta的分组
        if meta not in meta_groups:
            meta_groups[meta] = []
        meta_groups[meta].append(conversation)
    
    # 整理所有行数据
    all_rows: List[List[str]] = []
    for meta, conversations in meta_groups.items():
        for i, conv in enumerate(conversations):
            if i == 0:
                row = [meta if meta != "__empty_meta__" else ""] + conv
            else:
                row = [""] + conv
            all_rows.append(row)
    
    # 生成表头
    max_conv_length = max(len(row) - 1 for row in all_rows) if all_rows else 0
    num_turns = max_conv_length // 2
    headers: List[str] = ["meta"]
    for i in range(num_turns):
        headers.append(f"Human")
        headers.append(f"Assistant")
    
    # 补齐所有行的长度
    for row in all_rows:
        row += [""] * (len(headers) - len(row))
    
    # 写入CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(all_rows)
    
    return output.getvalue().encode('utf-8-sig')

