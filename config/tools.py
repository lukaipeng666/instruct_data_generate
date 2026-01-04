#!/usr/bin/env python3
"""
数据生成工具函数
包含可替换的提示构建函数和规则评分函数
"""

from typing import Dict, Any, Optional
import json
import random
import threading
from .prompt_config import *
import re

# 线程局部随机数生成器，避免多线程共享全局随机状态
_thread_local = threading.local()


def _get_thread_random() -> random.Random:
    """
    获取线程局部的随机数生成器
    每个线程拥有独立的 Random 实例，避免多线程竞争
    """
    if not hasattr(_thread_local, 'rng'):
        # 为每个线程创建独立的 Random 实例
        _thread_local.rng = random.Random()
    return _thread_local.rng


def build_generation_prompt(sample_data: Dict[str, Any], num_variants: int = 1, special: str = "", directions: list = ['信用卡年费', ' 股票爆仓', ' 基金赎回']) -> str:
    """
    构建数据生成提示词
    
    Args:
        sample_data: 样本数据，包含meta和turns字段
        num_variants: 要生成的变体数量
    
    Returns:
        str: 生成提示词
    """
    meta = sample_data.get('meta', {})
    turns = sample_data.get('turns', [])
    
    # 获取任务描述
    meta_description = meta.get('meta_description', '')
    
    conversation_str = json.dumps(turns, ensure_ascii=False, indent=4)

    # 使用线程局部随机数生成器，避免多线程竞争
    thread_rng = _get_thread_random()
    direction = thread_rng.sample(directions, min(num_variants, len(directions)))

    # 构建生成提示词
    prompt = command_prompt.format(num_variants=num_variants, meta_description=meta_description, conversation_str=conversation_str, direction=direction, special=special)

    # print(prompt)
    # import time
    # time.sleep(100000)
    return prompt


def build_evaluation_prompt(sample_data: Dict[str, Any], generated_data: Dict[str, Any], special: str = "") -> str:
    """
    构建评估提示词
    
    Args:
        sample_data: 原始样本数据
        generated_data: 生成的数据
    
    Returns:
        str: 评估提示词
    """
    meta = sample_data.get('meta', {})
    meta_description = meta.get('meta_description', '')
    
    # 获取生成的对话
    generated_turns = generated_data.get('turns', [])
    conversation = []
    for turn in generated_turns:
        role = turn.get('role', '')
        text = turn.get('text', '')
        conversation.append(f"{role}: {text}")
    
    conversation_str = '\n'.join(conversation)
    
    if special != "":
        special = "本数据集有以下特殊规则\n" + special
    
    # 构建评估提示词
    prompt = judge_prompt.format(meta_description=meta_description, conversation_str=conversation_str, special=special)

    return prompt


def _evaluate_entity_format(answer: str) -> int:
    """评估实体识别任务的格式"""
    score = 0
    answer = answer.strip()
    # 规则1：开头必须是"[["
    if answer == "[ ]":
        return 10
    if answer.startswith("[["):
        score += 2
    else:
        print("开头不符合")
        return 0  # 开头不符合直接返回0分
    
    # 规则2：结尾必须是"]]"
    if answer.endswith("]]"):
        score += 2
    else:
        print("结尾不符合")
        return 0  # 结尾不符合直接返回0分
    
    # 规则3：检查"["和"]"的数量是否成对
    left_brackets = answer.count('[')
    right_brackets = answer.count(']')
    if left_brackets == right_brackets and left_brackets >= 2:
        score += 3
    else:
        print("括号不成对")
        return 0  # 括号不成对直接返回0分
    
    # 规则4：中间不许出现换行符\n
    if '\n' not in answer:
        score += 3
        try:
            answer_list = json.loads(answer)
            if len(answer_list) == 0:
                return score
            base_length = len(answer_list[0])
            if len(answer_list) != 4:
                print("实体槽位不对")
                return 0
            if any(len(content) != base_length for content in answer_list):
                print("列表内长度不一致")
                return 0
            prohibit = ["YYYY", "HH", "时", "分", "秒", "MM", "DD", "SS"]
            if any(pro in str(answer_list[3]) for pro in prohibit):
                print("时间单位不应该存在")
                return 0
            for i in range(len(answer_list[2])):
                if "|" in answer_list[2][i] and "|" not in answer_list[3][i]:
                    print("|缺失")
                    return 0
                if "&" in answer_list[2][i] and "&" not in answer_list[3][i]:
                    print("&缺失")
                    return 0
            
        except Exception as e:
            print(f"列表无法被解析,原因是:{e}")
            return 0
    else:
        print("存在换行符")
        return 0  # 包含换行符直接返回0分
    return score  # 满分10分

def _evaluate_general_format(answer: str) -> int:
    """通用格式评估"""
    score = 10  # 默认满分
    
    # 检查是否为空
    if not answer.strip():
        return 0
    
    # 检查是否有多余的解释性文字
    if any(phrase in answer.lower() for phrase in ['以上是', '根据', '分析如下', '总结']):
        score -= 2
    
    # 尝试抽取可能的字典/列表结构（包含花括号或方括号的部分）
    if '{' in answer or '}' in answer or '[' in answer or ']' in answer:
        # 使用正则匹配可能的字典/列表结构
        pattern = r'(\{.*?\}|\[.*?\])'
        matches = re.findall(pattern, answer, re.DOTALL)
        
        if matches:
            # 尝试解析抽取到的结构
            parse_failed = False
            for match in matches:
                try:
                    json.loads(match)
                except:
                    parse_failed = True
                    break
            if parse_failed:
                score -= 5  # 能抽取结构但解析失败扣分
    
    return max(0, score)

def _evaluate_question_rewrite_format(answer: str) -> int:
    try:
        answer_list = json.loads(answer)
        return 10
    except Exception as e:
        print("无法被解析")
        return 0

def  build_filter_prompt(content: str) -> str:
    # 构建评估提示词
    prompt = filter_prompt.format(data=content)

    return prompt


# 配置函数映射，方便动态替换
PROMPT_BUILDERS = {
    'generation': build_generation_prompt,
    'evaluation': build_evaluation_prompt,
    'filter': build_filter_prompt,
}

# 规则函数判定注册
FORMAT_EVALUATORS = {
    'entity_extraction': lambda text: _evaluate_entity_format(text),
    'general': lambda text: _evaluate_general_format(text),
    'question_rewrite': lambda text: _evaluate_question_rewrite_format(text),
    'calculation' : lambda text: _evaluate_general_format(text)
}


def get_prompt_builder(prompt_type: str):
    """获取提示构建函数"""
    return PROMPT_BUILDERS.get(prompt_type, build_generation_prompt)


def get_format_evaluator(task_type: str):
    """获取格式评估函数
    
    Args:
        task_type: 任务类型
        
    Returns:
        格式评估函数，如果任务类型不存在则返回通用评估函数
    """
    return FORMAT_EVALUATORS.get(task_type, _evaluate_general_format) 