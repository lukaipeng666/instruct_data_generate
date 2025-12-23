#!/usr/bin/env python3
"""
分布式数据生成管道
将样本数据分配给多个本地模型服务同时处理，最大化数据生成速度
"""

import json
import os
import asyncio
import argparse
import time
import math
from pathlib import Path
from typing import List, Dict, Any
import logging
from develop.single_gen import main_process

# 配置日志
os.makedirs('log', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/pipeline_generation.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PipelineDataGenerator:
    def __init__(self, services: List[str], model: str = "/data/models/Qwen3-32B"):
        """
        初始化分布式数据生成器
        
        Args:
            services: API服务地址列表，如 ["http://localhost:6466/v1", ...]
            model: 模型名称
        """
        self.services = services
        self.model = model
        self.service_count = len(services)
        
    def split_samples(self, input_file: str, output_dir: str) -> List[str]:
        """将输入样本文件分割成多个子文件"""
        
        logger.info(f"读取样本文件: {input_file}")
        
        # 读取所有样本
        samples = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line.strip())
                    samples.append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"第{line_num}行JSON解析失败: {e}")
        
        total_samples = len(samples)
        logger.info(f"总样本数: {total_samples}")
        
        # 计算每个服务处理的样本数
        samples_per_service = math.ceil(total_samples / self.service_count)
        logger.info(f"每个服务处理约: {samples_per_service} 个样本")
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 分割数据并保存
        split_files = []
        for i in range(self.service_count):
            start_idx = i * samples_per_service
            end_idx = min((i + 1) * samples_per_service, total_samples)
            
            if start_idx >= total_samples:
                break
                
            service_samples = samples[start_idx:end_idx]
            split_file = output_path / f"samples_{i+1}_of_{self.service_count}.jsonl"
            
            with open(split_file, 'w', encoding='utf-8') as f:
                for sample in service_samples:
                    json_line = json.dumps(sample, ensure_ascii=False)
                    f.write(json_line + '\n')
            
            split_files.append(str(split_file))
            logger.info(f"分片 {i+1}: {len(service_samples)} 个样本 -> {split_file}")
        
        return split_files
    
    async def process_single_service(self, service_idx: int, api_base: str, input_file: str, 
                                   output_file: str, batch_size: int = 5, 
                                   max_concurrent: int = 5, min_score: int = 8,
                                   task_type: str = "entity_extraction",
                                   variants_per_sample: int = 3,
                                   sample_retry_times: int = 3,
                                   model: str = "/data/models/Qwen3-32B",
                                   retry_times: int = 3,
                                   special_prompt: str = "",
                                   directions: list = ["信用卡年费"]) -> Dict[str, Any]:
        """处理单个服务的任务"""
        
        logger.info(f"🚀 服务 {service_idx + 1} 开始生成数据: {api_base}")
        start_time = time.time()

        parameter = {
            "input_file": input_file,
            "output_file": output_file, 
            "api_base": api_base, 
            "model": model, 
            "batch_size": batch_size, 
            "max_concurrent": max_concurrent, 
            "retry_times": sample_retry_times, 
            "min_score": min_score, 
            "task_type": task_type, 
            "variants_per_sample": variants_per_sample, 
            "sample_retry_times": sample_retry_times,
            "retry_times":retry_times,
            "special_prompt":special_prompt,
            "directions": directions
        }
        
        try:
            process = await main_process(**parameter)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # 检查结果
            if process["status"] == "Sucessed":
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        output_count = sum(1 for _ in f)
                    
                    logger.info(f"✅ 服务 {service_idx + 1} 完成! 耗时: {duration:.1f}秒, 生成数据: {output_count}条")
                    
                    return {
                        'service_idx': service_idx,
                        'success': True,
                        'duration': duration,
                        'output_file': output_file,
                        'output_count': output_count
                    }
                else:
                    logger.error(f"❌ 服务 {service_idx + 1} 没有生成输出文件")
                    return {'service_idx': service_idx, 'success': False, 'error': 'no_output'}
            else:
                logger.error(f"❌ 服务 {service_idx + 1} 处理失败，返回码: {process.returncode}")
                return {'service_idx': service_idx, 'success': False, 'error': f'exit_code_{process.returncode}'}
                
        except Exception as e:
            logger.error(f"❌ 服务 {service_idx + 1} 异常: {e}")
            return {'service_idx': service_idx, 'success': False, 'error': str(e)}
    
    def merge_outputs(self, output_files: List[str], final_output: str) -> Dict[str, Any]:
        """合并所有输出文件"""
        
        logger.info(f"📦 开始合并输出文件到: {final_output}")
        
        total_records = 0
        successful_files = []
        
        # 创建最终输出文件
        with open(final_output, 'w', encoding='utf-8') as final_f:
            for i, output_file in enumerate(output_files):
                if os.path.exists(output_file):
                    file_records = 0
                    with open(output_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                final_f.write(line + '\n')
                                file_records += 1
                                total_records += 1
                    
                    successful_files.append(output_file)
                    logger.info(f"✅ 合并文件 {i+1}: {file_records} 条记录")
                    
                    # 删除临时文件
                    os.remove(output_file)
                    logger.info(f"🗑️  清理临时文件: {output_file}")
                else:
                    logger.warning(f"⚠️  输出文件不存在: {output_file}")
        
        result = {
            'total_records': total_records,
            'successful_files': len(successful_files),
            'failed_files': len(output_files) - len(successful_files)
        }
        
        logger.info(f"📊 合并完成: {total_records} 条记录")
        return result
    
    def cleanup_split_files(self, split_files: List[str]):
        """清理分割的临时文件"""
        for split_file in split_files:
            try:
                if os.path.exists(split_file):
                    os.remove(split_file)
                    logger.info(f"🗑️  清理分割文件: {split_file}")
            except Exception as e:
                logger.warning(f"清理文件失败 {split_file}: {e}")
    
    async def generate_data(self, input_file: str, output_file: str, 
                          batch_size: int = 5, max_concurrent: int = 5,
                          min_score: int = 8, task_type: str = "entity_extraction",
                          variants_per_sample: int = 3, sample_retry_times: int = 3,
                          data_rounds: int = 3, model: str = "/data/models/Qwen3-32B",
                          retry_times: int = 3, special_prompt: str = "",
                          directions: list = ["信用卡年费"]):
        """生成数据，使用多个服务并行处理，支持多轮数据使用"""
        
        logger.info("🚀 开始分布式数据生成")
        logger.info(f"使用 {self.service_count} 个服务:")
        for i, service in enumerate(self.services):
            logger.info(f"  服务 {i+1}: {service}")
        logger.info(f"数据使用轮次: {data_rounds} 轮")
        
        total_start_time = time.time()
        
        # 创建临时目录
        temp_dir = Path(output_file).parent / "temp_splits"
        
        # 存储所有轮次的结果
        all_round_results = []
        total_generated_count = 0
        
        # 多轮数据处理
        for round_num in range(data_rounds):
            logger.info(f"\n🔄 第 {round_num + 1}/{data_rounds} 轮数据生成")
            
            # 1. 分割样本数据
            logger.info("📊 样本分割")
            round_dir = temp_dir / f"round_{round_num + 1}"
            split_files = self.split_samples(input_file, str(round_dir))
            
            # 2. 并行处理
            logger.info(f"⚡ 并行生成 ({self.service_count} 个服务)")
            
            # 创建任务
            tasks = []
            output_files = []
            
            for i, (service, split_file) in enumerate(zip(self.services, split_files)):
                output_split = str(round_dir / f"generated_{i+1}_of_{self.service_count}.jsonl")
                output_files.append(output_split)
                
                task = self.process_single_service(
                    service_idx=i,
                    api_base=service,
                    input_file=split_file,
                    output_file=output_split,
                    batch_size=batch_size,
                    max_concurrent=max_concurrent,
                    min_score=min_score,
                    task_type=task_type,
                    variants_per_sample=variants_per_sample,
                    sample_retry_times=sample_retry_times,
                    model=model,
                    retry_times=retry_times,
                    special_prompt=special_prompt,
                    directions=directions
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 3. 统计本轮结果
            logger.info("📈 本轮结果统计")
            successful_count = 0
            round_output_count = 0
            
            for result in results:
                if isinstance(result, dict) and result.get('success'):
                    successful_count += 1
                    round_output_count += result.get('output_count', 0)
                    logger.info(f"✅ 服务 {result['service_idx'] + 1}: {result['output_count']} 条, {result['duration']:.1f}秒")
                else:
                    if isinstance(result, Exception):
                        logger.error(f"❌ 任务异常: {result}")
                    else:
                        logger.error(f"❌ 服务失败: {result}")
            
            total_generated_count += round_output_count
            all_round_results.extend(output_files)
            
            logger.info(f"第 {round_num + 1} 轮完成: 生成 {round_output_count} 条数据")
            
            # 4. 清理本轮分割文件
            self.cleanup_split_files(split_files)
        
        # 5. 合并所有轮次的输出
        logger.info(f"\n📦 合并所有 {data_rounds} 轮的输出文件")
        merge_result = self.merge_outputs(all_round_results, output_file)
        
        # 6. 清理所有临时目录
        logger.info(f"\n🗑️  清理临时目录")
        for round_num in range(data_rounds):
            round_dir = temp_dir / f"round_{round_num + 1}"
            try:
                if round_dir.exists():
                    round_dir.rmdir()
                    logger.info(f"🗑️  清理轮次目录: {round_dir}")
            except:
                pass
        
        try:
            temp_dir.rmdir()
            logger.info(f"🗑️  清理主临时目录: {temp_dir}")
        except:
            pass
        
        # 7. 总结
        total_end_time = time.time()
        total_duration = total_end_time - total_start_time
        
        logger.info(f"\n🎉 分布式多轮数据生成完成!")
        logger.info(f"=" * 70)
        logger.info(f"总耗时: {total_duration:.1f} 秒")
        logger.info(f"数据轮次: {data_rounds} 轮")
        logger.info(f"使用服务: {self.service_count} 个")
        logger.info(f"生成数据: {merge_result['total_records']} 条")
        logger.info(f"平均每轮: {merge_result['total_records']/data_rounds:.1f} 条")
        logger.info(f"平均速度: {merge_result['total_records']/total_duration:.2f} 记录/秒")
        logger.info(f"输出文件: {output_file}")
        
        logger.info("🏆 多轮数据生成任务完成!")


def test_services_connection(services: List[str]) -> List[str]:
    """测试所有服务的连接"""
    import requests
    
    logger.info("🔌 测试服务连接...")
    working_services = []
    
    for i, service in enumerate(services):
        try:
            response = requests.get(f"{service}/models", timeout=10)
            if response.status_code == 200:
                models = response.json()
                logger.info(f"✅ 服务 {i+1} ({service}): 连接成功")
                working_services.append(service)
            else:
                logger.error(f"❌ 服务 {i+1} ({service}): 状态码 {response.status_code}")
        except Exception as e:
            logger.error(f"❌ 服务 {i+1} ({service}): 连接失败 - {e}")
    
    logger.info(f"可用服务: {len(working_services)}/{len(services)}")
    return working_services


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
    parser.add_argument('--input-file', help='输入的样本JSONL文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出的JSONL文件路径')
    parser.add_argument('--services', nargs='+', default=default_services, help='API服务地址列表')
    parser.add_argument('--model', default='/data/models/Qwen3-32B', help='模型名称')
    parser.add_argument('--batch-size', type=int, default=16, help='每个服务的批处理大小')
    parser.add_argument('--max-concurrent', type=int, default=16, help='每个服务的最大并发数')
    parser.add_argument('--min-score', type=int, default=8, help='最低评分要求(0-10)')
    parser.add_argument('--task-type', default='entity_extraction', help='任务类型')
    parser.add_argument('--variants-per-sample', type=int, default=3, help='每个样本生成的变体数量')
    parser.add_argument('--data-rounds', type=int, default=10, help='数据使用轮次')
    parser.add_argument('--test-only', action='store_true', help='仅测试服务连接')
    parser.add_argument('--retry-times', default=3, type=int, help='重试次数')
    parser.add_argument('--special-prompt', default="", type=str, help='特殊任务提示词')
    parser.add_argument('--directions', nargs='*', default=['信用卡年费', '股票爆仓', '基金赎回'],help='需要构造的题材，可输入多个，如：--directions 信用卡年费 股票爆仓')

    
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not args.test_only and not os.path.exists(args.input_file):
        logger.error(f"输入文件不存在: {args.input_file}")
        return
    
    # 测试服务连接
    working_services = test_services_connection(args.services)
    
    if not working_services:
        logger.error("没有可用的服务，请检查服务是否正常运行")
        return
    
    if args.test_only:
        logger.info("服务连接测试完成")
        return
    
    # 创建分布式数据生成器
    generator = PipelineDataGenerator(
        services=working_services,
        model=args.model
    )

    # directions = json.loads(args.directions)
    
    # 开始生成数据
    await generator.generate_data(
        input_file=args.input_file,
        output_file=args.output,
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
        directions=args.directions
    )


if __name__ == "__main__":
    asyncio.run(main()) 