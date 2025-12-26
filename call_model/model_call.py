import sys
import os
import requests
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import get_web_config, get_redis_config


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
    retry_times: int = 3,
) -> str:
    """
    通过后端代理调用模型API（带流量控制）
    """
    # 从统一配置模块读取后端配置
    web_config = get_web_config()
    redis_config = get_redis_config()
    
    backend_host = web_config['host']
    backend_port = web_config['port']
    
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
        "top_p": top_p,
        "retry_times": retry_times
    }
    
    # 计算请求超时时间：max_wait_time + 实际调用timeout + 缓冲
    max_wait_time = redis_config['max_wait_time']
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
    retry_times: int = 3,
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
        top_p=top_p,
        retry_times=retry_times
    )

# 以下函数已删除，不再支持直接调用模式：
# - call_model_direct()
# - call_vllm_api() 
# - call_openai_api()
# 
# 所有模型调用必须通过后端代理（call_model_via_proxy）进行，
# 以确保统一的流量控制和并发管理。
