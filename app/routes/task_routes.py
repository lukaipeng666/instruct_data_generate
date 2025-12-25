#!/usr/bin/env python3
"""
任务管理路由
包括任务启动、停止、进度查询、状态管理等
"""

import os
import json
import queue
import threading
import time
import redis
import yaml
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db, ModelConfig, Task
from database.auth import get_current_user
from services.task_manager import (
    create_task, get_task, get_all_tasks, get_active_task,
    stop_task, delete_task, task_exists, run_main_py,
    running_tasks_lock, safe_lock, running_tasks
)

router = APIRouter(prefix='/api', tags=['任务管理'])


# Redis 客户端单例
_redis_client = None

def get_redis_client():
    """获取 Redis 客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        try:
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            redis_config = config.get('redis_service', {})
            host = redis_config.get('host', 'localhost')
            port = redis_config.get('port', 6379)
            db = redis_config.get('db', 0)
            password = redis_config.get('password', None)
            
            _redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True
            )
            # 测试连接
            _redis_client.ping()
        except Exception as e:
            print(f"⚠️  Redis 连接失败: {e}")
            _redis_client = None
    return _redis_client


@router.post('/start')
async def start_task(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """启动任务"""
    try:
        data = await request.json()
        
        # 获取数据库文件ID
        if not data.get('input_file') or not data.get('input_file').strip():
            return JSONResponse({
                'success': False,
                'error': '缺少必填参数: input_file'
            }, status_code=400)
        
        input_file = data['input_file']
        
        # 解析 db://file_id/filename 格式
        if not input_file.startswith('db://'):
            return JSONResponse({
                'success': False,
                'error': '输入文件必须是数据库文件（db://格式）'
            }, status_code=400)
        
        try:
            parts = input_file.replace('db://', '').split('/', 1)
            db_file_id = int(parts[0])
            db_user_id = current_user.id
        except (ValueError, IndexError) as e:
            return JSONResponse({
                'success': False,
                'error': f'无效的数据库文件路径格式: {str(e)}'
            }, status_code=400)
        
        # 如果提供了model_id，从数据库获取模型配置
        model_path = data.get('model')
        services = data.get('services', ['http://localhost:6466/v1'])
        
        # 模型配置相关参数（默认值）
        model_api_key = data.get('api_key', '')
        model_is_vllm = data.get('is_vllm', True)
        model_top_p = float(data.get('top_p', 1.0))
        model_max_tokens = int(data.get('max_tokens', 8192))
        model_timeout = int(data.get('timeout', 600))
        model_max_concurrent = int(data.get('max_concurrent', 16))
        
        if data.get('model_id'):
            model_config = db.query(ModelConfig).filter(
                ModelConfig.id == data['model_id'],
                ModelConfig.is_active == True
            ).first()
            
            if not model_config:
                return JSONResponse({
                    'success': False,
                    'error': '选择的模型不存在或已禁用'
                }, status_code=400)
            
            # 使用模型配置中的所有参数
            model_path = model_config.model_path
            services = [model_config.api_url]
            model_api_key = model_config.api_key
            model_is_vllm = model_config.is_vllm
            model_top_p = model_config.top_p
            model_max_tokens = model_config.max_tokens
            model_timeout = model_config.timeout
            model_max_concurrent = model_config.max_concurrent
        
        # 生成任务ID（使用文件名）
        # db://file_id/filename -> filename
        parts = input_file.replace('db://', '').split('/', 1)
        filename = parts[1] if len(parts) > 1 else 'task'
        task_id_base = os.path.splitext(filename)[0]
        
        # 清理任务ID，移除不允许的字符
        task_id_base = task_id_base.replace(' ', '_').replace('/', '_').replace('\\', '_')
        
        # 检查是否已有同名任务，如果有则添加序号
        # 同时检查内存和数据库中是否存在同名任务
        task_id = task_id_base
        counter = 1
        with running_tasks_lock:
            while task_id in running_tasks or db.query(Task).filter(Task.task_id == task_id).first():
                task_id = f"{task_id_base}_{counter}"
                counter += 1
        
        # 准备参数（优先使用模型配置中的参数）
        params = {
            'services': services,
            'model': model_path,
            'batch_size': int(data.get('batch_size', 16)),
            'max_concurrent': model_max_concurrent,
            'min_score': int(data.get('min_score', 10)),
            'task_type': data.get('task_type', 'general'),
            'variants_per_sample': int(data.get('variants_per_sample', 3)),
            'data_rounds': int(data.get('data_rounds', 10)),
            'retry_times': int(data.get('retry_times', 3)),
            'special_prompt': data.get('special_prompt', ''),
            'directions': data.get('directions', '信用卡年费 股票爆仓 基金赎回'),
            # 模型调用相关参数（使用模型配置中的值）
            'api_key': model_api_key,
            'is_vllm': model_is_vllm,
            'use_proxy': data.get('use_proxy', False),
            'top_p': model_top_p,
            'max_tokens': model_max_tokens,
            'timeout': model_timeout,
            'file_id': db_file_id,
            'user_id': db_user_id
        }
        
        # 创建内存中的任务
        create_task(task_id, params)
        
        # 同时在数据库中创建任务记录（为了外键约束）
        db_task = Task(
            task_id=task_id,
            user_id=current_user.id,
            status='running',
            params=json.dumps(params, ensure_ascii=False)
        )
        db.add(db_task)
        db.commit()
        
        # 在新线程中运行任务
        thread = threading.Thread(target=run_main_py, args=(params, task_id))
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            'success': True,
            'task_id': task_id
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.get('/progress/{task_id}')
def get_progress(task_id, request: Request, current_user=Depends(get_current_user)):
    """获取任务进度（Server-Sent Events）"""
    # 首先检查任务是否存在并获取输出队列
    with running_tasks_lock:
        if task_id not in running_tasks:
            raise HTTPException(status_code=404, detail='任务不存在')
        output_queue = running_tasks[task_id]['output_queue']
        log_history = running_tasks[task_id]['log_history'].copy()  # 复制历史日志
    
    def generate():
        try:
            # 首先发送所有历史日志
            for line in log_history:
                yield f"data: {json.dumps({'type': 'output', 'line': line})}\n\n"
            
            # 然后继续从队列中读取新日志
            while True:
                try:
                    line = output_queue.get(timeout=1)
                    if line is None:  # 结束标记
                        # 发送最终状态
                        try:
                            with safe_lock(running_tasks_lock):
                                if task_id in running_tasks:
                                    task_info = running_tasks[task_id]
                                    yield f"data: {json.dumps({'type': 'finished', 'return_code': task_info['return_code']})}\n\n"
                        except (RuntimeError, KeyError):
                            # 如果任务已被删除或锁有问题，直接退出
                            pass
                        break
                    else:
                        yield f"data: {json.dumps({'type': 'output', 'line': line})}\n\n"
                except queue.Empty:
                    # 检查任务是否已完成
                    task_finished = False
                    try:
                        with safe_lock(running_tasks_lock):
                            if task_id in running_tasks and running_tasks[task_id]['finished']:
                                task_info = running_tasks[task_id]
                                yield f"data: {json.dumps({'type': 'finished', 'return_code': task_info['return_code']})}\n\n"
                                task_finished = True
                    except (RuntimeError, KeyError):
                        # 如果任务已被删除或锁有问题，直接退出
                        task_finished = True
                    
                    if task_finished:
                        break
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                except (GeneratorExit, StopIteration):
                    # 生成器被关闭，正常退出
                    break
                except Exception:
                    # 其他异常，安全退出
                    break
        except GeneratorExit:
            # 生成器被关闭，正常退出
            pass
        except Exception:
            # 任何其他异常，安全退出
            pass
    
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@router.post('/stop/{task_id}')
def stop_task_route(task_id, current_user=Depends(get_current_user)):
    """停止任务"""
    if not stop_task(task_id):
        raise HTTPException(status_code=404, detail='任务不存在')
    return JSONResponse({'success': True})


@router.delete('/task/{task_id}')
def delete_task_route(task_id, current_user=Depends(get_current_user)):
    """删除任务（只能删除已停止的任务）"""
    success, error = delete_task(task_id)
    if not success:
        if error == '任务不存在':
            raise HTTPException(status_code=404, detail=error)
        return JSONResponse({
            'success': False,
            'error': error
        }, status_code=400)
    return JSONResponse({'success': True})


@router.get('/status/{task_id}')
def get_status(task_id, current_user=Depends(get_current_user)):
    """获取任务状态"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    
    return JSONResponse({
        'finished': task['finished'],
        'return_code': task['return_code']
    })


@router.get('/active_task')
def get_active_task_route(current_user=Depends(get_current_user)):
    """获取当前正在运行的任务ID"""
    task_id, task = get_active_task()
    if task_id:
        return JSONResponse({
            'success': True,
            'task_id': task_id,
            'params': task['params']
        })
    return JSONResponse({
        'success': False,
        'message': '没有运行中的任务'
    })


@router.get('/tasks')
def get_all_tasks_route(current_user=Depends(get_current_user)):
    """获取所有任务列表"""
    tasks_list = get_all_tasks()
    return JSONResponse({
        'success': True,
        'tasks': tasks_list
    })


@router.get('/task_progress/{task_id}')
def get_task_progress_from_redis(task_id: str, current_user=Depends(get_current_user)):
    """
    从 Redis 获取任务进度（Pipeline 生成任务）
    返回任务的实时进度信息
    """
    redis_client = get_redis_client()
    if not redis_client:
        return JSONResponse({
            'success': False,
            'error': 'Redis 服务不可用'
        }, status_code=503)
    
    try:
        redis_key = f"task_progress:{task_id}"
        progress_data = redis_client.get(redis_key)
        
        if not progress_data:
            return JSONResponse({
                'success': False,
                'error': '任务进度信息不存在，可能任务未启动或已过期'
            }, status_code=404)
        
        # 解析 JSON 数据
        progress = json.loads(progress_data)
        
        # 计算进度百分比（优先使用 completion_percent）
        if 'completion_percent' not in progress:
            if progress.get('total_rounds', 0) > 0:
                progress_percent = (progress.get('current_round', 0) / progress['total_rounds']) * 100
                progress['progress_percent'] = round(progress_percent, 2)
            else:
                progress['progress_percent'] = 0
        else:
            progress['progress_percent'] = progress['completion_percent']
        
        return JSONResponse({
            'success': True,
            'progress': progress
        })
        
    except json.JSONDecodeError as e:
        return JSONResponse({
            'success': False,
            'error': f'进度数据解析失败: {str(e)}'
        }, status_code=500)
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.get('/progress_unified/{task_id}')
def get_unified_task_progress(task_id: str, current_user=Depends(get_current_user)):
    """
    统一获取任务进度
    优先从 Redis 获取，如果 Redis 不存在，则从任务状态获取
    """
    # 1. 先尝试从 Redis 获取
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_key = f"task_progress:{task_id}"
            progress_data = redis_client.get(redis_key)
            
            if progress_data:
                # Redis 中有数据，直接返回
                progress = json.loads(progress_data)
                
                # 确保有 progress_percent 字段
                if 'completion_percent' in progress:
                    progress['progress_percent'] = progress['completion_percent']
                elif progress.get('total_rounds', 0) > 0:
                    progress['progress_percent'] = round(
                        (progress.get('current_round', 0) / progress['total_rounds']) * 100, 2
                    )
                else:
                    progress['progress_percent'] = 0
                
                # 添加数据来源
                progress['source'] = 'redis'
                
                return JSONResponse({
                    'success': True,
                    'progress': progress
                })
        except Exception as e:
            print(f"⚠️  从 Redis 读取失败: {e}，尝试从任务管理器获取")
    
    # 2. Redis 中没有数据，从任务管理器获取
    task = get_task(task_id)
    if not task:
        return JSONResponse({
            'success': False,
            'error': '任务不存在'
        }, status_code=404)
    
    # 3. 构造进度信息
    is_finished = task.get('finished', False)
    return_code = task.get('return_code')
    start_time = task.get('start_time', 0)
    run_time = time.time() - start_time if start_time > 0 else 0
    
    # 根据 finished 状态计算完成百分比
    if is_finished:
        # 任务已完成，判断是否成功
        if return_code == 0:
            completion_percent = 100.0
            status = 'completed'
        else:
            # 任务失败或被停止
            completion_percent = 0.0
            status = 'failed'
    else:
        # 任务还在运行，无法确定进度，显示为运行中
        completion_percent = None  # 未知进度
        status = 'running'
    
    progress = {
        'task_id': task_id,
        'status': status,
        'finished': is_finished,
        'return_code': return_code,
        'run_time': round(run_time, 2),
        'completion_percent': completion_percent,
        'source': 'task_manager',
        'message': '任务进度不可用，仅显示任务状态' if completion_percent is None else None
    }
    
    return JSONResponse({
        'success': True,
        'progress': progress
    })
