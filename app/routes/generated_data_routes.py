#!/usr/bin/env python3
"""
生成数据管理路由
包括生成数据的下载、编辑、确认、添加和批量删除
"""

import json
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db
from database.auth import get_current_user
from database.generated_data_service import (
    get_generated_data_by_task,
    get_generated_data_count,
    get_generated_data_with_ids,
    update_generated_data,
    confirm_generated_data
)
from routes.file_conversion_utils import convert_jsonl_to_csv_content
from routes.validation_utils import validate_turns_balance

router = APIRouter(prefix='/api', tags=['生成数据管理'])


@router.get('/generated_data/{task_id}/download')
async def download_generated_data(task_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """下载任务生成的数据（JSONL格式）"""
    try:
        from urllib.parse import unquote, quote
        
        # 确保 task_id 正确解码（处理中文等特殊字符）
        decoded_task_id = unquote(task_id)
        print(f"[Download] task_id: {task_id}, decoded: {decoded_task_id}, user_id: {current_user.id}")
        
        # 获取生成的数据
        data_list = get_generated_data_by_task(decoded_task_id, current_user.id)
        print(f"[Download] data_list count: {len(data_list) if data_list else 0}")
        
        if not data_list:
            # 检查任务是否存在
            from database.models import Task
            task = db.query(Task).filter(
                Task.task_id == decoded_task_id,
                Task.user_id == current_user.id
            ).first()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"任务不存在或无权访问: {decoded_task_id}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"任务 '{decoded_task_id}' 没有生成数据，请确认任务已完成并成功生成了数据"
                )
        
        # 将数据转换为JSONL格式
        jsonl_lines = []
        for data_item in data_list:
            json_line = json.dumps(data_item, ensure_ascii=False)
            jsonl_lines.append(json_line)
        
        # 合并为一个字符串
        jsonl_content = '\n'.join(jsonl_lines) + '\n'
        
        # 转换为字节
        content_bytes = jsonl_content.encode('utf-8')
        
        # 生成文件名（处理特殊字符）
        safe_task_id = decoded_task_id.replace('/', '_').replace('\\', '_').replace(':', '_')
        filename = f"generated_data_{safe_task_id}.jsonl"
        
        print(f"[Download] Success! Returning {len(content_bytes)} bytes")
        
        # 对文件名进行 URL 编码以支持中文等特殊字符
        # 使用 RFC 5987 规范的 filename* 参数
        encoded_filename = quote(filename, safe='')
        
        # 返回文件
        return Response(
            content=content_bytes,
            media_type='application/x-jsonlines',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"下载生成数据失败: {str(e)}"
        print(f"[Download Error] {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )


@router.get('/generated_data/{task_id}/info')
async def get_generated_data_info(task_id: str, current_user=Depends(get_current_user)):
    """获取任务生成数据的统计信息"""
    try:
        from urllib.parse import unquote
        
        # 确保 task_id 正确解码（处理中文等特殊字符）
        decoded_task_id = unquote(task_id)
        
        # 获取数据条数
        count = get_generated_data_count(decoded_task_id, current_user.id)
        
        return JSONResponse({
            'success': True,
            'task_id': decoded_task_id,
            'count': count,
            'has_data': count > 0
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取生成数据信息失败: {str(e)}"
        )


@router.get('/generated_data/{task_id}/download_csv')
async def download_generated_data_as_csv(task_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """下载任务生成的数据（CSV格式）"""
    try:
        from urllib.parse import unquote, quote
        
        # 确保 task_id 正确解码
        decoded_task_id = unquote(task_id)
        
        # 获取生成的数据
        data_list = get_generated_data_by_task(decoded_task_id, current_user.id)
        
        if not data_list:
            from database.models import Task
            task = db.query(Task).filter(
                Task.task_id == decoded_task_id,
                Task.user_id == current_user.id
            ).first()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"任务不存在或无权访问: {decoded_task_id}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"任务 '{decoded_task_id}' 没有生成数据"
                )
        
        # 先将数据转换为JSONL格式
        jsonl_lines = []
        for data_item in data_list:
            json_line = json.dumps(data_item, ensure_ascii=False)
            jsonl_lines.append(json_line)
        
        jsonl_content = '\n'.join(jsonl_lines) + '\n'
        jsonl_bytes = jsonl_content.encode('utf-8')
        
        # 转换为CSV格式
        try:
            csv_content = convert_jsonl_to_csv_content(jsonl_bytes)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"JSONL转换CSV失败: {str(e)}"
            )
        
        # 生成文件名
        safe_task_id = decoded_task_id.replace('/', '_').replace('\\', '_').replace(':', '_')
        filename = f"generated_data_{safe_task_id}.csv"
        encoded_filename = quote(filename, safe='')
        
        return Response(
            content=csv_content,
            media_type='text/csv',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载CSV失败: {str(e)}"
        )


@router.put('/generated_data/{data_id}')
async def update_generated_data_item(data_id: int, request: Request, current_user=Depends(get_current_user)):
    """更新单条生成数据"""
    try:
        data = await request.json()
        new_content = data.get('content')
        
        if not new_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少数据内容"
            )
        
        # 验证 Human 和 Assistant 数量是否一致
        turns = new_content.get('turns', [])
        is_valid, error_msg = validate_turns_balance(turns)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # 更新数据
        success = update_generated_data(data_id, current_user.id, new_content)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="数据不存在或无权修改"
            )
        
        return JSONResponse({
            'success': True,
            'message': '数据更新成功'
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据失败: {str(e)}"
        )


@router.post('/generated_data/{data_id}/confirm')
async def confirm_generated_data_item(data_id: int, request: Request, current_user=Depends(get_current_user)):
    """确认单条生成数据可用"""
    try:
        data = await request.json()
        is_confirmed = data.get('is_confirmed', True)
        
        # 确认数据
        success = confirm_generated_data(data_id, current_user.id, is_confirmed)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="数据不存在或无权操作"
            )
        
        return JSONResponse({
            'success': True,
            'message': '确认状态已更新' if is_confirmed else '已取消确认'
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认数据失败: {str(e)}"
        )


@router.post('/generated_data/{task_id}')
async def add_generated_data_item(task_id: str, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """向任务添加新的生成数据"""
    try:
        from database.models import GeneratedData, Task
        from urllib.parse import unquote
        
        data = await request.json()
        new_content = data.get('content')
        
        if not new_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少数据内容"
            )
        
        # 验证 Human 和 Assistant 数量是否一致
        turns = new_content.get('turns', [])
        is_valid, error_msg = validate_turns_balance(turns)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # 确保 task_id 正确解码
        decoded_task_id = unquote(task_id)
        
        # 检查任务是否存在
        task = db.query(Task).filter(
            Task.task_id == decoded_task_id,
            Task.user_id == current_user.id
        ).first()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )
        
        # 创建新的生成数据
        new_data = GeneratedData(
            task_id=decoded_task_id,
            user_id=current_user.id,
            data=new_content,
            is_confirmed=False
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        return JSONResponse({
            'success': True,
            'message': '数据添加成功',
            'data_id': new_data.id
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据失败: {str(e)}"
        )


@router.delete('/generated_data/batch')
async def batch_delete_generated_data(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量删除生成数据"""
    try:
        from database.models import GeneratedData
        
        data = await request.json()
        data_ids = data.get('data_ids', [])  # 要删除的数据 ID 列表
        
        if not data_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请指定要删除的数据"
            )
        
        # 查找属于当前用户的数据
        existing_data = db.query(GeneratedData).filter(
            GeneratedData.id.in_(data_ids),
            GeneratedData.user_id == current_user.id
        ).all()
        
        if not existing_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到要删除的数据或无权删除"
            )
        
        # 删除数据
        deleted_count = 0
        for item in existing_data:
            db.delete(item)
            deleted_count += 1
        
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': f'成功删除 {deleted_count} 条数据',
            'deleted_count': deleted_count
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除失败: {str(e)}"
        )

