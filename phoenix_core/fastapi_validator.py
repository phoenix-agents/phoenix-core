#!/usr/bin/env python3
"""
Phoenix Core FastAPI Validator - FastAPI 路由 Pydantic 校验装饰器

在 API 入口处拦截参数错误，防止进程因 KeyError/TypeError 崩溃

Usage:
    from fastapi import FastAPI
    from phoenix_core import validate_request
    from pydantic import BaseModel

    class BotActionRequest(BaseModel):
        action: str
        bot_name: str

    @app.post("/api/bots/action")
    @validate_request(BotActionRequest)
    async def bot_action(validated: BotActionRequest):
        # 安全使用 validated.action 和 validated.bot_name
        return {"success": True}
"""

from functools import wraps
from pydantic import BaseModel, ValidationError
from typing import Type, Optional, Callable
import logging

logger = logging.getLogger(__name__)


def validate_request(model_cls: Type[BaseModel], source: str = 'json'):
    """
    装饰器：自动校验 FastAPI 请求数据并注入到 kwargs['validated']

    Args:
        model_cls: Pydantic 模型类
        source: 数据来源 'json' | 'query' | 'body'

    Returns:
        装饰后的函数，接收 validated 参数

    错误处理:
        - 校验失败返回 400 + 详细错误信息
        - 进程不崩溃，继续运行
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 1. 提取请求数据
            request = kwargs.get('request')
            data = {}

            if request:
                if source == 'json':
                    try:
                        data = await request.json() or {}
                    except Exception:
                        data = {}
                elif source == 'query':
                    data = dict(request.query_params)
                elif source == 'form':
                    try:
                        data = await request.form()
                        data = dict(data)
                    except Exception:
                        data = {}

            # 2. Pydantic 校验
            try:
                validated_data = model_cls(**data)
            except ValidationError as e:
                logger.warning(f"API 参数校验失败：{e.errors()}")
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "参数校验失败",
                        "details": [
                            {
                                "loc": err['loc'],
                                "msg": err['msg'],
                                "type": err['type']
                            }
                            for err in e.errors()
                        ]
                    }
                )
            except Exception as e:
                logger.error(f"API 校验异常：{e}")
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Server内部错误",
                        "details": str(e)
                    }
                )

            # 3. 注入校验后的数据
            kwargs['validated'] = validated_data

            # 4. 执行原函数
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"API 处理异常：{e}")
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "处理失败",
                        "details": str(e)
                    }
                )

        return wrapper
    return decorator
