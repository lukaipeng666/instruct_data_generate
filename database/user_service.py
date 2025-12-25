"""
用户服务 - 处理用户相关的数据库操作
"""
from sqlalchemy.orm import Session
import bcrypt
from .models import User, SessionLocal, init_db, verify_and_create_columns
from datetime import datetime


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    # 将密码转换为字节
    password_bytes = plain_password.encode('utf-8')
    hash_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    # 将密码转换为字节
    password_bytes = password.encode('utf-8')
    # 生成salt并加密
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # 返回字符串格式
    return hashed.decode('utf-8')


def get_user_by_username(db: Session, username: str) -> User:
    """根据用户名获取用户"""
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> User:
    """验证用户登录"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def create_user(db: Session, username: str, password: str, is_admin: bool = False) -> User:
    """创建新用户"""
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        password_hash=hashed_password,
        is_active=True,
        is_admin=is_admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def init_default_admin():
    """初始化默认管理员账号"""
    db = SessionLocal()
    try:
        # 检查是否已存在admin用户
        admin_user = get_user_by_username(db, "admin")
        if not admin_user:
            # 创建默认管理员
            create_user(db, "admin", "suanfazu2025", is_admin=True)
            print("默认管理员账号已创建: admin / suanfazu2025")
        else:
            # 确保admin用户是管理员
            if not admin_user.is_admin:
                admin_user.is_admin = True
                db.commit()
                print("已将admin用户更新为管理员")
            else:
                print("管理员账号已存在")
    except Exception as e:
        print(f"初始化管理员账号时出错: {e}")
        db.rollback()
    finally:
        db.close()


def init_database():
    """
    初始化数据库
    1. 创建所有表结构
    2. 核查并创建缺失的字段
    3. 初始化默认管理员账号
    """
    print("\n=== 开始初始化数据库 ===")
    
    # 1. 创建所有表
    print("\n1. 创建数据库表...")
    init_db()
    print("✅ 表结构创建完成")
    
    # 2. 核查和创建缺失的字段
    print("\n2. 核查数据库字段...")
    verify_and_create_columns()
    
    # 3. 初始化默认管理员
    print("\n3. 初始化默认管理员账号...")
    init_default_admin()
    
    print("\n=== 数据库初始化完成 ===\n")

