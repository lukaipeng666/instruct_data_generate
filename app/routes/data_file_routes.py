#!/usr/bin/env python3
"""
数据文件管理路由
包括文件上传、删除、列表查询、内容编辑等
"""

import json
from fastapi import APIRouter, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db
from database.auth import get_current_user
from database.file_service import (
    create_data_file,
    get_data_file_by_id,
    get_user_data_files,
    delete_data_file,
    delete_data_files_batch,
)
from routes.file_conversion_utils import convert_csv_to_jsonl_content, convert_jsonl_to_csv_content
from routes.validation_utils import validate_turns_balance

router = APIRouter(prefix='/api', tags=['数据文件管理'])


@router.get('/task_types')
def get_task_types(current_user=Depends(get_current_user)):
    """获取支持的任务类型列表"""
    from config.tools import FORMAT_EVALUATORS
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
    """下载数据文件（JSONL格式，使用数据库中存储的原始文件名）"""
    try:
        # 获取文件信息
        data_file = get_data_file_by_id(db, file_id, current_user.id)
        if not data_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权访问"
            )
        
        # 直接使用数据库中存储的原始文件名
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


@router.get('/data_files/{file_id}/content/editable')
async def get_data_file_content_editable(file_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取数据文件内容（带索引，用于编辑）"""
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
        
        items = []
        for index, line in enumerate(content_text.strip().split('\n')):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                items.append({
                    'index': index,
                    'data': obj
                })
            except json.JSONDecodeError as e:
                items.append({
                    'index': index,
                    'data': {'_raw': line, '_error': str(e)}
                })
        
        return JSONResponse({
            'success': True,
            'file_id': file_id,
            'filename': data_file.filename,
            'total_lines': len(items),
            'items': items
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件内容失败: {str(e)}"
        )


@router.put('/data_files/{file_id}/content/{item_index}')
async def update_data_file_item(file_id: int, item_index: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """更新数据文件中的单条数据"""
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
        
        # 获取文件
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
        
        lines = content_text.strip().split('\n')
        
        # 检查索引是否有效
        if item_index < 0 or item_index >= len(lines):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"索引 {item_index} 超出范围，文件共有 {len(lines)} 条数据"
            )
        
        # 更新指定行
        lines[item_index] = json.dumps(new_content, ensure_ascii=False)
        
        # 重新组合内容
        new_file_content = '\n'.join(lines) + '\n'
        new_file_bytes = new_file_content.encode('utf-8')
        
        # 更新数据库
        data_file.file_content = new_file_bytes
        data_file.file_size = len(new_file_bytes)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': '数据更新成功'
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新数据失败: {str(e)}"
        )


@router.post('/data_files/{file_id}/content')
async def add_data_file_item(file_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """向数据文件添加新数据"""
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
        
        # 获取文件
        data_file = get_data_file_by_id(db, file_id, current_user.id)
        if not data_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或无权访问"
            )
        
        # 解析现有JSONL内容
        try:
            content_text = data_file.file_content.decode('utf-8')
        except UnicodeDecodeError:
            content_text = data_file.file_content.decode('utf-8-sig')
        
        # 处理空文件情况
        lines = [line for line in content_text.strip().split('\n') if line.strip()]
        
        # 添加新行
        new_line = json.dumps(new_content, ensure_ascii=False)
        lines.append(new_line)
        
        # 重新组合内容
        new_file_content = '\n'.join(lines) + '\n'
        new_file_bytes = new_file_content.encode('utf-8')
        
        # 更新数据库
        data_file.file_content = new_file_bytes
        data_file.file_size = len(new_file_bytes)
        db.commit()
        
        return JSONResponse({
            'success': True,
            'message': '数据添加成功',
            'new_index': len(lines) - 1,
            'total_count': len(lines)
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据失败: {str(e)}"
        )


@router.delete('/data_files/{file_id}/content/batch')
async def batch_delete_data_file_items(file_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量删除数据文件中的多条数据"""
    try:
        data = await request.json()
        indices = data.get('indices', [])  # 要删除的索引列表
        
        if not indices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请指定要删除的数据索引"
            )
        
        # 获取文件
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
        
        lines = content_text.strip().split('\n')
        total_lines = len(lines)
        
        # 验证索引是否有效
        invalid_indices = [i for i in indices if i < 0 or i >= total_lines]
        if invalid_indices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"索引超出范围: {invalid_indices}，文件共有 {total_lines} 条数据（索引 0-{total_lines-1}）"
            )
        
        # 删除指定索引的行（保留不在 indices 中的行）
        indices_set = set(indices)
        new_lines = [line for i, line in enumerate(lines) if i not in indices_set]
        
        if not new_lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除所有数据，文件至少需要保留一条数据"
            )
        
        # 重新组合内容
        new_file_content = '\n'.join(new_lines) + '\n'
        new_file_bytes = new_file_content.encode('utf-8')
        
        # 更新数据库
        data_file.file_content = new_file_bytes
        data_file.file_size = len(new_file_bytes)
        db.commit()
        
        deleted_count = len(indices)
        return JSONResponse({
            'success': True,
            'message': f'成功删除 {deleted_count} 条数据',
            'deleted_count': deleted_count,
            'remaining_count': len(new_lines)
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除失败: {str(e)}"
        )


@router.post('/data_files/batch_download')
async def batch_download_data_files(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量下载数据文件（打包成ZIP）"""
    try:
        import zipfile
        from io import BytesIO
        from datetime import datetime
        
        data = await request.json()
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要下载的文件"
            )
        
        # 创建ZIP文件
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for index, file_id in enumerate(file_ids):
                # 获取文件信息
                data_file = get_data_file_by_id(db, file_id, current_user.id)
                if not data_file:
                    continue
                
                # 添加文件到ZIP（使用原始文件名，添加数字前缀避免重复）
                # 格式：序号_原文件名，例如：1_data.jsonl
                original_filename = data_file.filename
                zip_filename = f"{index + 1}_{original_filename}"
                
                # 从数据库内容转换为文件对象
                file_content = data_file.file_content
                zip_file.writestr(zip_filename, file_content)
        
        zip_buffer.seek(0)
        
        # 生成ZIP文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"data_files_{timestamp}.zip"
        
        # 返回ZIP文件
        return Response(
            content=zip_buffer.getvalue(),
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="{zip_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量下载失败: {str(e)}"
        )

