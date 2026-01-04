"""
生成数据服务 - 处理模型生成数据的数据库操作
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from .models import GeneratedData, SessionLocal


def save_generated_data(
    task_id: str,
    user_id: int,
    data_content: Dict[str, Any],
    model_score: Optional[float] = None,
    rule_score: Optional[int] = None,
    retry_count: int = 0,
    generation_model: Optional[str] = None,
    task_type: Optional[str] = None,
    db: Optional[Session] = None
) -> GeneratedData:
    """
    保存单条生成数据到数据库
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
        data_content: 数据内容（字典格式，会自动转换为JSON）
        model_score: 模型评分
        rule_score: 规则评分
        retry_count: 重试次数
        generation_model: 生成模型名称
        task_type: 任务类型
        db: 数据库会话（可选，如果不提供则自动创建）
        
    Returns:
        保存后的GeneratedData对象
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    
    try:
        # 将数据内容转换为JSON字符串
        content_json = json.dumps(data_content, ensure_ascii=False)
        
        # 创建数据记录
        generated_data = GeneratedData(
            task_id=task_id,
            user_id=user_id,
            data_content=content_json,
            model_score=model_score,
            rule_score=rule_score,
            retry_count=retry_count,
            generation_model=generation_model,
            task_type=task_type,
            created_at=datetime.utcnow()
        )
        
        db.add(generated_data)
        db.commit()
        db.refresh(generated_data)
        
        return generated_data
    
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if should_close:
            db.close()


def save_batch_generated_data(
    task_id: str,
    user_id: int,
    data_list: List[Dict[str, Any]],
    generation_model: Optional[str] = None,
    task_type: Optional[str] = None
) -> int:
    """
    批量保存生成数据到数据库
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
        data_list: 数据列表，每个元素是完整的数据字典
        generation_model: 生成模型名称
        task_type: 任务类型
        
    Returns:
        成功保存的数据条数
    """
    db = SessionLocal()
    try:
        saved_count = 0
        
        for data_item in data_list:
            # 提取元数据
            meta = data_item.get('meta', {})
            model_score = meta.get('model_score')
            rule_score = meta.get('rule_score')
            retry_count = meta.get('retry_count', 0)
            
            # 如果meta中没有model信息，使用传入的参数
            gen_model = meta.get('generation_model') or generation_model
            
            # 保存数据
            save_generated_data(
                task_id=task_id,
                user_id=user_id,
                data_content=data_item,
                model_score=model_score,
                rule_score=rule_score,
                retry_count=retry_count,
                generation_model=gen_model,
                task_type=task_type,
                db=db
            )
            saved_count += 1
        
        return saved_count
    
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_generated_data_by_task(
    task_id: str,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    根据任务ID获取生成的数据
    
    Args:
        task_id: 任务ID
        user_id: 用户ID（可选，用于权限过滤）
        
    Returns:
        生成数据列表
    """
    db = SessionLocal()
    try:
        query = db.query(GeneratedData).filter(GeneratedData.task_id == task_id)
        
        if user_id is not None:
            query = query.filter(GeneratedData.user_id == user_id)
        
        results = query.all()
        
        # 转换为字典列表
        data_list = []
        for item in results:
            data_dict = json.loads(item.data_content)
            data_list.append(data_dict)
        
        return data_list
    
    finally:
        db.close()


def get_generated_data_with_ids(
    task_id: str,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    根据任务ID获取生成的数据（包含ID，用于编辑）
    
    Args:
        task_id: 任务ID
        user_id: 用户ID（可选，用于权限过滤）
        
    Returns:
        生成数据列表，每个元素包含 id 和 data 字段
    """
    db = SessionLocal()
    try:
        query = db.query(GeneratedData).filter(GeneratedData.task_id == task_id)
        
        if user_id is not None:
            query = query.filter(GeneratedData.user_id == user_id)
        
        results = query.order_by(GeneratedData.id).all()
        
        # 转换为字典列表，包含ID和确认状态
        data_list = []
        for item in results:
            data_dict = json.loads(item.data_content)
            data_list.append({
                'id': item.id,
                'data': data_dict,
                'is_confirmed': item.is_confirmed if hasattr(item, 'is_confirmed') else False,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'updated_at': item.updated_at.isoformat() if item.updated_at else None
            })
        
        return data_list
    
    finally:
        db.close()


def update_generated_data(
    data_id: int,
    user_id: int,
    new_content: Dict[str, Any]
) -> bool:
    """
    更新单条生成数据
    
    Args:
        data_id: 数据ID
        user_id: 用户ID（用于权限验证）
        new_content: 新的数据内容
        
    Returns:
        是否更新成功
    """
    db = SessionLocal()
    try:
        # 查找数据并验证权限
        data_item = db.query(GeneratedData).filter(
            GeneratedData.id == data_id,
            GeneratedData.user_id == user_id
        ).first()
        
        if not data_item:
            return False
        
        # 更新数据内容
        data_item.data_content = json.dumps(new_content, ensure_ascii=False)
        data_item.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_generated_data_count(
    task_id: str,
    user_id: Optional[int] = None
) -> int:
    """
    获取任务生成的数据条数
    
    Args:
        task_id: 任务ID
        user_id: 用户ID（可选，用于权限过滤）
        
    Returns:
        数据条数
    """
    db = SessionLocal()
    try:
        query = db.query(GeneratedData).filter(GeneratedData.task_id == task_id)
        
        if user_id is not None:
            query = query.filter(GeneratedData.user_id == user_id)
        
        return query.count()
    
    finally:
        db.close()


def confirm_generated_data(
    data_id: int,
    user_id: int,
    is_confirmed: bool = True
) -> bool:
    """
    确认或取消确认单条生成数据
    
    Args:
        data_id: 数据ID
        user_id: 用户ID（用于权限验证）
        is_confirmed: 是否确认
        
    Returns:
        是否操作成功
    """
    db = SessionLocal()
    try:
        # 查找数据并验证权限
        data_item = db.query(GeneratedData).filter(
            GeneratedData.id == data_id,
            GeneratedData.user_id == user_id
        ).first()
        
        if not data_item:
            return False
        
        # 更新确认状态
        data_item.is_confirmed = is_confirmed
        data_item.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def delete_generated_data_by_task(
    task_id: str,
    user_id: Optional[int] = None
) -> int:
    """
    删除任务的生成数据
    
    Args:
        task_id: 任务ID
        user_id: 用户ID（可选，用于权限过滤）
        
    Returns:
        删除的数据条数
    """
    db = SessionLocal()
    try:
        query = db.query(GeneratedData).filter(GeneratedData.task_id == task_id)
        
        if user_id is not None:
            query = query.filter(GeneratedData.user_id == user_id)
        
        count = query.count()
        query.delete()
        db.commit()
        
        return count
    
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def get_task_review_status(
    task_id: str,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    获取任务的审核状态
    
    Args:
        task_id: 任务ID
        user_id: 用户ID（可选，用于权限过滤）
        
    Returns:
        包含审核状态的字典:
        - total_count: 总数据条数
        - confirmed_count: 已确认条数
        - is_fully_reviewed: 是否全部审核完毕
    """
    db = SessionLocal()
    try:
        query = db.query(GeneratedData).filter(GeneratedData.task_id == task_id)
        
        if user_id is not None:
            query = query.filter(GeneratedData.user_id == user_id)
        
        total_count = query.count()
        confirmed_count = query.filter(GeneratedData.is_confirmed == True).count()
        
        return {
            'total_count': total_count,
            'confirmed_count': confirmed_count,
            'is_fully_reviewed': total_count > 0 and confirmed_count == total_count
        }
    
    finally:
        db.close()
