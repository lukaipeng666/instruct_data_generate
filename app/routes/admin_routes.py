#!/usr/bin/env python3
"""
管理员路由
包括用户管理、模型管理、任务管理等管理员功能
"""

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db, User, ModelConfig, Task
from database.auth import get_current_admin
from database.generated_data_service import (
    get_generated_data_count,
    get_generated_data_by_task,
    get_task_review_status
)

router = APIRouter(prefix='/api/admin', tags=['管理员'])


# ==================== 用户管理 ====================

@router.get('/users')
async def get_all_users(current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有用户列表（仅管理员）"""
    try:
        users = db.query(User).all()
        return JSONResponse({
            'success': True,
            'users': [{
                'id': user.id,
                'username': user.username,
                'is_active': user.is_active,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'task_count': len(user.tasks) if hasattr(user, 'tasks') else 0,
                'report_count': db.query(Task).filter(Task.user_id == user.id).count()
            } for user in users]
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.delete('/users/{user_id}')
async def delete_user(user_id: int, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除用户及其所有关联数据（仅管理员）"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse({
                'success': False,
                'error': '用户不存在'
            }, status_code=404)
        
        # 不能删除自己
        if user.id == current_admin.id:
            return JSONResponse({
                'success': False,
                'error': '不能删除当前登录的管理员账号'
            }, status_code=400)
        
        # 删除用户（级联删除会自动删除关联的任务）
        db.delete(user)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': f'用户 {user.username} 及其所有关联数据已删除'
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.get('/users/{user_id}/reports')
async def get_user_reports(user_id: int, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取指定用户的所有报告列表（仅管理员）"""
    try:
        import json
        
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse({
                'success': False,
                'error': '用户不存在'
            }, status_code=404)
        
        # 获取用户的所有任务
        tasks = db.query(Task).filter(Task.user_id == user_id).order_by(Task.started_at.desc()).all()
        
        reports = []
        for task in tasks:
            # 获取生成数据条数
            data_count = get_generated_data_count(task.task_id, user_id)
            
            # 获取审核状态
            review_status = get_task_review_status(task.task_id, user_id)
            
            # 解析参数
            params = {}
            if task.params:
                try:
                    params = json.loads(task.params)
                except:
                    pass
            
            reports.append({
                'id': task.id,
                'task_id': task.task_id,
                'status': task.status,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'finished_at': task.finished_at.isoformat() if task.finished_at else None,
                'data_count': data_count,
                'has_data': data_count > 0,
                'params': params,
                'error_message': task.error_message,
                # 审核状态
                'confirmed_count': review_status['confirmed_count'],
                'is_fully_reviewed': review_status['is_fully_reviewed']
            })
        
        return JSONResponse({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username
            },
            'reports': reports
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.get('/users/{user_id}/reports/{task_id}/download')
async def download_user_report(user_id: int, task_id: str, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """下载指定用户的报告数据（仅管理员）"""
    try:
        import json
        from urllib.parse import unquote, quote
        from fastapi.responses import Response
        
        # 解码 task_id
        decoded_task_id = unquote(task_id)
        
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 获取生成的数据
        data_list = get_generated_data_by_task(decoded_task_id, user_id)
        
        if not data_list:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="该任务没有生成数据")
        
        # 生成 JSONL 内容
        jsonl_lines = []
        for item in data_list:
            jsonl_lines.append(json.dumps(item, ensure_ascii=False))
        content = '\n'.join(jsonl_lines)
        content_bytes = content.encode('utf-8')
        
        # 生成文件名
        safe_task_id = decoded_task_id.replace('/', '_').replace('\\', '_').replace(':', '_')
        filename = f"generated_data_{user.username}_{safe_task_id}.jsonl"
        encoded_filename = quote(filename, safe='')
        
        return Response(
            content=content_bytes,
            media_type='application/x-jsonlines',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        if hasattr(e, 'status_code'):
            raise
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


# ==================== 模型管理 ====================

@router.get('/models')
async def get_all_models(current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有模型配置（仅管理员）"""
    try:
        models = db.query(ModelConfig).all()
        return JSONResponse({
            'success': True,
            'models': [{
                'id': model.id,
                'name': model.name,
                'api_url': model.api_url,
                'api_key': model.api_key,
                'model_path': model.model_path,
                'max_concurrent': model.max_concurrent,
                'temperature': model.temperature,
                'top_p': model.top_p,
                'max_tokens': model.max_tokens,
                'is_vllm': model.is_vllm,
                'timeout': model.timeout,
                'description': model.description,
                'is_active': model.is_active,
                'created_at': model.created_at.isoformat() if model.created_at else None
            } for model in models]
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.post('/models')
async def create_model(request: Request, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """创建模型配置（仅管理员）"""
    try:
        data = await request.json()
        
        # 检查必填字段
        if not data.get('name') or not data.get('api_url') or not data.get('model_path'):
            return JSONResponse({
                'success': False,
                'error': '模型名称、API地址和模型路径为必填项'
            }, status_code=400)
        
        # 检查名称是否已存在
        existing = db.query(ModelConfig).filter(ModelConfig.name == data['name']).first()
        if existing:
            return JSONResponse({
                'success': False,
                'error': f"模型名称 '{data['name']}' 已存在"
            }, status_code=400)
        
        model = ModelConfig(
            name=data['name'],
            api_url=data['api_url'],
            api_key=data.get('api_key', 'sk-xxxxx'),
            model_path=data['model_path'],
            max_concurrent=data.get('max_concurrent', 16),
            temperature=data.get('temperature', 1.0),
            top_p=data.get('top_p', 1.0),
            max_tokens=data.get('max_tokens', 2048),
            is_vllm=data.get('is_vllm', True),
            timeout=data.get('timeout', 600),
            description=data.get('description', ''),
            is_active=data.get('is_active', True)
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        
        return JSONResponse({
            'success': True,
            'model': {
                'id': model.id,
                'name': model.name,
                'api_url': model.api_url,
                'api_key': model.api_key,
                'model_path': model.model_path,
                'max_concurrent': model.max_concurrent,
                'temperature': model.temperature,
                'top_p': model.top_p,
                'max_tokens': model.max_tokens,
                'is_vllm': model.is_vllm,
                'timeout': model.timeout,
                'description': model.description,
                'is_active': model.is_active
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.put('/models/{model_id}')
async def update_model(model_id: int, request: Request, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """更新模型配置（仅管理员）"""
    try:
        model = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
        if not model:
            return JSONResponse({
                'success': False,
                'error': '模型不存在'
            }, status_code=404)
        
        data = await request.json()
        
        # 更新字段
        if 'name' in data:
            # 检查新名称是否与其他模型冲突
            existing = db.query(ModelConfig).filter(
                ModelConfig.name == data['name'],
                ModelConfig.id != model_id
            ).first()
            if existing:
                return JSONResponse({
                    'success': False,
                    'error': f"模型名称 '{data['name']}' 已被其他模型使用"
                }, status_code=400)
            model.name = data['name']
        
        if 'api_url' in data:
            model.api_url = data['api_url']
        if 'api_key' in data:
            model.api_key = data['api_key']
        if 'model_path' in data:
            model.model_path = data['model_path']
        if 'max_concurrent' in data:
            model.max_concurrent = data['max_concurrent']
        if 'temperature' in data:
            model.temperature = data['temperature']
        if 'top_p' in data:
            model.top_p = data['top_p']
        if 'max_tokens' in data:
            model.max_tokens = data['max_tokens']
        if 'is_vllm' in data:
            model.is_vllm = data['is_vllm']
        if 'timeout' in data:
            model.timeout = data['timeout']
        if 'description' in data:
            model.description = data['description']
        if 'is_active' in data:
            model.is_active = data['is_active']
        
        model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        
        return JSONResponse({
            'success': True,
            'model': {
                'id': model.id,
                'name': model.name,
                'api_url': model.api_url,
                'api_key': model.api_key,
                'model_path': model.model_path,
                'max_concurrent': model.max_concurrent,
                'temperature': model.temperature,
                'top_p': model.top_p,
                'max_tokens': model.max_tokens,
                'is_vllm': model.is_vllm,
                'timeout': model.timeout,
                'description': model.description,
                'is_active': model.is_active
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.delete('/models/{model_id}')
async def delete_model(model_id: int, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除模型配置（仅管理员）"""
    try:
        model = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
        if not model:
            return JSONResponse({
                'success': False,
                'error': '模型不存在'
            }, status_code=404)
        
        db.delete(model)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': f'模型 {model.name} 已删除'
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


# ==================== 任务管理 ====================

@router.get('/tasks')
async def get_all_admin_tasks(current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有用户的数据库任务记录（仅管理员）"""
    try:
        tasks = db.query(Task).all()
        return JSONResponse({
            'success': True,
            'tasks': [{
                'id': task.id,
                'task_id': task.task_id,
                'username': task.user.username if task.user else 'Unknown',
                'status': task.status,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'finished_at': task.finished_at.isoformat() if task.finished_at else None,
                'params': task.params,
                'error_message': task.error_message
            } for task in tasks]
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


@router.delete('/tasks/{task_db_id}')
async def delete_admin_task(task_db_id: int, current_admin=Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除数据库任务记录（仅管理员）"""
    try:
        task = db.query(Task).filter(Task.id == task_db_id).first()
        if not task:
            return JSONResponse({
                'success': False,
                'error': '任务不存在'
            }, status_code=404)
        
        task_id = task.task_id
        db.delete(task)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': f'任务 {task_id} 已删除'
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)
