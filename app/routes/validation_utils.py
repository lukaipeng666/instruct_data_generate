#!/usr/bin/env python3
"""
验证工具函数
提供数据格式验证功能
"""

from typing import Tuple


def validate_turns_balance(turns: list) -> Tuple[bool, str]:
    """
    验证对话轮次中 Human 和 Assistant 数量是否一致
    
    Args:
        turns: 对话轮次列表
        
    Returns:
        tuple: (是否合法, 错误信息)
    """
    if not turns:
        return True, ""
    
    human_count = sum(1 for t in turns if t.get('role') == 'Human')
    assistant_count = sum(1 for t in turns if t.get('role') == 'Assistant')
    
    if human_count != assistant_count:
        return False, f"Human 和 Assistant 数量不一致（Human: {human_count}, Assistant: {assistant_count}），请保证对话轮次成对出现"
    
    return True, ""

