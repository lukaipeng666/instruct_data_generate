#!/usr/bin/env python3
"""
文件管理服务
提供文件的创建、查询、删除等操作
"""

from sqlalchemy.orm import Session
from .models import DataFile, User
from typing import Optional, List


def create_data_file(
    db: Session,
    user_id: int,
    filename: str,
    file_content: bytes,
    content_type: str = 'application/x-jsonlines'
) -> DataFile:
    """
    创建数据文件记录
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        filename: 文件名
        file_content: 文件内容（二进制）
        content_type: 文件类型
        
    Returns:
        DataFile: 创建的文件对象
    """
    # 检查是否已有同名文件，如果有则添加序号
    existing_files = db.query(DataFile).filter(
        DataFile.user_id == user_id,
        DataFile.filename.like(f"{filename.rsplit('.', 1)[0]}%")
    ).all()
    
    final_filename = filename
    if existing_files:
        base_name = filename.rsplit('.', 1)[0]
        extension = filename.rsplit('.', 1)[1] if '.' in filename else ''
        counter = 1
        
        existing_names = {f.filename for f in existing_files}
        while final_filename in existing_names:
            if extension:
                final_filename = f"{base_name}_{counter}.{extension}"
            else:
                final_filename = f"{base_name}_{counter}"
            counter += 1
    
    # 创建文件记录
    data_file = DataFile(
        user_id=user_id,
        filename=final_filename,
        file_content=file_content,
        file_size=len(file_content),
        content_type=content_type
    )
    
    db.add(data_file)
    db.commit()
    db.refresh(data_file)
    
    return data_file


def get_data_file_by_id(db: Session, file_id: int, user_id: int) -> Optional[DataFile]:
    """
    根据ID获取文件（仅返回当前用户的文件）
    
    Args:
        db: 数据库会话
        file_id: 文件ID
        user_id: 用户ID
        
    Returns:
        DataFile: 文件对象，如果不存在或不属于该用户则返回None
    """
    return db.query(DataFile).filter(
        DataFile.id == file_id,
        DataFile.user_id == user_id
    ).first()


def get_user_data_files(db: Session, user_id: int) -> List[DataFile]:
    """
    获取用户的所有数据文件
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        List[DataFile]: 文件列表
    """
    return db.query(DataFile).filter(
        DataFile.user_id == user_id
    ).order_by(DataFile.created_at.desc()).all()


def delete_data_file(db: Session, file_id: int, user_id: int) -> bool:
    """
    删除数据文件
    
    Args:
        db: 数据库会话
        file_id: 文件ID
        user_id: 用户ID
        
    Returns:
        bool: 删除成功返回True，文件不存在或不属于该用户返回False
    """
    data_file = get_data_file_by_id(db, file_id, user_id)
    if not data_file:
        return False
    
    db.delete(data_file)
    db.commit()
    return True


def delete_data_files_batch(db: Session, file_ids: List[int], user_id: int) -> tuple[int, List[str]]:
    """
    批量删除数据文件
    
    Args:
        db: 数据库会话
        file_ids: 文件ID列表
        user_id: 用户ID
        
    Returns:
        tuple: (成功删除的数量, 错误列表)
    """
    deleted_count = 0
    errors = []
    
    for file_id in file_ids:
        try:
            if delete_data_file(db, file_id, user_id):
                deleted_count += 1
            else:
                errors.append(f"文件ID {file_id}: 文件不存在或无权删除")
        except Exception as e:
            errors.append(f"文件ID {file_id}: {str(e)}")
    
    return deleted_count, errors


def get_file_content(db: Session, file_id: int, user_id: int) -> Optional[bytes]:
    """
    获取文件内容
    
    Args:
        db: 数据库会话
        file_id: 文件ID
        user_id: 用户ID
        
    Returns:
        bytes: 文件内容，如果文件不存在或不属于该用户则返回None
    """
    data_file = get_data_file_by_id(db, file_id, user_id)
    if not data_file:
        return None
    
    return data_file.file_content
