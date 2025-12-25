#!/usr/bin/env python3
"""
分布式数据生成管道 - 主入口
"""

import os
import time
import argparse
import asyncio
from develop.pipeline_gen import PipelineDataGenerator


async def main():
    # 默认服务列表
    default_services = [
        "http://localhost:6466/v1",
        "http://localhost:6467/v1",
        "http://localhost:6468/v1",
        "http://localhost:6469/v1",
        "http://localhost:6470/v1",
        "http://localhost:6471/v1",
        "http://localhost:6472/v1",
        "http://localhost:6473/v1"
    ]
    
    parser = argparse.ArgumentParser(description='分布式并行生成对话数据')
    parser.add_argument('--services', nargs='+', default=default_services, help='API服务地址列表')
    parser.add_argument('--model', default='/data/models/Qwen3-32B', help='模型名称')
    parser.add_argument('--batch-size', type=int, default=16, help='每个服务的批处理大小')
    parser.add_argument('--max-concurrent', type=int, default=16, help='每个服务的最大并发数')
    parser.add_argument('--min-score', type=int, default=8, help='最低评分要求(0-10)')
    parser.add_argument('--task-type', default='entity_extraction', help='任务类型')
    parser.add_argument('--variants-per-sample', type=int, default=3, help='每个样本生成的变体数量')
    parser.add_argument('--data-rounds', type=int, default=10, help='数据使用轮次')
    parser.add_argument('--retry-times', default=3, type=int, help='重试次数')
    parser.add_argument('--special-prompt', default="", type=str, help='特殊任务提示词')
    parser.add_argument('--directions', nargs='*', default=['信用卡年费', '股票爆仓', '基金赎回'],help='需要构造的题材，可输入多个，如：--directions 信用卡年费 股票爆仓')
    parser.add_argument('--output', default='', type=str, help='输出文件名（已弃用，保留用于兼容）')
    
    # 模型调用相关参数
    parser.add_argument('--api-key', default="", type=str, help='API密钥（OpenAI格式需要）')
    parser.add_argument('--is-vllm', action='store_true', default=True, help='是否使用vLLM格式（默认True）')
    parser.add_argument('--no-vllm', action='store_false', dest='is_vllm', help='不使用vLLM格式')
    parser.add_argument('--use-proxy', action='store_true', default=True, help='是否使用代理（默认False）')
    parser.add_argument('--top-p', type=float, default=1.0, help='top_p参数（默认1.0）')
    parser.add_argument('--max-tokens', type=int, default=8192, help='最大token数（默认8192）')
    parser.add_argument('--timeout', type=int, default=600, help='超时时间秒数（默认600）')
    parser.add_argument('--file-id', type=int, required=True, help='数据库文件ID')
    parser.add_argument('--user-id', type=int, required=True, help='用户ID')
    parser.add_argument('--task-id', type=str, required=True, help='任务ID（由任务管理器传入）')

    
    
    args = parser.parse_args()
    
    # 使用命令行参数中的服务列表
    services = args.services
    
    # 创建分布式数据生成器
    generator = PipelineDataGenerator(
        services=services,
        model=args.model,
        api_key=args.api_key,
        is_vllm=args.is_vllm,
        use_proxy=args.use_proxy,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        timeout=args.timeout
    )
    
    # 使用从任务管理器传入的任务ID
    task_id = args.task_id
    
    # 开始生成数据
    await generator.generate_data(
        task_id=task_id,
        user_id=args.user_id,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent,
        min_score=args.min_score,
        task_type=args.task_type,
        variants_per_sample=args.variants_per_sample,
        sample_retry_times=3,  # 默认样本重试3次
        data_rounds=args.data_rounds,
        model=args.model,
        retry_times=args.retry_times,
        special_prompt=args.special_prompt,
        directions=args.directions,
        api_key=args.api_key,
        is_vllm=args.is_vllm,
        use_proxy=args.use_proxy,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        file_id=args.file_id
    )


if __name__ == "__main__":
    asyncio.run(main())