#!/usr/bin/env python3
"""
任务管理服务
负责任务的执行、进程管理和状态跟踪
"""

import os
import sys
import subprocess
import queue
import time
from threading import RLock
from contextlib import contextmanager
from datetime import datetime


# 存储运行中的任务
running_tasks = {}
running_tasks_lock = RLock()
# 存储清理任务的定时器
_cleanup_timers = {}


def _update_task_status_in_db(task_id: str, return_code: int = None, status: str = None):
    """
    更新数据库中的任务状态
    在任务完成后调用，将状态从 'running' 更新为 'finished' 或 'error' 或 'stopped'
    
    Args:
        task_id: 任务ID
        return_code: 进程返回码（可选，如果提供则根据返回码判断状态）
        status: 直接指定的状态（可选，如 'stopped'）
    """
    try:
        # 导入数据库模块（延迟导入避免循环依赖）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from database.models import SessionLocal, Task
        
        db = SessionLocal()
        try:
            # 查找任务记录
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if task:
                # 确定任务状态
                if status:
                    # 直接使用指定的状态
                    task.status = status
                elif return_code is not None:
                    # 根据返回码判断任务状态
                    if return_code == 0:
                        task.status = 'finished'
                    else:
                        task.status = 'error'
                        if task.error_message is None:
                            task.error_message = f'任务退出码: {return_code}'
                
                # 设置完成时间
                task.finished_at = datetime.utcnow()
                
                db.commit()
                print(f"✅ 数据库任务状态已更新: {task_id} -> {task.status}")
            else:
                print(f"⚠️ 数据库中未找到任务记录: {task_id}")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ 更新数据库任务状态失败: {task_id} - {e}")


@contextmanager
def safe_lock(lock):
    """安全地获取和释放锁，即使生成器被中断也能正确处理"""
    acquired = False
    try:
        lock.acquire()
        acquired = True
        yield
    finally:
        if acquired:
            try:
                lock.release()
            except RuntimeError:
                # 如果锁已经被释放或未获取，忽略错误
                pass


def run_main_py(params, task_id):
    """运行 main.py 并捕获输出"""
    # 构建命令 - 项目根目录是 app/services 向上两层
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cmd = [sys.executable, os.path.join(project_root, 'main.py')]
    
    # 添加任务ID参数（确保生成的数据使用正确的task_id）
    cmd.extend(['--task-id', task_id])
    
    # 添加所有参数
    for key, value in params.items():
        if key in ['file_id', 'user_id']:
            # file_id 和 user_id 必须传递
            arg_name = '--' + key.replace('_', '-')
            cmd.append(arg_name)
            cmd.append(str(value))
        elif key == 'directions':
            # directions 是空格分隔的字符串，需要拆分成多个参数
            if value and value.strip():
                directions_list = value.strip().split()
                cmd.extend(['--directions'] + directions_list)
        elif key == 'services':
            # services 是列表，需要拆分成多个参数
            if isinstance(value, list) and len(value) > 0:
                cmd.extend(['--services'] + value)
            elif isinstance(value, str) and value.strip():
                # 如果是字符串，按空格或逗号分隔
                services_list = [s.strip() for s in value.replace(',', ' ').split() if s.strip()]
                if services_list:
                    cmd.extend(['--services'] + services_list)
        elif key == 'special_prompt':
            # special_prompt 即使为空字符串也要传递
            arg_name = '--' + key.replace('_', '-')
            cmd.append(arg_name)
            cmd.append(str(value) if value is not None else '')
        elif key == 'is_vllm':
            # is_vllm 需要特殊处理：True传--is-vllm，False传--no-vllm
            if value:
                cmd.append('--is-vllm')
            else:
                cmd.append('--no-vllm')
        elif value is not None and value != '':
            # 将参数名转换为命令行格式
            arg_name = '--' + key.replace('_', '-')
            if isinstance(value, bool):
                if value:
                    cmd.append(arg_name)
            else:
                cmd.append(arg_name)
                cmd.append(str(value))
    
    # 运行进程并实时捕获输出
    # 设置环境变量，禁用Python输出缓冲，确保实时输出
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,  # 行缓冲模式，确保实时输出
        cwd=project_root,  # 使用项目根目录作为工作目录
        env=env  # 传递环境变量，PYTHONUNBUFFERED=1 确保Python立即刷新输出
    )
    
    # 将进程对象存储到任务中（线程安全）
    with running_tasks_lock:
        running_tasks[task_id]['process'] = process
    
    # 实时读取输出
    with running_tasks_lock:
        output_queue = running_tasks[task_id]['output_queue']
        log_history = running_tasks[task_id]['log_history']
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                line_stripped = line.rstrip()
                # 同时添加到队列和历史日志中
                output_queue.put(line_stripped)
                with running_tasks_lock:
                    if task_id in running_tasks:
                        running_tasks[task_id]['log_history'].append(line_stripped)
        output_queue.put(None)  # 结束标记
    except Exception as e:
        error_msg = f"ERROR: {str(e)}"
        output_queue.put(error_msg)
        with running_tasks_lock:
            if task_id in running_tasks:
                running_tasks[task_id]['log_history'].append(error_msg)
        output_queue.put(None)
    finally:
        process.wait()
        # 更新任务状态（线程安全）
        with running_tasks_lock:
            running_tasks[task_id]['return_code'] = process.returncode
            running_tasks[task_id]['finished'] = True
        
        # 更新数据库中的任务状态
        _update_task_status_in_db(
            task_id=task_id,
            return_code=process.returncode
        )
        
        # 启动延迟清理任务（5分钟后自动清理）
        _schedule_cleanup(task_id, delay=300)


def create_task(task_id, params):
    """创建新任务"""
    with running_tasks_lock:
        running_tasks[task_id] = {
            'output_queue': queue.Queue(),
            'log_history': [],  # 保存历史日志，用于新连接时发送
            'process': None,
            'finished': False,
            'return_code': None,
            'params': params,
            'start_time': time.time()  # 添加开始时间
        }


def get_task(task_id):
    """获取任务信息"""
    with running_tasks_lock:
        return running_tasks.get(task_id)


def get_all_tasks():
    """获取所有任务"""
    with running_tasks_lock:
        tasks_list = []
        for task_id, task in running_tasks.items():
            # 计算任务运行时间（秒）
            run_time = time.time() - task['start_time'] if 'start_time' in task else 0
            
            tasks_list.append({
                'task_id': task_id,
                'finished': task['finished'],
                'return_code': task['return_code'],
                'params': task['params'],
                'run_time': round(run_time, 2)
            })
        
        # 按开始时间倒序排列（最新的任务在前）
        tasks_list.sort(key=lambda x: running_tasks[x['task_id']]['start_time'], reverse=True)
        
        return tasks_list


def get_active_task():
    """获取当前正在运行的任务"""
    with running_tasks_lock:
        for task_id, task in running_tasks.items():
            if not task['finished']:
                return task_id, task
        return None, None


def stop_task(task_id):
    """停止任务"""
    with running_tasks_lock:
        if task_id not in running_tasks:
            return False
        
        task = running_tasks[task_id]
        if task['process']:
            try:
                task['process'].terminate()
                task['process'].wait(timeout=5)
            except:
                task['process'].kill()
        
        task['finished'] = True
    
    # 更新数据库中的任务状态为 'stopped'
    _update_task_status_in_db(task_id=task_id, status='stopped')
    
    # 取消之前的清理定时器（如果存在），启动新的清理
    if task_id in _cleanup_timers:
        _cleanup_timers[task_id].cancel()
    _schedule_cleanup(task_id, delay=300)
    
    return True


def _cleanup_task(task_id: str):
    """清理已完成的任务，释放内存"""
    with running_tasks_lock:
        if task_id in running_tasks:
            # 清理任务数据
            del running_tasks[task_id]
            # 清理清理定时器
            if task_id in _cleanup_timers:
                del _cleanup_timers[task_id]
            print(f"[TaskManager] 任务已清理: {task_id}")


def _schedule_cleanup(task_id: str, delay: int = 300):
    """调度延迟清理任务"""
    def cleanup_callback():
        _cleanup_task(task_id)
    
    import threading
    # 创建并启动清理定时器
    timer = threading.Timer(delay, cleanup_callback)
    timer.daemon = True
    
    with running_tasks_lock:
        _cleanup_timers[task_id] = timer
    
    timer.start()
    print(f"[TaskManager] 任务清理已调度: {task_id} (将在{delay}秒后清理)")


def delete_task(task_id):
    """删除任务（只能删除已停止的任务）"""
    with running_tasks_lock:
        if task_id not in running_tasks:
            return False, '任务不存在'
        
        task = running_tasks[task_id]
        
        # 检查任务是否已停止
        if not task['finished']:
            return False, '只能删除已停止的任务，请先停止任务'
        
        # 如果进程还在，确保它已终止
        if task['process']:
            try:
                task['process'].terminate()
                task['process'].wait(timeout=1)
            except:
                try:
                    task['process'].kill()
                except:
                    pass
        
        # 删除任务
        del running_tasks[task_id]
        
        # 取消清理定时器（如果存在）
        if task_id in _cleanup_timers:
            _cleanup_timers[task_id].cancel()
            del _cleanup_timers[task_id]
        return True, None


def task_exists(task_id):
    """检查任务是否存在"""
    with running_tasks_lock:
        return task_id in running_tasks
