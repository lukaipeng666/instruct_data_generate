"""
用户服务 - 处理用户相关的数据库操作
"""
from sqlalchemy.orm import Session
import bcrypt
import os
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


def is_bcrypt_hash(password: str) -> bool:
    """判断字符串是否是 bcrypt 哈希值"""
    # bcrypt 哈希值通常以 $2a$, $2b$, $2y$ 开头，长度为 60
    return (password.startswith('$2a$') or 
            password.startswith('$2b$') or 
            password.startswith('$2y$')) and len(password) == 60


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


def create_user_with_hash(db: Session, username: str, password_hash: str, is_admin: bool = False) -> User:
    """使用已有的密码哈希值创建新用户"""
    user = User(
        username=username,
        password_hash=password_hash,
        is_active=True,
        is_admin=is_admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def init_default_admin():
    """初始化默认管理员账号"""
    import sys
    import os
    
    # 添加配置模块路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import get_admin_config
    
    # 从 config.yaml 读取管理员配置
    admin_config = get_admin_config()
    admin_username = admin_config['username']
    admin_password = admin_config['password']
    
    db = SessionLocal()
    try:
        # 检查是否已存在管理员用户
        admin_user = get_user_by_username(db, admin_username)
        if not admin_user:
            # 判断配置中的密码是哈希值还是明文
            is_password_hash = is_bcrypt_hash(admin_password)
            
            if admin_config['generated']:
                print(f"⚠️  警告: config.yaml 中未设置 admin.password")
                if not is_password_hash:
                    print(f"📝 生成的随机管理员密码: {admin_password}")
                print(f"🔐 请立即记录此密码，或在 config.yaml 中设置 admin.password")
            
            # 如果配置中的是哈希值，直接使用；如果是明文，则先哈希
            if is_password_hash:
                # 配置中已经是哈希值，直接使用
                create_user_with_hash(db, admin_username, admin_password, is_admin=True)
                print(f"✅ 默认管理员账号已创建: {admin_username} (使用配置中的密码哈希值)")
            else:
                # 配置中是明文，需要先哈希
                create_user(db, admin_username, admin_password, is_admin=True)
                print(f"✅ 默认管理员账号已创建: {admin_username}")
        else:
            # 确保admin用户是管理员
            if not admin_user.is_admin:
                admin_user.is_admin = True
                db.commit()
                print(f"已将 {admin_username} 用户更新为管理员")
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
    
    # 检查数据库文件状态
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'app.db')
    print(f"📂 数据库路径: {db_path}")
    print(f"📂 数据库文件存在: {os.path.exists(db_path)}")
    
    # 1. 创建所有表
    print("\n1. 创建数据库表...")
    init_db()
    print("✅ 表结构创建完成")
    
    # 检查创建后的状态
    print(f"📂 创建表后数据库文件存在: {os.path.exists(db_path)}")
    if os.path.exists(db_path):
        print(f"📊 数据库文件大小: {os.path.getsize(db_path)} 字节")
    
    # 2. 核查和创建缺失的字段
    print("\n2. 核查数据库字段...")
    verify_and_create_columns()
    
    # 3. 初始化默认管理员
    print("\n3. 初始化默认管理员账号...")
    init_default_admin()
    
    print("\n=== 数据库初始化完成 ===\n")

