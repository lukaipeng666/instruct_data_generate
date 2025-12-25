"""
配置模块 - 统一读取 config.yaml 配置文件
"""
import os
import yaml
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

# 配置文件路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"

# 缓存配置
_config_cache: Optional[Dict[str, Any]] = None


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    加载配置文件（带缓存）
    
    Args:
        force_reload: 是否强制重新加载
        
    Returns:
        配置字典
    """
    global _config_cache
    
    if _config_cache is not None and not force_reload:
        return _config_cache
    
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f) or {}
    else:
        _config_cache = {}
    
    return _config_cache


def get_config(key_path: str, default: Any = None) -> Any:
    """
    获取配置值，支持点号分隔的路径
    
    Args:
        key_path: 配置键路径，如 "web_service.port"
        default: 默认值
        
    Returns:
        配置值
        
    Example:
        get_config("web_service.port", 5000)
        get_config("jwt.secret_key", "")
    """
    config = load_config()
    keys = key_path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value if value is not None else default


# ==================== 便捷配置访问函数 ====================

def get_web_config() -> Dict[str, Any]:
    """获取 Web 服务配置"""
    return {
        'host': get_config('web_service.host', '0.0.0.0'),
        'port': get_config('web_service.port', 5000),
    }


def get_frontend_url() -> str:
    """获取前端 URL"""
    return get_config('frontend.url', 'http://localhost:3000')


def get_cors_config() -> Dict[str, Any]:
    """获取 CORS 配置"""
    return {
        'origins': get_config('cors.origins', ['http://localhost:3000']),
        'allow_credentials': get_config('cors.allow_credentials', True),
        'allow_methods': get_config('cors.allow_methods', ['*']),
        'allow_headers': get_config('cors.allow_headers', ['*']),
    }


def get_jwt_config() -> Dict[str, Any]:
    """
    获取 JWT 配置
    如果 secret_key 为空，则生成随机密钥并警告
    """
    secret_key = get_config('jwt.secret_key', '')
    generated = False
    
    if not secret_key:
        secret_key = secrets.token_urlsafe(32)
        generated = True
    
    return {
        'secret_key': secret_key,
        'algorithm': get_config('jwt.algorithm', 'HS256'),
        'expire_minutes': get_config('jwt.expire_minutes', 43200),
        'generated': generated,  # 标记是否自动生成
    }


def get_admin_config() -> Dict[str, Any]:
    """
    获取管理员配置
    如果密码为空，则生成随机密码
    """
    password = get_config('admin.password', '')
    generated = False
    
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True
    
    return {
        'username': get_config('admin.username', 'admin'),
        'password': password,
        'generated': generated,  # 标记是否自动生成
    }


def get_redis_config() -> Dict[str, Any]:
    """获取 Redis 配置"""
    return {
        'host': get_config('redis_service.host', 'localhost'),
        'port': get_config('redis_service.port', 6379),
        'db': get_config('redis_service.db', 0),
        'password': get_config('redis_service.password', None),
        'max_wait_time': get_config('redis_service.max_wait_time', 300),
        'default_max_concurrency': get_config('redis_service.default_max_concurrency', 16),
    }


def get_model_services_config() -> Dict[str, Any]:
    """获取默认模型服务配置"""
    return {
        'default_services': get_config('model_services.default_services', ['http://localhost:6466/v1']),
        'default_model': get_config('model_services.default_model', '/data/models/Qwen3-32B'),
        'default_api_key': get_config('model_services.default_api_key', ''),
    }


def get_default_services() -> List[str]:
    """获取默认服务地址列表"""
    return get_config('model_services.default_services', ['http://localhost:6466/v1'])


def get_default_model() -> str:
    """获取默认模型路径"""
    return get_config('model_services.default_model', '/data/models/Qwen3-32B')

