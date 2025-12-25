import time
import json
import openai
import requests
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from requests.exceptions import HTTPError, Timeout, ConnectTimeout


def get_backend_config() -> Dict:
    """读取后端配置"""
    # 尝试多个可能的配置文件位置
    possible_paths = [
        Path(__file__).parent.parent / "config" / "config.yaml",
        Path.cwd() / "config" / "config.yaml",
        # 兼容旧路径
        Path(__file__).parent.parent / "web-ui" / "config.yaml",
        Path.cwd() / "web-ui" / "config.yaml",
    ]
    
    for config_path in possible_paths:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            if config:  # 确保配置不为空
                return config
    
    # 默认配置
    return {
        'web_service': {
            'host': 'localhost',
            'port': 5000  # 默认后端服务端口
        },
        'redis_service': {
            'max_wait_time': 300
        }
    }


def call_model_via_proxy(
    api_url: str,
    api_key: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: int = 300,
    is_vllm: bool = False,
    top_p: float = 1.0,
) -> str:
    """
    通过后端代理调用模型API（带流量控制）
    """
    config = get_backend_config()
    web_config = config.get('web_service', {})
    backend_host = web_config.get('host', 'localhost')
    backend_port = web_config.get('port', 16385)
    
    # 如果host是0.0.0.0，使用localhost
    if backend_host == '0.0.0.0':
        backend_host = 'localhost'
    
    backend_url = f"http://{backend_host}:{backend_port}/api/model-call"
    
    payload = {
        "api_url": api_url,
        "api_key": api_key,
        "messages": messages,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "is_vllm": is_vllm,
        "top_p": top_p
    }
    
    # 计算请求超时时间：max_wait_time + 实际调用timeout + 缓冲
    redis_config = config.get('redis_service', {})
    max_wait_time = redis_config.get('max_wait_time', 300)
    request_timeout = max_wait_time + timeout + 60  # 添加60秒缓冲
    
    try:
        response = requests.post(
            backend_url,
            json=payload,
            timeout=request_timeout,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("success"):
            return result.get("content", "")
        else:
            return f"模型调用失败: {result.get('error', '未知错误')}"
    
    except requests.exceptions.ConnectionError as e:
        return f"后端代理不可用: {str(e)}"
    except Exception as e:
        return f"代理调用失败: {str(e)}"


def call_model_api(
    api_url: str,
    api_key: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    retry_times: int = 3,  # 保留参数以保持接口兼容性，但不使用
    timeout: int = 300,
    is_vllm: bool = False,
    top_p: float = 1.0,
    use_proxy: bool = True,  # 保留参数以保持接口兼容性，但强制使用代理
) -> str:
    """
    调用模型API的主入口（仅支持通过后端代理调用）
    
    注意：use_proxy 参数已废弃，始终使用后端代理（带Redis流量控制）
    """
    # 强制使用后端代理（带Redis流量控制）
    return call_model_via_proxy(
        api_url=api_url,
        api_key=api_key,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        is_vllm=is_vllm,
        top_p=top_p
    )

# 以下函数已删除，不再支持直接调用模式：
# - call_model_direct()
# - call_vllm_api() 
# - call_openai_api()
# 
# 所有模型调用必须通过后端代理（call_model_via_proxy）进行，
# 以确保统一的流量控制和并发管理。
