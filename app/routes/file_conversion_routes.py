#!/usr/bin/env python3
"""
文件转换路由
提供批量转换、直接上传转换等功能
"""

import zipfile
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db
from database.auth import get_current_user
from database.file_service import get_data_file_by_id
from routes.file_conversion_utils import convert_csv_to_jsonl_content, convert_jsonl_to_csv_content

router = APIRouter(prefix='/api', tags=['文件转换'])


@router.post('/data_files/batch_convert')
async def batch_convert_data_files(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """批量转换数据文件格式（CSV<->JSONL），打包成ZIP下载"""
    try:
        from io import BytesIO

        data = await request.json()
        file_ids = data.get('file_ids', [])

        if not file_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要转换的文件"
            )

        # 创建ZIP文件
        zip_buffer = BytesIO()

        converted_files = []
        errors = []

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_id in file_ids:
                try:
                    # 获取文件信息
                    data_file = get_data_file_by_id(db, file_id, current_user.id)
                    if not data_file:
                        errors.append({'file_id': file_id, 'error': '文件不存在或无权访问'})
                        continue

                    filename = data_file.filename
                    content = data_file.file_content

                    # 判断文件格式并转换
                    if filename.endswith('.csv'):
                        # CSV -> JSONL
                        converted_content = convert_csv_to_jsonl_content(content)
                        new_filename = filename[:-4] + '.jsonl'
                        conversion_type = 'csv_to_jsonl'
                    elif filename.endswith('.jsonl'):
                        # JSONL -> CSV
                        converted_content = convert_jsonl_to_csv_content(content)
                        new_filename = filename[:-6] + '.csv'
                        conversion_type = 'jsonl_to_csv'
                    else:
                        errors.append({'file_id': file_id, 'filename': filename, 'error': '不支持的文件格式，仅支持.csv和.jsonl'})
                        continue

                    # 添加转换后的文件到ZIP
                    zip_file.writestr(new_filename, converted_content)
                    converted_files.append({
                        'original_filename': filename,
                        'converted_filename': new_filename,
                        'conversion_type': conversion_type
                    })

                except Exception as e:
                    errors.append({'file_id': file_id, 'error': str(e)})

        if not converted_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"没有成功转换任何文件。错误: {errors}"
            )

        zip_buffer.seek(0)

        # 生成ZIP文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"converted_files_{timestamp}.zip"

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
            detail=f"批量转换失败: {str(e)}"
        )


@router.post('/convert_files')
async def convert_files_direct(files: List[UploadFile] = File(...)):
    """直接上传文件并转换格式（CSV<->JSONL），不保存到数据库

    - 单个文件：直接返回转换后的文件
    - 多个文件：打包成ZIP下载
    """
    try:
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要转换的文件"
            )

        converted_files = []
        errors = []

        for index, file in enumerate(files):
            try:
                if not file.filename:
                    errors.append({'index': index, 'error': '文件名为空'})
                    continue

                filename = file.filename
                content = await file.read()

                # 判断文件格式并转换
                if filename.endswith('.csv'):
                    # CSV -> JSONL
                    converted_content = convert_csv_to_jsonl_content(content)
                    new_filename = filename[:-4] + '.jsonl'
                    conversion_type = 'csv_to_jsonl'
                    media_type = 'application/x-jsonlines'
                elif filename.endswith('.jsonl'):
                    # JSONL -> CSV
                    converted_content = convert_jsonl_to_csv_content(content)
                    new_filename = filename[:-6] + '.csv'
                    conversion_type = 'jsonl_to_csv'
                    media_type = 'text/csv'
                else:
                    errors.append({'index': index, 'filename': filename, 'error': '不支持的文件格式，仅支持.csv和.jsonl'})
                    continue

                converted_files.append({
                    'original_filename': filename,
                    'converted_filename': new_filename,
                    'converted_content': converted_content,
                    'media_type': media_type,
                    'conversion_type': conversion_type
                })

            except Exception as e:
                errors.append({'index': index, 'error': str(e)})

        if not converted_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"没有成功转换任何文件。错误: {errors}"
            )

        # 单个文件：直接返回转换后的文件
        if len(converted_files) == 1:
            file_data = converted_files[0]
            from urllib.parse import quote
            encoded_filename = quote(file_data['converted_filename'], safe='')

            return Response(
                content=file_data['converted_content'],
                media_type=file_data['media_type'],
                headers={
                    'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )

        # 多个文件：打包成ZIP
        from io import BytesIO
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_data in converted_files:
                zip_file.writestr(file_data['converted_filename'], file_data['converted_content'])

        zip_buffer.seek(0)

        # 生成ZIP文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"converted_files_{timestamp}.zip"

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
            detail=f"文件转换失败: {str(e)}"
        )

