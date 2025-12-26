#!/usr/bin/env python3
"""
报告管理路由
包括任务报告的列表查询、数据查看、删除等
"""

import json
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db
from database.auth import get_current_user
from database.generated_data_service import (
    get_generated_data_by_task,
    get_generated_data_count,
    get_generated_data_with_ids
)

router = APIRouter(prefix='/api', tags=['报告管理'])


@router.get('/reports')
async def get_user_reports(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户的所有任务报告列表（含生成数据统计）"""
    try:
        from database.models import Task
        
        # 获取用户的所有任务
        tasks = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.started_at.desc()).all()
        
        reports = []
        for task in tasks:
            # 获取生成数据条数
            data_count = get_generated_data_count(task.task_id, current_user.id)
            
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
                'error_message': task.error_message
            })
        
        return JSONResponse({
            'success': True,
            'reports': reports
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取报告列表失败: {str(e)}"
        )


@router.get('/reports/{task_id}/data')
async def get_report_data(task_id: str, current_user=Depends(get_current_user)):
    """获取指定任务的生成数据（用于预览）"""
    try:
        from urllib.parse import unquote
        
        # 确保 task_id 正确解码（处理中文等特殊字符）
        decoded_task_id = unquote(task_id)
        
        # 获取生成的数据
        data_list = get_generated_data_by_task(decoded_task_id, current_user.id)
        
        if not data_list:
            return JSONResponse({
                'success': True,
                'data': [],
                'count': 0
            })
        
        return JSONResponse({
            'success': True,
            'data': data_list,
            'count': len(data_list)
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取生成数据失败: {str(e)}"
        )


@router.get('/reports/{task_id}/data/editable')
async def get_report_data_editable(task_id: str, current_user=Depends(get_current_user)):
    """获取指定任务的生成数据（包含ID，用于编辑）"""
    try:
        from urllib.parse import unquote
        
        # 确保 task_id 正确解码
        decoded_task_id = unquote(task_id)
        
        # 获取带ID的生成数据
        data_list = get_generated_data_with_ids(decoded_task_id, current_user.id)
        
        if not data_list:
            return JSONResponse({
                'success': True,
                'data': [],
                'count': 0
            })
        
        return JSONResponse({
            'success': True,
            'data': data_list,
            'count': len(data_list)
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取生成数据失败: {str(e)}"
        )


@router.delete('/reports/{task_id}')
async def delete_report(task_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """删除单个报告（删除任务和关联的生成数据）"""
    try:
        from database.models import Task, GeneratedData
        from urllib.parse import unquote
        
        # 确保 task_id 正确解码（处理中文等特殊字符）
        decoded_task_id = unquote(task_id)
        
        # 查找任务
        task = db.query(Task).filter(
            Task.task_id == decoded_task_id,
            Task.user_id == current_user.id
        ).first()
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail="报告不存在或无权删除"
            )
        
        # 删除关联的生成数据
        db.query(GeneratedData).filter(
            GeneratedData.task_id == decoded_task_id,
            GeneratedData.user_id == current_user.id
        ).delete()
        
        # 删除任务
        db.delete(task)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': f'报告 {decoded_task_id} 已删除'
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"删除报告失败: {str(e)}"
        )


@router.post('/reports/batch_delete')
async def batch_delete_reports(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量删除报告（删除任务和关联的生成数据）"""
    try:
        from database.models import Task, GeneratedData
        
        data = await request.json()
        task_ids = data.get('task_ids', [])
        
        if not task_ids:
            raise HTTPException(
                status_code=400,
                detail="请选择要删除的报告"
            )
        
        deleted_count = 0
        errors = []
        
        for task_id in task_ids:
            try:
                # 查找任务
                task = db.query(Task).filter(
                    Task.task_id == task_id,
                    Task.user_id == current_user.id
                ).first()
                
                if not task:
                    errors.append({'task_id': task_id, 'error': '任务不存在或无权删除'})
                    continue
                
                # 删除关联的生成数据
                db.query(GeneratedData).filter(
                    GeneratedData.task_id == task_id,
                    GeneratedData.user_id == current_user.id
                ).delete()
                
                # 删除任务
                db.delete(task)
                deleted_count += 1
            except Exception as e:
                errors.append({'task_id': task_id, 'error': str(e)})
        
        db.commit()
        
        return JSONResponse({
            'success': True,
            'deleted_count': deleted_count,
            'errors': errors,
            'message': f'成功删除 {deleted_count} 个报告' + (f'，{len(errors)} 个失败' if errors else '')
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"批量删除报告失败: {str(e)}"
        )

