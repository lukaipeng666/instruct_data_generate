#!/usr/bin/env python3
"""
报告生成模块
负责生成和管理数据生成过程的报告
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class ServiceReport:
    """单个服务的运行报告"""
    service_idx: int
    api_base: str
    success: bool
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    input_samples: int = 0
    output_count: int = 0
    error: Optional[str] = None
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class RoundReport:
    """单轮生成的报告"""
    round_num: int
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    total_input_samples: int = 0
    total_output_count: int = 0
    service_reports: List[ServiceReport] = field(default_factory=list)
    
    def add_service_report(self, report: ServiceReport):
        """添加服务报告"""
        self.service_reports.append(report)
        self.total_output_count += report.output_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'round_num': self.round_num,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'total_input_samples': self.total_input_samples,
            'total_output_count': self.total_output_count,
            'service_reports': [sr.to_dict() for sr in self.service_reports]
        }


@dataclass  
class PipelineReport:
    """整个Pipeline的运行报告"""
    task_name: str = ""
    input_file: str = ""
    output_file: str = ""
    model: str = ""
    task_type: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    total_rounds: int = 0
    total_services: int = 0
    total_input_samples: int = 0
    total_output_count: int = 0
    round_reports: List[RoundReport] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    
    def add_round_report(self, report: RoundReport):
        """添加轮次报告"""
        self.round_reports.append(report)
        self.total_output_count += report.total_output_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_name': self.task_name,
            'input_file': self.input_file,
            'output_file': self.output_file,
            'model': self.model,
            'task_type': self.task_type,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            'end_time': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            'duration': self.duration,
            'total_rounds': self.total_rounds,
            'total_services': self.total_services,
            'total_input_samples': self.total_input_samples,
            'total_output_count': self.total_output_count,
            'average_per_round': self.total_output_count / self.total_rounds if self.total_rounds > 0 else 0,
            'speed_per_second': self.total_output_count / self.duration if self.duration > 0 else 0,
            'config': self.config,
            'round_reports': [rr.to_dict() for rr in self.round_reports]
        }


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, report_file: Optional[str] = None):
        """
        初始化报告生成器
        
        Args:
            report_file: 报告文件路径，如果为None则不保存文件
        """
        self.report_file = report_file
        self.pipeline_report: Optional[PipelineReport] = None
        self.current_round: Optional[RoundReport] = None
    
    def start_pipeline(self, task_name: str, input_file: str, output_file: str,
                       model: str, task_type: str, total_rounds: int, 
                       total_services: int, config: Dict[str, Any] = None):
        """
        开始一个新的Pipeline报告
        
        Args:
            task_name: 任务名称
            input_file: 输入文件路径
            output_file: 输出文件路径
            model: 使用的模型
            task_type: 任务类型
            total_rounds: 总轮次数
            total_services: 服务数量
            config: 配置信息
        """
        self.pipeline_report = PipelineReport(
            task_name=task_name,
            input_file=input_file,
            output_file=output_file,
            model=model,
            task_type=task_type,
            start_time=time.time(),
            total_rounds=total_rounds,
            total_services=total_services,
            config=config or {}
        )
        
        print(f"📊 开始记录Pipeline报告: {task_name}")
    
    def start_round(self, round_num: int, total_input_samples: int):
        """
        开始一个新的轮次
        
        Args:
            round_num: 轮次编号（从1开始）
            total_input_samples: 本轮输入样本数
        """
        self.current_round = RoundReport(
            round_num=round_num,
            start_time=time.time(),
            total_input_samples=total_input_samples
        )
    
    def add_service_result(self, service_idx: int, api_base: str, success: bool,
                          start_time: float, end_time: float, 
                          input_samples: int, output_count: int,
                          error: Optional[str] = None,
                          stats: Dict[str, Any] = None):
        """
        添加服务运行结果
        
        Args:
            service_idx: 服务索引
            api_base: API地址
            success: 是否成功
            start_time: 开始时间
            end_time: 结束时间
            input_samples: 输入样本数
            output_count: 输出数量
            error: 错误信息
            stats: 统计信息
        """
        if self.current_round is None:
            print("⚠️ 警告: 当前没有活动的轮次")
            return
        
        service_report = ServiceReport(
            service_idx=service_idx,
            api_base=api_base,
            success=success,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            input_samples=input_samples,
            output_count=output_count,
            error=error,
            stats=stats or {}
        )
        
        self.current_round.add_service_report(service_report)
        
        # 打印服务结果
        if success:
            print(f"  ✅ 服务 {service_idx + 1}: 生成 {output_count} 条, 耗时 {service_report.duration:.1f}秒")
        else:
            print(f"  ❌ 服务 {service_idx + 1}: 失败 - {error}")
    
    def end_round(self):
        """结束当前轮次"""
        if self.current_round is None:
            return
        
        self.current_round.end_time = time.time()
        self.current_round.duration = self.current_round.end_time - self.current_round.start_time
        
        if self.pipeline_report:
            self.pipeline_report.add_round_report(self.current_round)
        
        # 打印轮次摘要
        print(f"📈 第 {self.current_round.round_num} 轮完成: "
              f"生成 {self.current_round.total_output_count} 条, "
              f"耗时 {self.current_round.duration:.1f}秒")
        
        # 保存报告
        self._save_report()
        
        self.current_round = None
    
    def end_pipeline(self, total_input_samples: int):
        """
        结束Pipeline报告
        
        Args:
            total_input_samples: 总输入样本数
        """
        if self.pipeline_report is None:
            return
        
        self.pipeline_report.end_time = time.time()
        self.pipeline_report.duration = self.pipeline_report.end_time - self.pipeline_report.start_time
        self.pipeline_report.total_input_samples = total_input_samples
        
        # 打印最终报告
        self._print_summary()
        
        # 保存最终报告
        self._save_report()
    
    def _print_summary(self):
        """打印报告摘要"""
        if self.pipeline_report is None:
            return
        
        report = self.pipeline_report
        print(f"\n{'=' * 70}")
        print(f"🎉 数据生成任务完成!")
        print(f"{'=' * 70}")
        print(f"任务名称: {report.task_name}")
        print(f"总耗时: {report.duration:.1f} 秒")
        print(f"数据轮次: {report.total_rounds} 轮")
        print(f"使用服务: {report.total_services} 个")
        print(f"输入样本: {report.total_input_samples} 条")
        print(f"生成数据: {report.total_output_count} 条")
        if report.total_rounds > 0:
            print(f"平均每轮: {report.total_output_count / report.total_rounds:.1f} 条")
        if report.duration > 0:
            print(f"平均速度: {report.total_output_count / report.duration:.2f} 记录/秒")
        print(f"输出文件: {report.output_file}")
        if self.report_file:
            print(f"报告文件: {self.report_file}")
        print(f"{'=' * 70}")
    
    def _save_report(self):
        """保存报告到文件"""
        if self.report_file is None or self.pipeline_report is None:
            return
        
        try:
            # 确保目录存在
            Path(self.report_file).parent.mkdir(parents=True, exist_ok=True)
            
            # 写入报告
            with open(self.report_file, 'w', encoding='utf-8') as f:
                json.dump(self.pipeline_report.to_dict(), f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"⚠️ 保存报告失败: {e}")
    
    def get_report(self) -> Optional[Dict[str, Any]]:
        """获取当前报告"""
        if self.pipeline_report:
            return self.pipeline_report.to_dict()
        return None


class IncrementalReportWriter:
    """增量报告写入器，每次single_gen完成后追加到报告"""
    
    def __init__(self, report_file: str):
        """
        初始化增量报告写入器
        
        Args:
            report_file: 报告文件路径
        """
        self.report_file = report_file
        self.records: List[Dict[str, Any]] = []
        
        # 确保目录存在
        Path(self.report_file).parent.mkdir(parents=True, exist_ok=True)
    
    def append_result(self, result: Dict[str, Any]):
        """
        追加一条结果记录
        
        Args:
            result: 结果记录
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            **result
        }
        self.records.append(record)
        
        # 立即追加到文件
        try:
            with open(self.report_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"⚠️ 追加报告记录失败: {e}")
    
    def get_all_records(self) -> List[Dict[str, Any]]:
        """获取所有记录"""
        return self.records.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要统计"""
        successful = [r for r in self.records if r.get('success', False)]
        failed = [r for r in self.records if not r.get('success', False)]
        
        total_output = sum(r.get('output_count', 0) for r in successful)
        total_duration = sum(r.get('duration', 0) for r in self.records)
        
        return {
            'total_records': len(self.records),
            'successful_count': len(successful),
            'failed_count': len(failed),
            'total_output': total_output,
            'total_duration': total_duration,
            'average_output_per_run': total_output / len(successful) if successful else 0,
            'speed_per_second': total_output / total_duration if total_duration > 0 else 0
        }
