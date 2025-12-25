#!/usr/bin/env python3
"""
认证相关路由
包括登录、注册、登出、获取用户信息等
"""

from datetime import timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import authenticate_user, get_db
from database.auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from database.user_service import get_user_by_username, create_user

router = APIRouter(prefix='/api', tags=['认证'])


@router.post('/login')
async def login(request: Request, db: Session = Depends(get_db)):
    """用户登录"""
    try:
        data = await request.json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名和密码不能为空"
            )
        
        user = authenticate_user(db, username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "is_admin": user.is_admin
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.post('/register')
async def register(request: Request, db: Session = Depends(get_db)):
    """用户注册（只能注册普通用户）"""
    try:
        data = await request.json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名和密码不能为空"
            )
        
        # 验证用户名长度
        if len(username) < 3 or len(username) > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名长度必须在3-20个字符之间"
            )
        
        # 验证用户名格式（只允许字母、数字、下划线）
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名只能包含字母、数字和下划线"
            )
        
        # 验证密码长度
        if len(password) < 6 or len(password) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度必须在6-128个字符之间"
            )
        
        # 检查用户名是否已存在
        existing_user = get_user_by_username(db, username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在，请选择其他用户名"
            )
        
        # 创建普通用户（is_admin=False）
        user = create_user(db, username, password, is_admin=False)
        
        # 自动登录，返回token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "is_admin": user.is_admin,
            "message": "注册成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.get('/me')
async def get_current_user_info(current_user=Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin
    }


@router.post('/logout')
async def logout():
    """登出（客户端删除token即可）"""
    return {"message": "登出成功"}
