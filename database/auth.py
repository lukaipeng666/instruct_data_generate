"""
认证相关功能 - JWT token生成和验证
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .models import get_db
from .user_service import get_user_by_username

# 添加配置模块路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import get_jwt_config

# JWT配置 - 从 config.yaml 读取
_jwt_config = get_jwt_config()
SECRET_KEY = _jwt_config['secret_key']
ALGORITHM = _jwt_config['algorithm']
ACCESS_TOKEN_EXPIRE_MINUTES = _jwt_config['expire_minutes']

if _jwt_config['generated']:
    print("⚠️  警告: config.yaml 中未设置 jwt.secret_key，使用随机生成的密钥。生产环境请设置固定密钥！")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, credentials_exception):
    """验证token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    username = verify_token(token, credentials_exception)
    user = get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_admin(
    current_user = Depends(get_current_user)
):
    """获取当前管理员用户，非管理员拒绝访问"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问，需要管理员权限"
        )
    return current_user
