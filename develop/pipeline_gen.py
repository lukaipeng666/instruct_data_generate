#!/usr/bin/env python3
"""
分布式数据生成管道
将样本数据分配给多个本地模型服务同时处理，最大化数据生成速度
"""

import json
import os
import asyncio
import time
import yaml
import redis
from pathlib import Path
from typing import List, Dict, Any, Optional

# 导入新的模块
from develop.single_gen import main_process_from_samples
from develop.file_reader import FileReader


class PipelineDataGenerator:
    def __init__(self, services: List[str], model: str = "/data/models/Qwen3-32B",
                 api_key: str = "", is_vllm: bool = True, use_proxy: bool = True,
                 top_p: float = 1.0, max_tokens: int = 8192, timeout: int = 600):
        """
        初始化分布式数据生成器
        
        Args:
            services: API服务地址列表，如 ["http://localhost:6466/v1", ...]
            model: 模型名称
            api_key: API密钥（OpenAI格式需要）
            is_vllm: 是否使用vLLM格式
            use_proxy: 是否使用代理
            top_p: top_p参数
            max_tokens: 最大token数
            timeout: 超时时间
        """
        self.services = services
        self.model = model
        self.service_count = len(services)
        
        # 模型调用相关参数
        self.api_key = api_key
        self.is_vllm = is_vllm
        self.use_proxy = use_proxy
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # Redis 客户端（延迟初始化）
        self._redis_client = None
    
    def get_redis_client(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端（单例模式）"""
        if self._redis_client is None:
            try:
                config = self._get_yaml_config()
                redis_config = config.get('redis_service', {})
                host = redis_config.get('host', 'localhost')
                port = redis_config.get('port', 6379)
                db = redis_config.get('db', 0)
                password = redis_config.get('password', None)
                
                self._redis_client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True
                )
                # 测试连接
                self._redis_client.ping()
            except Exception as e:
                print(f"⚠️  Redis 连接失败: {e}，任务进度将不会记录到 Redis")
                self._redis_client = None
        return self._redis_client
    
    def _get_yaml_config(self) -> dict:
        """读取 YAML 配置文件"""
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def update_task_progress(self, task_id: str, progress_data: dict):
        """
        更新任务进度到 Redis
        
        Args:
            task_id: 任务ID
            progress_data: 进度数据字典
        """
        redis_client = self.get_redis_client()
        if redis_client:
            try:
                redis_key = f"task_progress:{task_id}"
                # 更新进度数据（JSON格式）
                redis_client.set(redis_key, json.dumps(progress_data, ensure_ascii=False))
                # 设置过期时间（24小时）
                redis_client.expire(redis_key, 86400)
            except Exception as e:
                print(f"⚠️  Redis 更新进度失败: {e}")
        
    def split_samples_in_memory(self, samples: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        在内存中将样本分配给各个服务（不写中间文件）
        
        Args:
            samples: 样本数据列表
            
        Returns:
            分配后的样本列表的列表
        """
        print(f"📊 内存中分配样本: 总数 {len(samples)}, 服务数 {self.service_count}")
        
        # 使用 FileReader 的静态方法进行分割
        parts = FileReader.split_samples_in_memory(samples, self.service_count)
        
        for i, part in enumerate(parts):
            print(f"  服务 {i+1}: 分配 {len(part)} 个样本")
        
        return parts
    
    async def process_single_service(self, service_idx: int, api_base: str, 
                                   samples: List[Dict[str, Any]],
                                   task_id: str, user_id: int,
                                   batch_size: int = 5, 
                                   max_concurrent: int = 5, min_score: int = 8,
                                   task_type: str = "entity_extraction",
                                   variants_per_sample: int = 3,
                                   sample_retry_times: int = 3,
                                   model: str = "/data/models/Qwen3-32B",
                                   retry_times: int = 3,
                                   special_prompt: str = "",
                                   directions: list = ["信用卡年费"],
                                   api_key: str = "",
                                   is_vllm: bool = True,
                                   use_proxy: bool = False,
                                   top_p: float = 1.0,
                                   max_tokens: int = 8192,
                                   timeout: int = 600) -> Dict[str, Any]:
        """
        处理单个服务的任务，数据直接保存到SQL数据库
        
        Args:
            service_idx: 服务索引
            api_base: API地址
            samples: 样本数据列表
            task_id: 任务ID
            user_id: 用户ID
            ...其他参数...
        """
        
        print(f"🚀 服务 {service_idx + 1} 开始生成数据: {api_base} (样本数: {len(samples)})")
        start_time = time.time()

        try:
            # 直接传递样本数据，保存到数据库
            result = await main_process_from_samples(
                samples=samples,
                task_id=task_id,
                user_id=user_id,
                api_base=api_base,
                model=model,
                batch_size=batch_size,
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
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 检查结果
            if result.get("status") == "Success":
                output_count = result.get('output_count', 0)
                print(f"✅ 服务 {service_idx + 1} 完成! 耗时: {duration:.1f}秒, 生成数据: {output_count}条")
                
                return {
                    'service_idx': service_idx,
                    'api_base': api_base,
                    'success': True,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'input_samples': len(samples),
                    'output_count': output_count,
                    'stats': result.get('stats', {})
                }
            else:
                error_msg = result.get('error', 'unknown error')
                print(f"❌ 服务 {service_idx + 1} 处理失败: {error_msg}")
                return {
                    'service_idx': service_idx, 
                    'api_base': api_base,
                    'success': False, 
                    'error': error_msg,
                    'input_samples': len(samples),
                    'output_count': 0
                }
                
        except Exception as e:
            print(f"❌ 服务 {service_idx + 1} 异常: {e}")
            return {
                'service_idx': service_idx, 
                'api_base': api_base,
                'success': False, 
                'error': str(e),
                'input_samples': len(samples),
                'output_count': 0
            }
    
    
    async def generate_data(self, task_id: str, user_id: int,
                          batch_size: int = 5, max_concurrent: int = 5,
                          min_score: int = 8, task_type: str = "entity_extraction",
                          variants_per_sample: int = 3, sample_retry_times: int = 3,
                          data_rounds: int = 3, model: str = "/data/models/Qwen3-32B",
                          retry_times: int = 3, special_prompt: str = "",
                          directions: list = ["信用卡年费"],
                          api_key: str = "", is_vllm: bool = True, use_proxy: bool = False,
                          top_p: float = 1.0, max_tokens: int = 8192, timeout: int = 600,
                          file_id: int = None):
        """
        生成数据，使用多个服务并行处理，支持多轮数据使用
        数据直接保存到SQL数据库
        
        Args:
            task_id: 任务ID（必需）
            user_id: 用户ID（必需）
            file_id: 输入文件ID（可选，如果不提供则使用task关联的文件）
            其他参数: 生成配置参数
            
        Returns:
            包含任务状态、生成数量等信息的字典
        """
        
        print("🚀 开始分布式数据生成")
        print(f"使用 {self.service_count} 个服务:")
        for i, service in enumerate(self.services):
            print(f"  服务 {i+1}: {service}")
        print(f"数据使用轮次: {data_rounds} 轮")
        
        total_start_time = time.time()
        
        # 1. 从数据库读取输入数据（一次性读入内存）
        print(f"\n📂 从数据库读取数据 (file_id={file_id}, user_id={user_id})")
        samples, read_errors = FileReader.read_samples(file_id=file_id, user_id=user_id)
        
        if read_errors:
            print(f"⚠️ 读取时有 {len(read_errors)} 个错误")
        print(f"✅ 读取完成: {len(samples)} 个样本")
        
        if not samples:
            print("❌ 没有有效样本，退出")
            return {
                'status': 'Failed',
                'error': 'No valid samples',
                'total_generated': 0
            }
        
        # 2. 存储所有轮次的结果统计
        total_generated_count = 0
        
        # 初始化任务进度
        self.update_task_progress(task_id, {
            'task_id': task_id,
            'status': 'running',
            'current_round': 0,
            'total_rounds': data_rounds,
            'total_samples': len(samples),
            'generated_count': 0,
            'start_time': total_start_time,
            'services': self.service_count
        })
        
        # 3. 多轮数据处理
        for round_num in range(data_rounds):
            print(f"\n🔄 第 {round_num + 1}/{data_rounds} 轮数据生成")
            
            # 更新 Redis 进度：当前轮次开始
            self.update_task_progress(task_id, {
                'task_id': task_id,
                'status': 'running',
                'current_round': round_num + 1,
                'total_rounds': data_rounds,
                'total_samples': len(samples),
                'generated_count': total_generated_count,
                'start_time': total_start_time,
                'services': self.service_count,
                'round_status': 'processing'
            })
            
            # 3.1 在内存中分配样本给各个服务
            sample_parts = self.split_samples_in_memory(samples)
            
            # 3.2 创建并行任务
            print(f"⚡ 并行生成 ({self.service_count} 个服务)")
            tasks = []
            
            for i, (service, sample_part) in enumerate(zip(self.services, sample_parts)):
                if not sample_part:
                    print(f"  服务 {i+1}: 没有分配到样本，跳过")
                    continue
                
                task = self.process_single_service(
                    service_idx=i,
                    api_base=service,
                    samples=sample_part,
                    task_id=task_id,
                    user_id=user_id,
                    batch_size=batch_size,
                    max_concurrent=max_concurrent,
                    min_score=min_score,
                    task_type=task_type,
                    variants_per_sample=variants_per_sample,
                    sample_retry_times=sample_retry_times,
                    model=model,
                    retry_times=retry_times,
                    special_prompt=special_prompt,
                    directions=directions,
                    api_key=api_key if api_key else self.api_key,
                    is_vllm=is_vllm if is_vllm is not None else self.is_vllm,
                    use_proxy=use_proxy if use_proxy is not None else self.use_proxy,
                    top_p=top_p if top_p else self.top_p,
                    max_tokens=max_tokens if max_tokens else self.max_tokens,
                    timeout=timeout if timeout else self.timeout
                )
                tasks.append(task)
            
            # 3.3 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 3.4 统计本轮结果
            print("📈 本轮结果统计")
            round_output_count = 0
            round_errors = 0
            
            for result in results:
                if isinstance(result, dict):
                    if result.get('success'):
                        round_output_count += result.get('output_count', 0)
                    else:
                        round_errors += 1
                elif isinstance(result, Exception):
                    print(f"❌ 任务异常: {result}")
                    round_errors += 1
            
            total_generated_count += round_output_count
            
            # 更新 Redis 进度：当前轮次完成
            round_completion = ((round_num + 1) / data_rounds) * 100
            self.update_task_progress(task_id, {
                'task_id': task_id,
                'status': 'running',
                'current_round': round_num + 1,
                'total_rounds': data_rounds,
                'total_samples': len(samples),
                'generated_count': total_generated_count,
                'start_time': total_start_time,
                'services': self.service_count,
                'round_status': 'completed',
                'round_output': round_output_count,
                'round_errors': round_errors,
                'completion_percent': round(round_completion, 2)  # 完成百分比
            })
            
            print(f"第 {round_num + 1} 轮完成: 生成 {round_output_count} 条数据")
        
        # 4. 计算总耗时
        total_duration = time.time() - total_start_time
        
        # 计算完成百分比（100%表示已完成）
        completion_percent = 100.0
        
        # 更新 Redis 进度：任务完成
        self.update_task_progress(task_id, {
            'task_id': task_id,
            'status': 'completed',
            'current_round': data_rounds,
            'total_rounds': data_rounds,
            'total_samples': len(samples),
            'generated_count': total_generated_count,
            'start_time': total_start_time,
            'end_time': time.time(),
            'duration': total_duration,
            'services': self.service_count,
            'completion_percent': completion_percent  # 完成百分比
        })
        
        print(f"\n🏆 多轮数据生成任务完成!")
        print(f"  总耗时: {total_duration:.1f}秒")
        print(f"  总生成数据: {total_generated_count} 条")
        
        return {
            'status': 'Success',
            'task_id': task_id,
            'total_generated': total_generated_count,
            'total_rounds': data_rounds,
            'total_duration': total_duration,
            'completion_percent': completion_percent  # 添加完成百分比到返回值
        }
