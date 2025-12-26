#!/usr/bin/env python3
"""
模型管理路由（普通用户）
普通用户可以查看已激活的模型列表
支持模型调用限流功能
"""

import os
import sys
import json
import time
import logging
from typing import List, Dict, Optional

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import get_db, ModelConfig
from database.auth import get_current_user

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api', tags=['模型'])


# ========== 数据模型定义 ==========

class ModelCallRequest(BaseModel):
    """模型调用请求"""
    api_url: str
    api_key: str = ""
    messages: List[Dict[str, str]]
    model: str
    temperature: float = 0.0
    max_tokens: int = 8192
    timeout: int = 300
    is_vllm: bool = False
    top_p: float = 1.0
    retry_times: int = 3


class ModelCallResponse(BaseModel):
    """模型调用响应"""
    success: bool
    content: str = ""
    error: Optional[str] = None


# 导入统一配置模块
from config import get_redis_config

# ========== Redis 配置 ==========

_redis_client = None

def get_redis_client():
    """获取 Redis 客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        redis_config = get_redis_config()
        
        _redis_client = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config['db'],
            password=redis_config['password'],
            decode_responses=True
        )
    return _redis_client


def get_model_max_concurrency(model_name: str) -> int:
    """
    获取模型的最大并发数
    首先从数据库查询，如果没有则使用默认值
    """
    from database import SessionLocal, ModelConfig
    
    db = SessionLocal()
    try:
        model = db.query(ModelConfig).filter(
            ModelConfig.name == model_name,
            ModelConfig.is_active == True
        ).first()
        
        if model and model.max_concurrent:
            return model.max_concurrent
        
        # 默认并发数
        redis_config = get_redis_config()
        return redis_config['default_max_concurrency']
    finally:
        db.close()


@router.get('/models')
async def get_active_models(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取所有激活的模型配置（普通用户可访问）"""
    try:
        # 只返回已激活的模型
        models = db.query(ModelConfig).filter(ModelConfig.is_active == True).all()
        return JSONResponse({
            'success': True,
            'models': [{
                'id': model.id,
                'name': model.name,
                'description': model.description,
                'created_at': model.created_at.isoformat() if model.created_at else None
            } for model in models]
        })
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)
    

def _model_call_sync(request: ModelCallRequest) -> ModelCallResponse:
    """
    同步执行模型调用（在线程池中运行）
    """
    # 从统一配置模块读取
    redis_config = get_redis_config()
    max_wait_time = redis_config['max_wait_time']
    
    model_name = request.model
    redis_key = f"model_concurrency:{model_name}"
    
    # 获取模型的最大并发数
    max_concurrency = get_model_max_concurrency(model_name)
    
    # Lua 脚本：原子性地检查并增加计数器
    # 返回值：1 表示成功获取槽位，0 表示并发已满
    acquire_slot_script = """
    local current = tonumber(redis.call('GET', KEYS[1]) or '0')
    local max_concurrency = tonumber(ARGV[1])
    if current < max_concurrency then
        redis.call('INCR', KEYS[1])
        redis.call('EXPIRE', KEYS[1], 3600)
        return 1
    else
        return 0
    end
    """
    
    try:
        redis_client = get_redis_client()
        
        # 注册 Lua 脚本
        try_acquire = redis_client.register_script(acquire_slot_script)
        
        # 尝试获取锁（等待直到获取到或超时）
        start_time = time.time()
        acquired = False
        wait_iterations = 0
        
        while time.time() - start_time < max_wait_time:
            # 使用 Lua 脚本原子性地尝试获取槽位
            result = try_acquire(keys=[redis_key], args=[max_concurrency])
            
            if result == 1:
                acquired = True
                current_count = redis_client.get(redis_key)
                current_count = int(current_count) if current_count else 1
                elapsed_time = time.time() - start_time
                if wait_iterations > 0:
                    logger.info(f"[Redis] 获取并发槽位成功: {model_name} (等待: {elapsed_time:.2f}秒, 当前并发: {current_count}/{max_concurrency})")
                else:
                    logger.info(f"[Redis] 获取并发槽位成功: {model_name} (当前并发: {current_count}/{max_concurrency})")
                break
            
            # 等待一段时间后重试
            wait_iterations += 1
            if wait_iterations % 2 == 0:  # 每5秒记录一次等待状态
                current_count = redis_client.get(redis_key)
                current_count = int(current_count) if current_count else 0
                elapsed_time = time.time() - start_time
                logger.info(f"[Redis] 等待并发槽位: {model_name} (已等待: {elapsed_time:.1f}秒, 当前并发: {current_count}/{max_concurrency})")
            time.sleep(2.5)
        
        if not acquired:
            elapsed_time = time.time() - start_time
            error_msg = f"等待超时（{elapsed_time:.1f}秒），模型 {model_name} 并发数已达上限 {max_concurrency}"
            logger.error(f"[Redis] {error_msg}")
            return ModelCallResponse(
                success=False,
                error=error_msg,
                content="服务繁忙，请稍后再试"
            )
        
        # 执行模型调用
        try:
            if request.is_vllm:
                result = call_vllm_api_sync(
                    api_url=request.api_url,
                    messages=request.messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout,
                    top_p=request.top_p,
                    retry_times=request.retry_times
                )
            else:
                result = call_openai_api_sync(
                    api_url=request.api_url,
                    api_key=request.api_key,
                    messages=request.messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout,
                    top_p=request.top_p,
                    retry_times=request.retry_times
                )
            
            return ModelCallResponse(success=True, content=result)
        
        finally:
            # 释放并发计数
            new_count = redis_client.decr(redis_key)
            # 如果计数变为0或负数，删除key
            if new_count <= 0:
                redis_client.delete(redis_key)
                logger.info(f"[Redis] 释放并发槽位并删除key: {model_name} (剩余并发: 0)")
            else:
                logger.info(f"[Redis] 释放并发槽位: {model_name} (剩余并发: {new_count}/{max_concurrency})")
    
    except redis.ConnectionError as e:
        logger.error(f"[Redis] Redis连接错误: {e}")
        logger.warning(f"[Redis] Redis不可用，回退到直接调用模式 (模型: {model_name})")
        # Redis 不可用时，直接调用（不限流）
        try:
            if request.is_vllm:
                result = call_vllm_api_sync(
                    api_url=request.api_url,
                    messages=request.messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout,
                    top_p=request.top_p,
                    retry_times=request.retry_times
                )
            else:
                result = call_openai_api_sync(
                    api_url=request.api_url,
                    api_key=request.api_key,
                    messages=request.messages,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout,
                    top_p=request.top_p,
                    retry_times=request.retry_times
                )
            return ModelCallResponse(success=True, content=result)
        except Exception as call_error:
            logger.error(f"[Redis] 直接调用失败: {call_error}")
            return ModelCallResponse(success=False, error=str(call_error))
    
    except Exception as e:
        logger.error(f"[Redis] 模型调用异常: {model_name}, 错误: {e}")
        return ModelCallResponse(success=False, error=str(e))


@router.post("/model-call", response_model=ModelCallResponse)
async def model_call_with_rate_limit(request: ModelCallRequest):
    """
    带流量控制的模型调用代理接口
    使用 Redis 进行并发计数和限流
    当并发超过限制时，最多等待 max_wait_time 秒
    
    注意：使用 asyncio.to_thread 在线程池中执行同步阻塞操作，
    避免阻塞 FastAPI 事件循环，确保多个请求可以真正并发执行
    """
    import asyncio
    # 在线程池中执行同步操作，不阻塞事件循环
    return await asyncio.to_thread(_model_call_sync, request)


def call_vllm_api_sync(
    api_url: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 600,
    top_p: float = 1.0,
    retry_times: int = 3,
) -> str:
    """同步调用vllm API（带重试）"""
    import requests
    
    do_sample = temperature > 0.0
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": True,
        "do_sample": do_sample,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    
    base_url = api_url.rstrip('/')
    endpoint = "/chat/completions"
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    full_url = f"{base_url}{endpoint}"
    
    # 重试逻辑
    for attempt in range(retry_times):
        try:
            full_response = ""
            
            with requests.post(
                full_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=timeout
            ) as response:
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            return full_response.strip()
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                full_response += delta
                        except (KeyError, json.JSONDecodeError):
                            continue
                
                return full_response.strip()
        
        except requests.exceptions.Timeout as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2  # 指数退避：2, 4, 6 秒
                logger.warning(f"[vLLM API] 调用超时，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[vLLM API] 重试{retry_times}次后仍然超时: {str(e)}")
                raise
        
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[vLLM API] 连接错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[vLLM API] 重试{retry_times}次后仍然连接失败: {str(e)}")
                raise
        
        except requests.exceptions.HTTPError as e:
            # 4xx 错误不重试（客户端错误）
            if 400 <= e.response.status_code < 500:
                logger.error(f"[vLLM API] 客户端错误，不重试: {str(e)}")
                raise
            # 5xx 错误重试（服务器错误）
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[vLLM API] 服务器错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[vLLM API] 重试{retry_times}次后仍然失败: {str(e)}")
                raise
        
        except Exception as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[vLLM API] 未知错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {type(e).__name__}: {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[vLLM API] 重试{retry_times}次后仍然失败: {type(e).__name__}: {str(e)}")
                raise
    
    # 理论上不会到这里
    raise Exception("API调用失败")


def call_openai_api_sync(
    api_url: str,
    api_key: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 16384,
    timeout: int = 300,
    top_p: float = 1.0,
    retry_times: int = 3,
) -> str:
    """同步调用OpenAI兼容API（带重试）"""
    import openai
    
    # 重试逻辑
    for attempt in range(retry_times):
        try:
            client = openai.OpenAI(
                api_key=api_key,
                base_url=api_url,
                timeout=timeout,
                max_retries=0  # 我们自己实现重试逻辑
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
        
        except openai.APITimeoutError as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[OpenAI API] 调用超时，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[OpenAI API] 重试{retry_times}次后仍然超时: {str(e)}")
                raise
        
        except openai.APIConnectionError as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[OpenAI API] 连接错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[OpenAI API] 重试{retry_times}次后仍然连接失败: {str(e)}")
                raise
        
        except openai.APIStatusError as e:
            # 4xx 错误不重试（客户端错误）
            if 400 <= e.status_code < 500:
                logger.error(f"[OpenAI API] 客户端错误，不重试: {str(e)}")
                raise
            # 5xx 错误重试（服务器错误）
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[OpenAI API] 服务器错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[OpenAI API] 重试{retry_times}次后仍然失败: {str(e)}")
                raise
        
        except Exception as e:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                logger.warning(f"[OpenAI API] 未知错误，{wait_time}秒后重试 (尝试 {attempt + 1}/{retry_times}): {type(e).__name__}: {str(e)}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"[OpenAI API] 重试{retry_times}次后仍然失败: {type(e).__name__}: {str(e)}")
                raise
    
    # 理论上不会到这里
    raise Exception("API调用失败")
