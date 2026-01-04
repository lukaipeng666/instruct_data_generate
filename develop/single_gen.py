#!/usr/bin/env python3
"""
数据生成脚本
读取样本数据，使用本地大模型生成新数据，进行评估并保存合格的数据
"""

import json
import traceback
import os
import asyncio
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import sys
import random
import threading
from threading import Lock

# 线程局部随机数生成器，避免多线程共享全局随机状态
_thread_local = threading.local()


def _get_thread_random() -> random.Random:
    """
    获取线程局部的随机数生成器
    每个线程拥有独立的 Random 实例，避免多线程竞争
    """
    if not hasattr(_thread_local, 'rng'):
        _thread_local.rng = random.Random()
    return _thread_local.rng

# 导入工具函数
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.tools import (
    get_prompt_builder,
    get_format_evaluator
)
from config import get_default_services, get_default_model
# 导入模型调用函数
from call_model.model_call import call_model_api

# 从配置获取默认值
_default_api_base = get_default_services()[0] if get_default_services() else "http://localhost:16466/v1"
_default_model = get_default_model()


class DataGenerator:
    def __init__(self, 
                 api_base: str = None,
                 model: str = None,
                 max_concurrent: int = 5,
                 retry_times: int = 3,
                 min_score: int = 9,
                 task_type: str = "entity_extraction",
                 variants_per_sample: int = 3,
                 sample_retry_times: int = 3,
                 special_prompt: str = "",
                 directions: list = ["信用卡年费"],
                 api_key: str = "",
                 is_vllm: bool = True,
                 use_proxy: bool = False,
                 top_p: float = 1.0,
                 max_tokens: int = 8192,
                 timeout: int = 600):
        self.api_base = api_base or _default_api_base
        self.model = model or _default_model
        self.max_concurrent = max_concurrent
        self.retry_times = retry_times  # API调用重试次数
        self.sample_retry_times = sample_retry_times  # 样本处理重试次数
        self.min_score = min_score  # 最低分数要求
        self.task_type = task_type
        self.variants_per_sample = variants_per_sample
        
        # 模型调用相关参数
        self.api_key = api_key
        self.is_vllm = is_vllm
        self.use_proxy = use_proxy
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # 使用锁保护统计数据，确保多线程安全
        self._stats_lock = Lock()
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
        """初始化（保留兼容性）"""
        pass
    
    async def close_session(self):
        """关闭（保留兼容性）"""
        pass
    
    async def call_api(self, prompt: str, temperature: float = 0.6) -> Optional[str]:
        """调用模型API（使用 call_model 模块）"""
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            # 使用 call_model_api 进行调用（在线程池中运行同步函数）
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: call_model_api(
                    api_url=self.api_base,
                    api_key=self.api_key,
                    messages=messages,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=self.max_tokens,
                    retry_times=self.retry_times,
                    timeout=self.timeout,
                    is_vllm=self.is_vllm,
                    top_p=self.top_p,
                    use_proxy=self.use_proxy
                )
            )
            
            # 检查是否为错误响应
            if response and (response.startswith("模型调用失败") or 
                            response.startswith("API Connection Error") or
                            response.startswith("Rate Limit Error") or
                            response.startswith("代理调用失败")):
                print(f"API调用失败: {response}")
                with self._stats_lock:
                    self.stats['api_errors'] += 1
                return None
            
            return response.strip() if response else None
            
        except Exception as e:
            print(f"API调用异常: {type(e).__name__}: {str(e)}")
            print(f"详细堆栈: {traceback.format_exc()}")
            with self._stats_lock:
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
                        return data
                    elif isinstance(data, dict):
                        return [data]
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析失败: {e}")
            
            # 方法2: 尝试直接解析整个响应
            try:
                data = json.loads(response.strip())
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
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
                        return data
                except json.JSONDecodeError as e:
                    print(f"❌ 数组模式JSON解析失败: {e}")
            
            # 所有方法都失败
            print("❌ 未找到有效的JSON内容")
            return []
            
        except Exception as e:
            print(f"❌ 解析过程中出现异常: {type(e).__name__}: {e}")
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
                # 使用线程局部随机数生成器
                thread_rng = _get_thread_random()
                if self.directions == "验证码":
                    # 随机生成4位或6位数字验证码
                    length = thread_rng.choice([4, 6])
                    verification_code = ''.join(str(thread_rng.randint(0, 9)) for _ in range(length))
                    result = [f"随机生成的{length}位验证码：{verification_code}"]
                elif self.directions == "手机号码":
                    # 随机生成11位中国大陆手机号（首位固定为1，第二位常见为3/4/5/7/8）
                    first = '1'
                    second = thread_rng.choice(['3', '4', '5', '7', '8'])
                    rest = ''.join(str(thread_rng.randint(0, 9)) for _ in range(9))
                    phone_number = first + second + rest
                    result = [f"随机生成的11位手机号码：{phone_number}"]
                elif self.directions == "身份证号码":
                    # 随机生成18位身份证号（前6位地址码简化处理，第7-14位生日随机，最后1位可能为X）
                    address_code = ''.join(str(thread_rng.randint(0, 9)) for _ in range(6))  # 简化地址码
                    year = str(thread_rng.randint(1950, 2005))  # 随机年份
                    month = f"{thread_rng.randint(1, 12):02d}"  # 月份补0
                    day = f"{thread_rng.randint(1, 28):02d}"  # 日期简化处理（1-28）
                    birth_code = year + month + day
                    seq_code = ''.join(str(thread_rng.randint(0, 9)) for _ in range(3))  # 顺序码
                    last_code = thread_rng.choice([str(i) for i in range(10)] + ['X'])  # 校验码（可能为X）
                    id_card = address_code + birth_code + seq_code + last_code
                    result = [f"随机生成的18位身份证号码：{id_card}"]
                else:
                    num_length = thread_rng.randint(4, 35)
                    num_str = str(thread_rng.randint(1000, 10**num_length))
                    result = [f"随机生成的长度为{num_length}的数字{num_str}"]
            else:
                result = self.directions
            prompt = self.generation_prompt_builder(sample_data, self.variants_per_sample, self.special_prompt, result)
        
            # 调用API生成数据
            response = await self.call_api(prompt, temperature=0.3)
            if response is None:
                print("❌ 生成数据API调用失败")
                return []
            
            # 解析生成的数据
            generated_list = self.parse_generated_data(response, batch_idx, thread_idx, is_main_batch, is_main_thread)
            with self._stats_lock:
                self.stats['data_generated'] += len(generated_list)
            return generated_list
            
        except Exception as e:
            print(f"生成数据时出错: {str(e)}")
            return []
    
    async def evaluate_generated_data(self, sample_data: Dict[str, Any], generated_data: Dict[str, Any]) -> Tuple[int, int]:
        """评估生成的数据，返回(模型评分, 规则评分)"""
        try:
            # 获取Assistant的回答用于规则评估
            assistant_text = ""
            # 修复：turns应该是列表，默认值应该是[]而不是{}
            turns = generated_data.get('turns', [])
            
            if not isinstance(turns, list):
                print(f"❌ turns不是列表类型，跳过该数据")
                return 0, 0
            
            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                if turn.get('role') == 'Assistant':
                    assistant_text = turn.get('text', '')
                    break
            
            Assistant = 0
            Human = 0
            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                role = turn.get('role', '')
                # 处理role字段：去除首尾空格
                if isinstance(role, str):
                    role = role.strip()
                if role == 'Assistant':
                    Assistant += 1
                elif role == 'Human':
                    Human += 1
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
                            return 0, 0
                    if all(eval_response for eval_response in eval_response_list):
                        model_score_list = [self.parse_evaluation_score(eval_response) for eval_response in eval_response_list]
                        if all((model_score and model_score >= self.min_score) for model_score in model_score_list):
                            model_score = sum(model_score_list) / len(model_score_list)
                        else:
                            model_score = 0
                        if model_score is None:
                            model_score = 0
            with self._stats_lock:
                self.stats['data_evaluated'] += 1
            return model_score, rule_score
            
        except Exception as e:
            print(f"❌ 评估数据时出错: {str(e)}")
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
                    return model_score_, eval_response
            if all(eval_response for eval_response in eval_response_list):
                model_score_list = [self.parse_evaluation_score(eval_response) for eval_response in eval_response_list]
                if all((model_score and model_score >= self.min_score) for model_score in model_score_list):
                    model_score = sum(model_score_list) / len(model_score_list)
                else:
                    model_score = 0
                if model_score is None:
                    model_score = 0

            return model_score_, eval_response
            
        except Exception as e:
            print(f"❌ 评估数据时出错: {str(e)}")
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
                        with self._stats_lock:
                            self.stats['sample_retries'] += 1
                        continue
                    else:
                        return []
                
                # 评估每个生成的数据
                qualified_data = []
                
                for idx, generated_data in enumerate(generated_list):
                    if not isinstance(generated_data, dict):
                        continue
                    if 'turns' not in generated_data:
                        continue
                    
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
                        with self._stats_lock:
                            self.stats['data_passed'] += 1
                    else:
                        with self._stats_lock:
                            self.stats['data_failed'] += 1
                
                # 如果有合格数据，直接返回
                if qualified_data:
                    return qualified_data
                
                # 如果没有合格数据且还可以重试
                if retry_count < self.sample_retry_times - 1:
                    with self._stats_lock:
                        self.stats['sample_retries'] += 1
                    continue
                else:
                    return []
                
            except Exception as e:
                if retry_count < self.sample_retry_times - 1:
                    print(f"❌ 处理样本时出错: {str(e)}，重试中...")
                    with self._stats_lock:
                        self.stats['sample_retries'] += 1
                    continue
                else:
                    print(f"❌ 重试{self.sample_retry_times}次后仍然出错: {str(e)}")
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
                print(f"批处理中出现异常: {result}")
        
        return all_qualified_data
    
    async def generate_from_samples(self, samples: List[Dict[str, Any]], 
                                     batch_size: int = 5,
                                     task_id: str = None,
                                     user_id: int = None) -> Dict[str, Any]:
        """
        从内存中的样本数据生成数据并保存到数据库
        
        Args:
            samples: 样本数据列表
            batch_size: 批处理大小
            task_id: 任务ID（必需）
            user_id: 用户ID（必需）
            
        Returns:
            包含统计信息和生成结果的字典
        """
        print(f"📊 开始处理 {len(samples)} 个样本")
        
        # 验证必需参数
        if not task_id or not user_id:
            raise ValueError("保存到数据库时必须提供 task_id 和 user_id")
        
        # 重置统计数据
        self.stats['samples_read'] = len(samples)
        
        # 初始化会话
        await self.init_session()
        
        try:
            # 导入数据库服务
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from database import save_batch_generated_data
            
            
            # 分批处理
            all_qualified_data = []
            for i in range(0, len(samples), batch_size):
                batch = samples[i:i + batch_size]
                batch_idx = i // batch_size
                is_main_batch = (batch_idx == 0)  # 第一个批次为主批次
                print(f"📦 批次 {batch_idx + 1}/{(len(samples) + batch_size - 1)//batch_size}")
                
                # 处理当前批次
                batch_results = await self.process_batch(batch, batch_idx, is_main_batch)
                
                all_qualified_data.extend(batch_results)
                
                # 批量保存当前批次的数据到数据库
                if batch_results:
                    try:
                        saved_count = save_batch_generated_data(
                            task_id=task_id,
                            user_id=user_id,
                            data_list=batch_results,
                            generation_model=self.model.split('/')[-1],
                            task_type=self.task_type
                        )
                    except Exception as e:
                        print(f"❌ 保存批次 {batch_idx + 1} 数据失败: {e}")
                        raise e
                
            
            print(f"✅ 数据生成完成，共 {len(all_qualified_data)} 条合格数据")
            
            # 返回结果和统计信息
            return {
                'status': 'Success',
                'output_count': len(all_qualified_data),
                'qualified_data': all_qualified_data,
                'stats': self.stats.copy(),
                'task_id': task_id
            }
        
        except Exception as e:
            print(f"处理样本时出错: {str(e)}")
            return {
                'status': 'Failed',
                'error': str(e),
                'output_count': 0,
                'stats': self.stats.copy()
            }
        
        finally:
            await self.close_session()

async def main_process_from_samples(samples: List[Dict[str, Any]], 
                                     api_base: str, model: str, batch_size: int, 
                                     max_concurrent: int, retry_times: int, min_score: int, 
                                     task_type: str, variants_per_sample: int, 
                                     sample_retry_times: int, special_prompt: str, 
                                     directions: list, 
                                     task_id: str,
                                     user_id: int,
                                     api_key: str = "", 
                                     is_vllm: bool = True, use_proxy: bool = False,
                                     top_p: float = 1.0, max_tokens: int = 8192, 
                                     timeout: int = 600) -> Dict[str, Any]:
    """
    主处理函数 - 生成数据并保存到SQL数据库
    
    Args:
        samples: 样本数据列表
        api_base: API服务地址
        model: 模型名称
        batch_size: 批处理大小
        max_concurrent: 最大并发数
        retry_times: 重试次数
        min_score: 最低评分要求
        task_type: 任务类型
        variants_per_sample: 每个样本生成的变体数量
        sample_retry_times: 样本处理重试次数
        special_prompt: 特殊提示词
        directions: 生成方向列表
        task_id: 任务ID（必需）
        user_id: 用户ID（必需）
        api_key: API密钥
        is_vllm: 是否使用vLLM格式
        use_proxy: 是否使用代理
        top_p: top_p参数
        max_tokens: 最大token数
        timeout: 超时时间
        
    Returns:
        包含统计信息和生成结果的字典
    """
    try:
        if not samples:
            print("输入样本为空")
            return {"status": "Failed", "error": "输入样本为空", "output_count": 0}
        
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
            directions=directions,
            api_key=api_key,
            is_vllm=is_vllm,
            use_proxy=use_proxy,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout
        )
        
        # 开始生成数据（直接从内存中的样本）
        start_time = time.time()
        result = await generator.generate_from_samples(
            samples=samples,
            batch_size=batch_size,
            task_id=task_id,
            user_id=user_id
        )
        end_time = time.time()
        
        print(f"总耗时: {end_time - start_time:.2f} 秒")
        
        # 返回完整结果
        result['duration'] = end_time - start_time
        result['input_samples'] = len(samples)
        return result
        
    except Exception as e:
        print(f"处理过程出错: {str(e)}")
        return {"status": "Failed", "error": str(e), "output_count": 0}

# 注意：本模块的独立运行模式已废弃，请使用 main.py 入口调用