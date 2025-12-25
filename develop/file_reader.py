#!/usr/bin/env python3
"""
文件读取模块
负责从数据库读取和解析JSONL格式的数据文件
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple
import sys
import os

# 添加数据库模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import SessionLocal
from database.file_service import get_file_content


class FileReader:
    """文件读取器，负责从数据库读取和分配样本数据"""
    
    @staticmethod
    def read_from_database(file_id: int, user_id: int) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        从数据库读取文件内容并解析为样本列表
        
        Args:
            file_id: 数据文件ID
            user_id: 用户ID
            
        Returns:
            Tuple[samples, errors]: 成功读取的样本列表和错误信息列表
        """
        samples = []
        errors = []
        
        db = SessionLocal()
        try:
            # 从数据库获取文件内容
            file_content = get_file_content(db, file_id, user_id)
            if not file_content:
                error_msg = f"数据库文件不存在或无权访问 (file_id={file_id}, user_id={user_id})"
                errors.append(error_msg)
                return [], errors
            
            # 解析文件内容（假设是JSONL格式）
            content_str = file_content.decode('utf-8')
            for line_num, line in enumerate(content_str.strip().split('\n'), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    samples.append(data)
                except json.JSONDecodeError as e:
                    error_msg = f"第{line_num}行JSON解析失败: {e}"
                    errors.append(error_msg)
                    print(error_msg)
            
            return samples, errors
            
        except Exception as e:
            error_msg = f"从数据库读取文件失败: {e}"
            errors.append(error_msg)
            return [], errors
        finally:
            db.close()
    
    @staticmethod
    def read_samples(file_id: int, user_id: int) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        从数据库读取样本数据
        
        Args:
            file_id: 数据文件ID
            user_id: 用户ID
            
        Returns:
            Tuple[samples, errors]: 成功读取的样本列表和错误信息列表
        """
        return FileReader.read_from_database(file_id, user_id)
    
    @staticmethod
    def split_samples_in_memory(samples: List[Dict[str, Any]], 
                                 num_parts: int) -> List[List[Dict[str, Any]]]:
        """
        在内存中将样本分割成多个部分
        
        Args:
            samples: 样本列表
            num_parts: 分割的部分数
            
        Returns:
            分割后的样本列表的列表
        """
        if not samples:
            return [[] for _ in range(num_parts)]
        
        total_samples = len(samples)
        samples_per_part = math.ceil(total_samples / num_parts)
        
        parts = []
        for i in range(num_parts):
            start_idx = i * samples_per_part
            end_idx = min((i + 1) * samples_per_part, total_samples)
            
            if start_idx >= total_samples:
                parts.append([])
            else:
                parts.append(samples[start_idx:end_idx])
        
        return parts


class OutputWriter:
    """输出写入器，负责写入生成的数据"""
    
    @staticmethod
    def write_jsonl(file_path: str, data: List[Dict[str, Any]], 
                    mode: str = 'w') -> int:
        """
        写入JSONL文件
        
        Args:
            file_path: 输出文件路径
            data: 要写入的数据列表
            mode: 写入模式 ('w' 覆盖, 'a' 追加)
            
        Returns:
            写入的记录数
        """
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        count = 0
        with open(file_path, mode, encoding='utf-8') as f:
            for item in data:
                json_line = json.dumps(item, ensure_ascii=False)
                f.write(json_line + '\n')
                count += 1
        
        return count
    
    @staticmethod
    def append_jsonl(file_path: str, data: List[Dict[str, Any]]) -> int:
        """
        追加写入JSONL文件
        
        Args:
            file_path: 输出文件路径
            data: 要追加的数据列表
            
        Returns:
            写入的记录数
        """
        return OutputWriter.write_jsonl(file_path, data, mode='a')
    
    @staticmethod
    def merge_jsonl_files(input_files: List[str], output_file: str) -> int:
        """
        合并多个JSONL文件
        
        Args:
            input_files: 输入文件列表
            output_file: 输出文件路径
            
        Returns:
            合并的总记录数
        """
        total_records = 0
        
        # 确保目录存在
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for input_file in input_files:
                if Path(input_file).exists():
                    with open(input_file, 'r', encoding='utf-8') as in_f:
                        for line in in_f:
                            line = line.strip()
                            if line:
                                out_f.write(line + '\n')
                                total_records += 1
        
        return total_records
