#!/usr/bin/env python3
"""
文件读取模块
负责从数据库读取和解析JSONL格式的数据文件
"""

import json
import math
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


# 注意：OutputWriter 类已删除，数据现在直接保存到数据库
