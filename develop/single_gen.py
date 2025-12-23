#!/usr/bin/env python3
"""
数据生成脚本
读取样本数据，使用本地大模型生成新数据，进行评估并保存合格的数据
"""

import json
import traceback
import os
import argparse
import asyncio
import aiohttp
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path
import sys
import random

# 导入工具函数
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tools import (
    get_prompt_builder,
    get_format_evaluator
)

# 配置日志
os.makedirs('log', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/data_generation_.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataGenerator:
    def __init__(self, 
                 api_base: str = "http://localhost:6466/v1",
                 model: str = "/data/models/Qwen3-32B",
                 max_concurrent: int = 5,
                 retry_times: int = 3,
                 min_score: int = 9,
                 task_type: str = "entity_extraction",
                 variants_per_sample: int = 3,
                 sample_retry_times: int = 3,
                 special_prompt: str = "",
                 directions: list = ["信用卡年费"]):
        self.api_base = api_base
        self.model = model
        self.max_concurrent = max_concurrent
        self.retry_times = retry_times  # API调用重试次数
        self.sample_retry_times = sample_retry_times  # 样本处理重试次数
        self.min_score = min_score  # 最低分数要求
        self.task_type = task_type
        self.variants_per_sample = variants_per_sample
        self.session = None
        self.stats = {
            'samples_read': 0,
            'data_generated': 0,
            'data_evaluated': 0,
            'data_passed': 0,
            'data_failed': 0,
            'api_errors': 0,
            'sample_retries': 0  # 新增：样本重试次数统计
        }
        
        # 获取可配置的函数
        self.generation_prompt_builder = get_prompt_builder('generation')
        self.evaluation_prompt_builder = get_prompt_builder('evaluation')
        self.format_evaluator = get_format_evaluator(task_type)
        self.filter_prompt = get_prompt_builder('filter')
        self.special_prompt = special_prompt
        self.directions = directions
    
    async def init_session(self):
        """初始化HTTP会话"""
        timeout = aiohttp.ClientTimeout(total=600)  
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
    
    async def call_api(self, prompt: str, temperature: float = 0.6) -> Optional[str]:
        """调用本地API"""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": 8096,
            "stream": True
        }
        
        full_response = ""
        for attempt in range(self.retry_times):
            try:
                async with self.session.post(
                    f"{self.api_base}/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning(f"API调用失败 (状态码: {response.status}): {error_text}")
                        if attempt < self.retry_times - 1:
                            await asyncio.sleep(2 ** attempt)
                        continue

                    async for line in response.content:
                        line = line.strip().decode('utf-8')
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                return full_response.strip()
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_response += delta
                                    # print(delta, end="", flush=True)
                            except (KeyError, json.JSONDecodeError) as e:
                                logger.debug(f"解析流数据失败: {data_str}")
                                continue
                    return full_response.strip()

            except asyncio.TimeoutError:
                logger.warning(f"API调用超时 (尝试 {attempt + 1}/{self.retry_times})")
            except aiohttp.ClientConnectorError as e:
                logger.warning(f"连接错误 (尝试 {attempt + 1}/{self.retry_times}): {e!r}")
            except aiohttp.ServerDisconnectedError:
                logger.warning(f"服务器断开连接 (尝试 {attempt + 1}/{self.retry_times})")
            except aiohttp.ClientResponseError as e:
                logger.warning(f"响应错误 (状态码: {e.status}): {e.message}")
            except Exception as e:
                logger.warning(f"未预期异常 {type(e).__name__} (尝试 {attempt + 1}/{self.retry_times}): {str(e) or repr(e)}")
                logger.debug(f"详细堆栈: {traceback.format_exc()}")

            if attempt < self.retry_times - 1:
                await asyncio.sleep(2 ** attempt)
        
        self.stats['api_errors'] += 1
        return None
    
    def parse_generated_data(self, response: str, batch_idx: int = None, thread_idx: int = None, is_main_batch: bool = False, is_main_thread: bool = False) -> List[Dict[str, Any]]:
        """解析生成的数据
        
        Args:
            response: 模型输出的原始响应
            batch_idx: 批次索引（从0开始）
            thread_idx: 线程/样本索引（从0开始）
            is_main_batch: 是否为主批次（第一个批次）
            is_main_thread: 是否为主线程（第一个样本）
        """
        # 尝试提取JSON内容
        try:
            # 方法1: 查找JSON代码块
            # 注意：使用贪婪匹配(.*)而不是非贪婪匹配(.*?)
            # 因为模型输出的text字段中可能包含```符号，非贪婪匹配会过早结束
            json_pattern = r'```json\s*(.*)\s*```'
            json_match = re.search(json_pattern, response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                try:
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        logger.info("✅ 成功解析JSON数组")
                        logger.info(f"📊 解析后的数据长度: {len(data)}")
                        if len(data) > 0:
                            logger.info(f"📊 第一个元素的结构: {json.dumps(data[0], ensure_ascii=False, indent=2)[:300]}")
                        return data
                    elif isinstance(data, dict):
                        logger.info("✅ 成功解析JSON对象（转换为列表）")
                        return [data]
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析失败: {e}")
            
            # 方法2: 尝试直接解析整个响应
            try:
                data = json.loads(response.strip())
                if isinstance(data, list):
                    logger.info("✅ 成功解析整个响应为JSON数组")
                    return data
                elif isinstance(data, dict):
                    logger.info("✅ 成功解析整个响应为JSON对象（转换为列表）")
                    return [data]
            except json.JSONDecodeError:
                pass
            
            # 方法3: 查找以[开头]结尾的数组
            # 使用贪婪匹配(.*)匹配到最后一个]，避免嵌套数组匹配错误
            array_pattern = r'\[.*\]'
            array_match = re.search(array_pattern, response, re.DOTALL)
            if array_match:
                array_str = array_match.group(0)
                try:
                    data = json.loads(array_str)
                    if isinstance(data, list):
                        logger.info("✅ 成功从数组模式提取并解析JSON")
                        return data
                except json.JSONDecodeError as e:
                    logger.warning(f"数组模式JSON解析失败: {e}")
            
            # 所有方法都失败
            logger.warning("未找到有效的JSON内容")
            # 如果是主批次的主线程，打印详细日志
            if is_main_batch and is_main_thread:
                logger.error("=" * 80)
                logger.error("【主批次主线程】模型输出解析失败 - 详细日志")
                logger.error(f"批次索引: {batch_idx}, 线程索引: {thread_idx}")
                logger.error("所有解析方法均失败")
                logger.error("=" * 80)
                logger.error("完整模型输出:")
                logger.error(response)
                logger.error("=" * 80)
                # 尝试分析问题
                if "```json" in response:
                    logger.error("检测到```json标记，但内容无法解析")
                elif "[" in response and "]" in response:
                    logger.error("检测到数组标记[]，但内容无法解析")
                else:
                    logger.error("未检测到JSON格式标记")
            return []
            
        except Exception as e:
            logger.warning(f"解析过程中出现异常: {e}")
            # 如果是主批次的主线程，打印详细日志
            if is_main_batch and is_main_thread:
                logger.error("=" * 80)
                logger.error("【主批次主线程】模型输出解析异常 - 详细日志")
                logger.error(f"批次索引: {batch_idx}, 线程索引: {thread_idx}")
                logger.error(f"异常类型: {type(e).__name__}")
                logger.error(f"异常信息: {e}")
                logger.error("=" * 80)
                logger.error("完整模型输出:")
                logger.error(response)
                logger.error("=" * 80)
            return []

    def parse_evaluation_score(self, response: str) -> Optional[int]:
        """解析评估分数"""
        import re
        
        # 优先查找\\boxed{}格式的评分
        boxed_pattern = r'\\boxed\{(\d+)\}'
        boxed_match = re.search(boxed_pattern, response)
        if boxed_match:
            score = int(boxed_match.group(1))
            if 0 <= score <= 10:
                return score
        
        # 备用方案：查找最后一行的数字评分
        lines = response.strip().split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line.isdigit() and 0 <= int(line) <= 10:
                return int(line)
        
        return None
    
    async def generate_data_from_sample(self, sample_data: Dict[str, Any], batch_idx: int = None, thread_idx: int = None, is_main_batch: bool = False, is_main_thread: bool = False) -> List[Dict[str, Any]]:
        """根据样本数据生成新数据
        
        Args:
            sample_data: 样本数据
            batch_idx: 批次索引（从0开始）
            thread_idx: 线程/样本索引（从0开始）
            is_main_batch: 是否为主批次（第一个批次）
            is_main_thread: 是否为主线程（第一个样本）
        """
        try:
            # 构建生成提示
            if self.task_type == "calculation":
                if self.directions == "验证码":
                    # 随机生成4位或6位数字验证码
                    length = random.choice([4, 6])
                    verification_code = ''.join(str(random.randint(0, 9)) for _ in range(length))
                    result = [f"随机生成的{length}位验证码：{verification_code}"]
                elif self.directions == "手机号码":
                    # 随机生成11位中国大陆手机号（首位固定为1，第二位常见为3/4/5/7/8）
                    first = '1'
                    second = random.choice(['3', '4', '5', '7', '8'])
                    rest = ''.join(str(random.randint(0, 9)) for _ in range(9))
                    phone_number = first + second + rest
                    result = [f"随机生成的11位手机号码：{phone_number}"]
                elif self.directions == "身份证号码":
                    # 随机生成18位身份证号（前6位地址码简化处理，第7-14位生日随机，最后1位可能为X）
                    address_code = ''.join(str(random.randint(0, 9)) for _ in range(6))  # 简化地址码
                    year = str(random.randint(1950, 2005))  # 随机年份
                    month = f"{random.randint(1, 12):02d}"  # 月份补0
                    day = f"{random.randint(1, 28):02d}"  # 日期简化处理（1-28）
                    birth_code = year + month + day
                    seq_code = ''.join(str(random.randint(0, 9)) for _ in range(3))  # 顺序码
                    last_code = random.choice([str(i) for i in range(10)] + ['X'])  # 校验码（可能为X）
                    id_card = address_code + birth_code + seq_code + last_code
                    result = [f"随机生成的18位身份证号码：{id_card}"]
                else:
                    num_length = random.randint(4, 35)
                    num_str = str(random.randint(1000, 10**num_length))
                    result = [f"随机生成的长度为{num_length}的数字{num_str}"]
            else:
                result = self.directions
            prompt = self.generation_prompt_builder(sample_data, self.variants_per_sample, self.special_prompt, result)
        
            # 调用API生成数据
            response = await self.call_api(prompt, temperature=0.3)
            if response is None:
                logger.error("生成数据API调用失败")
                return []
            
            # 如果是主批次的主线程，打印模型输出
            if is_main_batch and is_main_thread:
                logger.info("=" * 80)
                logger.info("【主批次主线程】模型原始输出")
                logger.info(f"批次索引: {batch_idx}, 线程索引: {thread_idx}")
                logger.info("=" * 80)
                logger.info(response)
                logger.info("=" * 80)
            
            # 解析生成的数据
            generated_list = self.parse_generated_data(response, batch_idx, thread_idx, is_main_batch, is_main_thread)
            logger.info(f"📊 解析结果：generated_list长度={len(generated_list)}")
            if generated_list:
                logger.info(f"📊 第一个generated_data的结构: {json.dumps(generated_list[0] if len(generated_list) > 0 else {}, ensure_ascii=False, indent=2)[:500]}")
            self.stats['data_generated'] += len(generated_list)
            return generated_list
            
        except Exception as e:
            logger.error(f"生成数据时出错: {str(e)}")
            return []
    
    async def evaluate_generated_data(self, sample_data: Dict[str, Any], generated_data: Dict[str, Any]) -> Tuple[int, int]:
        """评估生成的数据，返回(模型评分, 规则评分)"""
        try:
            # 获取Assistant的回答用于规则评估
            assistant_text = ""
            # 修复：turns应该是列表，默认值应该是[]而不是{}
            turns = generated_data.get('turns', [])
            
            # 添加调试日志：检查turns的类型和内容
            if not isinstance(turns, list):
                logger.error(f"⚠️ 警告：turns不是列表类型！类型: {type(turns)}, 值: {turns}")
                logger.error(f"generated_data结构: {json.dumps(generated_data, ensure_ascii=False, indent=2)}")
                return 0, 0
            
            for turn in turns:
                if not isinstance(turn, dict):
                    logger.error(f"⚠️ 警告：turn不是字典类型！类型: {type(turn)}, 值: {turn}")
                    continue
                if turn.get('role') == 'Assistant':
                    assistant_text = turn.get('text', '')
                    break
            
            Assistant = 0
            Human = 0
            for turn_idx, turn in enumerate(turns):
                if not isinstance(turn, dict):
                    logger.warning(f"⚠️ turn[{turn_idx}]不是字典: {type(turn)}, 值: {turn}")
                    continue
                role = turn.get('role', '')
                # 处理role字段：去除首尾空格，统一大小写
                if isinstance(role, str):
                    role = role.strip()
                # 添加调试：打印每个turn的role
                logger.info(f"🔍 调试：turn[{turn_idx}]的role='{role}' (原始值: '{turn.get('role', '')}', 类型: {type(role)})")
                if role == 'Assistant':
                    Assistant += 1
                    logger.info(f"  ✅ 找到Assistant，当前计数: {Assistant}")
                elif role == 'Human':
                    Human += 1
                    logger.info(f"  ✅ 找到Human，当前计数: {Human}")
                    human_content = turn.get('text')
                    if human_content:
                        human_content = human_content.strip()
                        human_content = human_content.split("\n")
                else:
                    logger.warning(f"⚠️ turn[{turn_idx}]未知的role值: '{role}' (原始值: '{turn.get('role', '')}', 类型: {type(role)})")
                    logger.warning(f"  turn完整内容: {json.dumps(turn, ensure_ascii=False)}")
                    # if human_content[-1][:6] != "客户当前输入":
                    #     print("'客户当前输入'不在内容范围内")
                    #     return 0, 0
            # 规则评分
            rule_score = 0
            model_score = 0
            if Assistant == 1 and Human == 1:
                rule_score = self.format_evaluator(assistant_text)
                if rule_score == 10:
                    # 模型评分
                    eval_prompt = self.evaluation_prompt_builder(sample_data, generated_data, self.special_prompt)
                    eval_response_list = []
                    for _ in range(1):
                        eval_response = await self.call_api(eval_prompt, temperature=0.2)
                        eval_response_list.append(eval_response)
                        model_score_ = self.parse_evaluation_score(eval_response)
                        if (model_score_ and model_score_ < self.min_score) or not model_score_:
                            logger.warning(f"模型评估存在低于{self.min_score}分或缺失打分的情况，默认评分0分")
                            return 0, 0
                    if all(eval_response for eval_response in eval_response_list):
                        model_score_list = [self.parse_evaluation_score(eval_response) for eval_response in eval_response_list]
                        if all((model_score and model_score >= self.min_score) for model_score in model_score_list):
                            model_score = sum(model_score_list) / len(model_score_list)
                        else:
                            model_score = 0
                            logger.warning(f"模型评估存在低于{self.min_score}分或缺失打分的情况，默认评分0分")
                        if model_score is None:
                            model_score = 0
                            logger.warning("模型评估解析失败，默认评分0分")
                    else:
                        logger.warning("模型评估API调用失败，默认评分0分")
                else:
                    logger.warning("输出不符合规则，模型默认评分0分")
            else:
                logger.warning("生成的对话不全")
                logger.warning(f"Assistant的数量为:{Assistant}, Human的数量为:{Human}")
            self.stats['data_evaluated'] += 1
            return model_score, rule_score
            
        except Exception as e:
            logger.error(f"评估数据时出错: {str(e)}\n错误的数据是:{json.dumps(generated_data, indent=4, ensure_ascii=False)}")
            return 0, 0
    

    async def evaluate_data(self, content: str) -> int:
        """评估生成的数据，返回(模型评分, 规则评分)"""
        try:
            model_score = 0

            # 模型评分
            eval_prompt = self.filter_prompt(content)
            eval_response_list = []
            for _ in range(1):
                eval_response = await self.call_api(eval_prompt, temperature=0.2)
                eval_response_list.append(eval_response)
                model_score_ = self.parse_evaluation_score(eval_response)
                if (model_score_ and model_score_ < self.min_score) or not model_score_:
                    logger.warning(f"模型评估存在低于{self.min_score}分或缺失打分的情况，默认评分0分")
                    return model_score_, eval_response
            if all(eval_response for eval_response in eval_response_list):
                model_score_list = [self.parse_evaluation_score(eval_response) for eval_response in eval_response_list]
                if all((model_score and model_score >= self.min_score) for model_score in model_score_list):
                    model_score = sum(model_score_list) / len(model_score_list)
                else:
                    model_score = 0
                    logger.warning(f"模型评估存在低于{self.min_score}分或缺失打分的情况，默认评分0分")
                if model_score is None:
                    model_score = 0
                    logger.warning("模型评估解析失败，默认评分0分")
            else:
                logger.warning("模型评估API调用失败，默认评分0分")

            return model_score_, eval_response
            
        except Exception as e:
            logger.error(f"评估数据时出错: {str(e)}")
            return 0, "评分时出错"
    
    async def process_single_sample(self, sample_data: Dict[str, Any], batch_idx: int = None, thread_idx: int = None, is_main_batch: bool = False, is_main_thread: bool = False) -> List[Dict[str, Any]]:
        """处理单个样本，生成并评估数据，如果没有合格数据则重试
        
        Args:
            sample_data: 样本数据
            batch_idx: 批次索引（从0开始）
            thread_idx: 线程/样本索引（从0开始）
            is_main_batch: 是否为主批次（第一个批次）
            is_main_thread: 是否为主线程（第一个样本）
        """
        for retry_count in range(self.sample_retry_times):
            try:
                # 生成数据
                generated_list = await self.generate_data_from_sample(sample_data, batch_idx, thread_idx, is_main_batch, is_main_thread)
                
                if not generated_list:
                    if retry_count < self.sample_retry_times - 1:
                        logger.warning(f"未能生成有效数据，准备重试 ({retry_count + 1}/{self.sample_retry_times})")
                        self.stats['sample_retries'] += 1
                        continue
                    else:
                        logger.warning(f"重试{self.sample_retry_times}次后仍未能生成有效数据")
                        return []
                
                # 评估每个生成的数据
                qualified_data = []
                
                for idx, generated_data in enumerate(generated_list):
                    # 添加调试日志：检查generated_data的结构
                    if not isinstance(generated_data, dict):
                        logger.error(f"⚠️ 警告：generated_data[{idx}]不是字典类型！类型: {type(generated_data)}, 值: {generated_data}")
                        continue
                    if 'turns' not in generated_data:
                        logger.error(f"⚠️ 警告：generated_data[{idx}]中没有'turns'字段！")
                        logger.error(f"generated_data结构: {json.dumps(generated_data, ensure_ascii=False, indent=2)}")
                        continue
                    
                    # 添加详细调试日志：打印turns的内容
                    turns = generated_data.get('turns', [])
                    logger.info(f"🔍 调试：generated_data[{idx}]的turns内容:")
                    logger.info(f"  turns类型: {type(turns)}, 长度: {len(turns) if isinstance(turns, list) else 'N/A'}")
                    if isinstance(turns, list):
                        for turn_idx, turn in enumerate(turns):
                            logger.info(f"  turn[{turn_idx}]: {json.dumps(turn, ensure_ascii=False)}")
                    else:
                        logger.error(f"  turns不是列表！值: {turns}")
                    
                    model_score, rule_score = await self.evaluate_generated_data(sample_data, generated_data)
                    
                    # 检查是否达到最低分数要求：规则评分必须满分，模型评分达到最低要求
                    if model_score >= self.min_score and rule_score == 10:
                        # 构建完整的数据结构
                        complete_data = {
                            'meta': sample_data.get('meta', {}).copy(),
                            'turns': generated_data.get('turns', [])
                        }
                        
                        # 添加生成元数据
                        complete_data['meta']['generated'] = True
                        complete_data['meta']['generation_model'] = self.model.split('/')[-1]
                        complete_data['meta']['generation_time'] = datetime.now().isoformat()
                        complete_data['meta']['model_score'] = model_score
                        complete_data['meta']['rule_score'] = rule_score
                        complete_data['meta']['source_task'] = self.task_type
                        complete_data['meta']['retry_count'] = retry_count  # 记录重试次数
                        
                        qualified_data.append(complete_data)
                        self.stats['data_passed'] += 1
                        logger.info(f"数据通过评估 - 模型评分: {model_score}, 规则评分: {rule_score} (重试次数: {retry_count})")
                    else:
                        self.stats['data_failed'] += 1
                        if rule_score != 10:
                            logger.info(f"数据未通过评估 - 规则评分未满分: {rule_score} (需要10分), 模型评分: {model_score}")
                        else:
                            logger.info(f"数据未通过评估 - 模型评分不足: {model_score} (需要≥{self.min_score}), 规则评分: {rule_score}")
                
                # 如果有合格数据，直接返回
                if qualified_data:
                    return qualified_data
                
                # 如果没有合格数据且还可以重试
                if retry_count < self.sample_retry_times - 1:
                    logger.warning(f"本轮未产生合格数据，准备重试 ({retry_count + 1}/{self.sample_retry_times})")
                    self.stats['sample_retries'] += 1
                    continue
                else:
                    logger.warning(f"重试{self.sample_retry_times}次后仍未产生合格数据")
                    return []
                
            except Exception as e:
                if retry_count < self.sample_retry_times - 1:
                    logger.error(f"处理样本时出错: {str(e)}，准备重试 ({retry_count + 1}/{self.sample_retry_times})")
                    self.stats['sample_retries'] += 1
                    continue
                else:
                    logger.error(f"重试{self.sample_retry_times}次后仍然出错: {str(e)}")
                    return []
        
        return []
    
    async def process_batch(self, samples: List[Dict[str, Any]], batch_idx: int = None, is_main_batch: bool = False) -> List[Dict[str, Any]]:
        """批量处理样本
        
        Args:
            samples: 样本列表
            batch_idx: 批次索引（从0开始）
            is_main_batch: 是否为主批次（第一个批次）
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(sample, thread_idx):
            async with semaphore:
                # 判断是否为主线程（第一个样本）
                is_main_thread = (thread_idx == 0)
                return await self.process_single_sample(sample, batch_idx, thread_idx, is_main_batch, is_main_thread)
        
        tasks = [process_with_semaphore(sample, idx) for idx, sample in enumerate(samples)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 收集所有合格的数据
        all_qualified_data = []
        for result in results:
            if isinstance(result, list):
                all_qualified_data.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"批处理中出现异常: {result}")
        
        return all_qualified_data
    
    async def generate_from_file(self, input_file: str, output_file: str, batch_size: int = 5):
        """从文件生成数据"""
        logger.info(f"开始从文件生成数据: {input_file}")
        
        # 初始化会话
        await self.init_session()
        
        try:
            # 读取样本文件
            samples = []
            with open(input_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line.strip())
                        samples.append(data)
                        self.stats['samples_read'] += 1
                    except json.JSONDecodeError as e:
                        logger.warning(f"第{line_num}行JSON解析失败: {e}")
            
            logger.info(f"共读取 {len(samples)} 个样本")
            
            # 创建输出文件
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 分批处理
            all_qualified_data = []
            with open(output_file, 'w', encoding='utf-8') as out_f:
                for i in range(0, len(samples), batch_size):
                    batch = samples[i:i + batch_size]
                    batch_idx = i // batch_size
                    is_main_batch = (batch_idx == 0)  # 第一个批次为主批次
                    logger.info(f"处理批次 {batch_idx + 1}/{(len(samples) + batch_size - 1)//batch_size}")
                    
                    # 处理当前批次
                    batch_results = await self.process_batch(batch, batch_idx, is_main_batch)
                    
                    # 立即写入合格的数据
                    for qualified_data in batch_results:
                        json_line = json.dumps(qualified_data, ensure_ascii=False)
                        out_f.write(json_line + '\n')
                    
                    all_qualified_data.extend(batch_results)
                    
                    # 显示进度
                    progress = (i + len(batch)) / len(samples) * 100
                    logger.info(f"进度: {progress:.1f}% (已生成合格数据: {len(all_qualified_data)} 条)")
            
            logger.info(f"数据生成完成! 统计: {self.stats}")
            logger.info(f"输出文件: {output_file}")
            logger.info(f"总计生成合格数据: {len(all_qualified_data)} 条")
        
        finally:
            await self.close_session()


def test_api_connection(api_base: str) -> bool:
    """测试API连接"""
    import requests
    try:
        response = requests.get(f"{api_base}/models", timeout=10)
        if response.status_code == 200:
            models = response.json()
            logger.info(f"API连接成功，可用模型: {[m['id'] for m in models.get('data', [])]}")
            return True
        else:
            logger.error(f"API连接失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"API连接测试失败: {e}")
        return False


async def main_process(input_file, output_file, api_base, model, batch_size, max_concurrent, retry_times, min_score, task_type, variants_per_sample, sample_retry_times, special_prompt, directions):
    
    try:
        # 检查输入文件
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return
        
        # 测试API连接
        logger.info("测试API连接...")
        if not test_api_connection(api_base):
            logger.error("API连接失败，请检查服务是否正常运行")
            return
        
        # 创建数据生成器
        generator = DataGenerator(
            api_base=api_base,
            model=model,
            max_concurrent=max_concurrent,
            retry_times=retry_times,
            min_score=min_score,
            task_type=task_type,
            variants_per_sample=variants_per_sample,
            sample_retry_times=sample_retry_times,
            special_prompt=special_prompt,
            directions=directions
        )
        
        # 开始生成数据
        start_time = time.time()
        await generator.generate_from_file(input_file, output_file, batch_size)
        end_time = time.time()
        
        logger.info(f"总耗时: {end_time - start_time:.2f} 秒")

        return {"status": "Sucessed"}
    except Exception as e:
        return {"status": "Failed"}

def main():
    parser = argparse.ArgumentParser(description='使用本地大模型生成新的对话数据')
    parser.add_argument('--input_file', help='输入的样本JSONL文件路径')
    parser.add_argument('--output_file', '-o', required=True, help='输出的JSONL文件路径')
    parser.add_argument('--api-base', default='http://localhost:6466/v1', help='API服务地址')
    parser.add_argument('--model', default='/data/models/Qwen3-32B', help='模型名称')
    parser.add_argument('--batch-size', type=int, default=1, help='批处理大小')
    parser.add_argument('--max-concurrent', type=int, default=5, help='最大并发数')
    parser.add_argument('--retry-times', type=int, default=3, help='重试次数')
    parser.add_argument('--min-score', type=int, default=8, help='最低评分要求(0-10)')
    parser.add_argument('--task-type', default='entity_extraction', help='任务类型')
    parser.add_argument('--variants-per-sample', type=int, default=1, help='每个样本生成的变体数量')
    parser.add_argument('--sample-retry-times', type=int, default=1, help='样本处理重试次数')
    
    args = parser.parse_args()
    asyncio.run(main_process(args.input_file, args.output, args.api_base, args.model, args.batch_size, args.max_concurrent, args.retry_times, args.min_score, args.task_type, args.variants_per_sample, args.sample_retry_times)) 


if __name__ == "__main__":
    # 运行异步主函数
    main()