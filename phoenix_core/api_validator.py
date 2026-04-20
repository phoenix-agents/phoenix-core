#!/usr/bin/env python3
"""
Phoenix Core API Validator - Flask 路由 Pydantic 校验装饰器

在 API 入口处拦截参数错误，防止进程因 KeyError/TypeError 崩溃

Usage:
    from flask import Flask, request, jsonify
    from phoenix_core.api_validator import validate_request
    from pydantic import BaseModel

    class StopBotRequest(BaseModel):
        bot_id: str

    @app.route('/api/bot/stop', methods=['POST'])
    @validate_request(StopBotRequest)
    def stop_bot(validated: StopBotRequest):
        # 安全使用 validated.bot_id
        return jsonify({"success": True})
"""

from functools import wraps
from pydantic import BaseModel, ValidationError
from typing import Type, Optional, Callable
import logging

# Flask 是可选依赖，仅在使用时导入
try:
    from flask import request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    request = None
    jsonify = None

logger = logging.getLogger(__name__)


def validate_request(model_cls: Type[BaseModel], source: str = 'json'):
    """
    装饰器：自动校验请求数据并注入到 kwargs['validated']

    Args:
        model_cls: Pydantic 模型类
        source: 数据来源 'json' | 'args' | 'form'

    Returns:
        装饰后的函数，接收 validated 参数

    错误处理:
        - 校验失败返回 400 + 详细错误信息
        - 进程不崩溃，继续运行
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not FLASK_AVAILABLE:
                logger.error("Flask 不可用，api_validator 需要安装 Flask")
                return jsonify({"error": "Server配置错误：Flask 未安装"}), 500

            # 1. 提取请求数据
            if source == 'json':
                data = request.get_json(silent=True) or {}
            elif source == 'args':
                data = request.args.to_dict()
            elif source == 'form':
                data = request.form.to_dict()
            else:
                data = {}

            # 2. Pydantic 校验
            try:
                validated_data = model_cls(**data)
            except ValidationError as e:
                logger.warning(f"API 参数校验失败：{e.errors()}")
                return jsonify({
                    "error": "参数校验失败",
                    "details": [
                        {
                            "loc": err['loc'],
                            "msg": err['msg'],
                            "type": err['type']
                        }
                        for err in e.errors()
                    ]
                }), 400
            except Exception as e:
                logger.error(f"API 校验异常：{e}")
                return jsonify({
                    "error": "Server内部错误",
                    "details": str(e)
                }), 500

            # 3. 注入校验后的数据
            kwargs['validated'] = validated_data

            # 4. 执行原函数
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"API 处理异常：{e}")
                return jsonify({
                    "error": "处理失败",
                    "details": str(e)
                }), 500

        return wrapper
    return decorator


def validate_request_async(model_cls: Type[BaseModel], source: str = 'json'):
    """
    异步版本装饰器 (用于 async def 路由)

    Usage:
        @app.route('/api/bot/status', methods=['GET'])
        @validate_request_async(StatusRequest)
        async def get_bot_status(validated: StatusRequest):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not FLASK_AVAILABLE:
                logger.error("Flask 不可用，api_validator 需要安装 Flask")
                return jsonify({"error": "Server配置错误：Flask 未安装"}), 500

            # 1. 提取请求数据
            if source == 'json':
                data = request.get_json(silent=True) or {}
            elif source == 'args':
                data = request.args.to_dict()
            elif source == 'form':
                data = request.form.to_dict()
            else:
                data = {}

            # 2. Pydantic 校验
            try:
                validated_data = model_cls(**data)
            except ValidationError as e:
                logger.warning(f"API 参数校验失败：{e.errors()}")
                return jsonify({
                    "error": "参数校验失败",
                    "details": [
                        {
                            "loc": err['loc'],
                            "msg": err['msg'],
                            "type": err['type']
                        }
                        for err in e.errors()
                    ]
                }), 400

            # 3. 注入校验后的数据
            kwargs['validated'] = validated_data

            # 4. 执行原异步函数
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# ========== 便捷模型定义 ===========

class BotIdRequest(BaseModel):
    """通用 Bot ID 请求"""
    bot_id: str


class BotActionRequest(BaseModel):
    """Bot 动作请求"""
    bot_id: str
    action: str  # start, stop, restart


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    bot_id: str
    channel_id: str
    message: str
