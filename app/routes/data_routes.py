#!/usr/bin/env python3
"""
数据文件管理路由
包括文件上传、删除、列表查询等
"""

import os
import csv
import json
import io
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db
from database.auth import get_current_user
from database.file_service import (
    create_data_file,
    get_data_file_by_id,
    get_user_data_files,
    delete_data_file,
    delete_data_files_batch,
    get_file_content
)
from database.generated_data_service import (
    get_generated_data_by_task,
    get_generated_data_count,
    get_generated_data_with_ids,
    update_generated_data,
    confirm_generated_data
)
from config.tools import FORMAT_EVALUATORS

router = APIRouter(prefix='/api', tags=['数据管理'])


@router.get('/task_types')
def get_task_types(current_user=Depends(get_current_user)):
    """获取支持的任务类型列表"""
    return JSONResponse({
        'success': True,
        'types': list(FORMAT_EVALUATORS.keys())
    })


@router.get('/data_files')
async def get_data_files(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户上传的数据文件列表（从数据库读取）"""
    try:
        # 从数据库获取用户文件
        data_files = get_user_data_files(db, current_user.id)
        
        files = []
        for data_file in data_files:
            files.append({
                'id': data_file.id,  # 使用数据库ID
                'name': data_file.filename,
                'size': data_file.file_size,
                'upload_time': data_file.created_at.isoformat(),
                'path': f'db://{data_file.id}/{data_file.filename}'  # 虚拟路径，表示存储在数据库中
            })
        
        return JSONResponse({
            'success': True,
            'files': files
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


def convert_csv_to_jsonl_content(csv_content: bytes) -> bytes:
    """
    将CSV内容转换为JSONL格式
    基于csv_to_jsonl.py的逻辑
    """
    # 解码CSV内容
    try:
        csv_text = csv_content.decode('utf-8-sig')
    except UnicodeDecodeError:
        csv_text = csv_content.decode('utf-8')
    
    csv_reader = csv.reader(io.StringIO(csv_text))
    
    # 读取列名
    headers = next(csv_reader)
    
    # 提取所有 Human 和 Assistant 列的索引
    human_indices = [i for i, col in enumerate(headers) if col == "Human"]
    assistant_indices = [i for i, col in enumerate(headers) if col == "Assistant"]
    
    # 验证第一列是否为 meta
    if headers[0] != "meta":
        raise ValueError("CSV 第一列必须命名为 'meta'")
    
    # 记录当前活跃的 meta（用于共享逻辑）
    current_active_meta = ""
    
    jsonl_lines = []
    for row in csv_reader:
        if not row:  # 跳过空行
            continue
        
        # 处理当前行的 meta（支持共享逻辑）
        row_meta = row[0].strip() if len(row) > 0 else ""
        if row_meta:  # 如果当前行 meta 非空，更新活跃 meta
            current_active_meta = row_meta
        # 若当前行 meta 为空，则沿用之前的活跃 meta
        
        # 提取多轮对话内容
        turns = []
        for h_idx, a_idx in zip(human_indices, assistant_indices):
            # 添加 Human 内容（非空才添加）
            if h_idx < len(row) and row[h_idx].strip():
                turns.append({
                    "role": "Human",
                    "text": row[h_idx].strip()
                })
            # 添加 Assistant 内容（非空才添加）
            if a_idx < len(row) and row[a_idx].strip():
                turns.append({
                    "role": "Assistant",
                    "text": row[a_idx].strip()
                })
        
        # 构造输出对象
        output_obj = {
            "meta": {"meta_description": current_active_meta},
            "turns": turns
        }
        # 添加到JSONL行
        jsonl_lines.append(json.dumps(output_obj, ensure_ascii=False))
    
    # 合并为JSONL内容
    jsonl_content = '\n'.join(jsonl_lines) + '\n'
    return jsonl_content.encode('utf-8')


@router.post('/data_files/upload')
async def upload_data_file(file: UploadFile = File(...), current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """上传数据文件（支持jsonl和csv格式），存储到数据库"""
    try:
        # 检查文件格式
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        is_csv = file.filename.endswith('.csv')
        is_jsonl = file.filename.endswith('.jsonl')
        
        if not is_csv and not is_jsonl:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只支持上传 .jsonl 或 .csv 格式的文件"
            )
        
        # 读取文件内容
        content = await file.read()
        
        # 如果是CSV文件，转换为JSONL格式
        if is_csv:
            try:
                content = convert_csv_to_jsonl_content(content)
                # 修改文件名为.jsonl后缀
                filename = file.filename[:-4] + '.jsonl'
            except ValueError as ve:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV格式错误: {str(ve)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CSV转换失败: {str(e)}"
                )
        else:
            filename = file.filename
        
        # 保存到数据库
        data_file = create_data_file(
            db=db,
            user_id=current_user.id,
            filename=filename,
            file_content=content,
            content_type='application/x-jsonlines'
        )
        
        return JSONResponse({
            'success': True,
            'file': {
                'id': data_file.id,
                'name': data_file.filename,
                'size': data_file.file_size,
                'upload_time': data_file.created_at.isoformat(),
                'path': f'db://{data_file.id}/{data_file.filename}'
            },
            'message': f'文件上传成功{"（已从CSV转换为JSONL）" if is_csv else ""}'
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传文件失败: {str(e)}"
        )


@router.delete('/data_files/{file_id}')
async def delete_data_file_route(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """删除数据文件（从数据库删除）"""
    try:
        # 从数据库删除
        if not delete_data_file(db, file_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权删除"
            )
        
        return JSONResponse({
            'success': True,
            'message': f'文件 ID:{file_id} 已删除'
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文件失败: {str(e)}"
        )


@router.post('/data_files/batch_delete')
async def batch_delete_data_files(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量删除数据文件（从数据库删除）"""
    try:
        data = await request.json()
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要删除的文件"
            )
        
        # 从数据库批量删除
        deleted_count, errors = delete_data_files_batch(db, file_ids, current_user.id)
        
        return JSONResponse({
            'success': True,
            'deleted_count': deleted_count,
            'errors': errors,
            'message': f'成功删除 {deleted_count} 个文件' + (f'，{len(errors)} 个失败' if errors else '')
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除失败: {str(e)}"
        )


@router.get('/data_files/{file_id}/download')
async def download_data_file(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """下载数据文件（JSONL格式，从数据库读取）"""
    try:
        # 获取文件信息
        data_file = get_data_file_by_id(db, file_id, current_user.id)
        if not data_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权访问"
            )
        
        # 返回文件内容
        from urllib.parse import quote
        encoded_filename = quote(data_file.filename, safe='')
        
        return Response(
            content=data_file.file_content,
            media_type=data_file.content_type,
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}"
        )


def convert_jsonl_to_csv_content(jsonl_content: bytes) -> bytes:
    """
    将JSONL内容转换为CSV格式
    基于jsonl_to_csv.py的逻辑
    """
    # 解码JSONL内容
    try:
        jsonl_text = jsonl_content.decode('utf-8')
    except UnicodeDecodeError:
        jsonl_text = jsonl_content.decode('utf-8-sig')
    
    # 用字典归类：key=meta值，value=该meta对应的所有行数据
    meta_groups: Dict[str, List[List[str]]] = {}
    
    for line in jsonl_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        
        # 提取meta
        meta = (((obj.get("meta") or {}).get("meta_description")) or "").strip() or "__empty_meta__"
        
        # 提取对话内容
        turns = obj.get("turns") or []
        human_texts: List[str] = []
        assistant_texts: List[str] = []
        for msg in turns:
            role = (msg.get("role") or "").strip()
            text = (msg.get("text") or "").strip()
            if role == "Human":
                human_texts.append(text)
            elif role == "Assistant":
                assistant_texts.append(text)
        
        # 补齐对话轮次
        max_turns = max(len(human_texts), len(assistant_texts))
        human_texts += [""] * (max_turns - len(human_texts))
        assistant_texts += [""] * (max_turns - len(assistant_texts))
        
        # 合并为对话对列表
        conversation: List[str] = []
        for h, a in zip(human_texts, assistant_texts):
            conversation.extend([h, a])
        
        # 加入对应meta的分组
        if meta not in meta_groups:
            meta_groups[meta] = []
        meta_groups[meta].append(conversation)
    
    # 整理所有行数据
    all_rows: List[List[str]] = []
    for meta, conversations in meta_groups.items():
        for i, conv in enumerate(conversations):
            if i == 0:
                row = [meta if meta != "__empty_meta__" else ""] + conv
            else:
                row = [""] + conv
            all_rows.append(row)
    
    # 生成表头
    max_conv_length = max(len(row) - 1 for row in all_rows) if all_rows else 0
    num_turns = max_conv_length // 2
    headers: List[str] = ["meta"]
    for i in range(num_turns):
        headers.append(f"Human_{i+1}")
        headers.append(f"Assistant_{i+1}")
    
    # 补齐所有行的长度
    for row in all_rows:
        row += [""] * (len(headers) - len(row))
    
    # 写入CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(all_rows)
    
    return output.getvalue().encode('utf-8-sig')


@router.get('/data_files/{file_id}/download_csv')
async def download_data_file_as_csv(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """下载数据文件（CSV格式，从JSONL转换）"""
    try:
        # 获取文件信息
        data_file = get_data_file_by_id(db, file_id, current_user.id)
        if not data_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权访问"
            )
        
        # 转换为CSV格式
        try:
            csv_content = convert_jsonl_to_csv_content(data_file.file_content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"JSONL转换CSV失败: {str(e)}"
            )
        
        # 生成CSV文件名
        csv_filename = data_file.filename.replace('.jsonl', '.csv') if data_file.filename.endswith('.jsonl') else data_file.filename + '.csv'
        
        from urllib.parse import quote
        encoded_filename = quote(csv_filename, safe='')
        
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
            detail=f"下载CSV文件失败: {str(e)}"
        )


@router.get('/data_files/{file_id}/content')
async def get_data_file_content(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """查看数据文件内容（解析每一条JSONL）"""
    try:
        # 获取文件信息
        data_file = get_data_file_by_id(db, file_id, current_user.id)
        if not data_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权访问"
            )
        
        # 解析JSONL内容
        try:
            content_text = data_file.file_content.decode('utf-8')
        except UnicodeDecodeError:
            content_text = data_file.file_content.decode('utf-8-sig')
        
        lines = []
        for line in content_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                lines.append(obj)
            except json.JSONDecodeError as e:
                # 如果解析失败，保留原始字符串
                lines.append({"_raw": line, "_error": str(e)})
        
        return JSONResponse({
            'success': True,
            'file_id': file_id,
            'filename': data_file.filename,
            'total_lines': len(lines),
            'data': lines
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件内容失败: {str(e)}"
        )


@router.get('/generated_data/{task_id}/download')
async def download_generated_data(task_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """下载任务生成的数据（JSONL格式）"""
    try:
        import json
        from urllib.parse import unquote
        import traceback
        
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
        from urllib.parse import quote
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


@router.get('/reports')
async def get_user_reports(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户的所有任务报告列表（含生成数据统计）"""
    try:
        from database.models import Task
        import json
        
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取生成数据失败: {str(e)}"
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
                status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                status_code=status.HTTP_400_BAD_REQUEST,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除报告失败: {str(e)}"
        )
