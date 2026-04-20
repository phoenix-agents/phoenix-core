#!/usr/bin/env python3
"""
Phoenix Core 多 Bot 协作协议端到端测试

使用方法:
    1. 确保 Gateway (小小谦) 和 Worker Bot (场控) 都在 Discord 频道中在线
    2. 设置环境变量:
       - DISCORD_BOT_TOKEN: 一个用于测试的 Discord Bot Token (不能是 Gateway 或 Worker 自己)
       - TEST_CHANNEL_ID: 测试频道 ID
    3. 运行：python tests/e2e_protocol_test.py
"""

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, List

import discord


# ========== 配置 ==========
GATEWAY_ID = "1483335704590155786"      # 小小谦的 Discord ID
WORKER_ID = "1479053473038467212"       # 场控的 Discord ID
TESTER_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("TEST_CHANNEL_ID", "0"))

# ========== 测试结果记录 ==========
@dataclass
class ProtocolMessage:
    """协议消息结构"""
    msg_type: str          # ASK / RESPONSE / CONFIRM 等
    request_id: str
    sender: str
    target: str
    content: str
    timestamp: float

class TestResults:
    def __init__(self):
        self.gateway_ask: Optional[ProtocolMessage] = None
        self.worker_response: Optional[ProtocolMessage] = None
        self.gateway_reply_to_user: Optional[str] = None
        self.errors: List[str] = []
        self.duplicate_responses: int = 0
        self.timeout_occurred: bool = False

results = TestResults()

# ========== Discord 客户端 ==========
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ 测试 Bot 已登录：{client.user} (ID: {client.user.id})")
    
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ 找不到测试频道 ID: {CHANNEL_ID}")
        await client.close()
        return
    
    print(f"\n📡 开始监听频道：{channel.name}")
    print(f"⏳ 请在 5 秒后发送测试消息：@小小谦 问问场控在不在")
    print("=" * 60)

@client.event
async def on_message(message: discord.Message):
    # 忽略自己发送的消息
    if message.author == client.user:
        return
    
    content = message.content.strip()
    author_id = str(message.author.id)
    timestamp = time.time()
    
    # 1. 检测 Gateway 发出的 ASK 协议消息
    if author_id == GATEWAY_ID:
        match = re.match(r"<@(\d+)> \[(ASK|REQUEST)\|([^\|]+)\|([^\|]+)\] (.*)", content)
        if match:
            target_id, msg_type, request_id, sender, body = match.groups()
            results.gateway_ask = ProtocolMessage(
                msg_type=msg_type,
                request_id=request_id,
                sender=sender,
                target=target_id,
                content=body,
                timestamp=timestamp
            )
            print(f"✅ [Gateway] 发送 ASK: request_id={request_id}, target=<@{target_id}>")
            return
        
        # 检测 Gateway 回复用户的最终消息（纯文本，无协议头）
        if not re.search(r"\[(ASK|REQUEST|RESPONSE|CONFIRM)", content):
            # 可能是最终回复
            if "在的" in content or "电流满格" in content or "场控" in content:
                results.gateway_reply_to_user = content
                print(f"✅ [Gateway] 最终回复用户：{content[:50]}...")
    
    # 2. 检测 Worker 发出的 RESPONSE 协议消息
    elif author_id == WORKER_ID:
        match = re.match(r"<@(\d+)> \[(RESPONSE)\|([^\|]+)\|([^\|]+)\] (.*)", content)
        if match:
            target_id, msg_type, request_id, sender, body = match.groups()
            
            # 检查是否是重复响应（同一个 request_id 之前已经收到过）
            if results.worker_response and results.worker_response.request_id == request_id:
                results.duplicate_responses += 1
                print(f"⚠️  [Worker] 重复 RESPONSE: request_id={request_id} (第 {results.duplicate_responses} 次)")
            else:
                results.worker_response = ProtocolMessage(
                    msg_type=msg_type,
                    request_id=request_id,
                    sender=sender,
                    target=target_id,
                    content=body,
                    timestamp=timestamp
                )
                print(f"✅ [Worker] 发送 RESPONSE: request_id={request_id}, target=<@{target_id}>, content={body[:30]}...")
            return
        
        # 检测 Worker 是否错误地回复了非协议消息（例如纯文本或错误提示）
        if "错误格式" in content or "无效输入" in content:
            results.errors.append(f"Worker 返回错误提示：{content[:80]}")
            print(f"❌ [Worker] 错误响应：{content[:80]}")
    
    # 3. 检测是否有超时提示（来自 Gateway）
    if author_id == GATEWAY_ID and "响应超时" in content:
        results.timeout_occurred = True
        results.errors.append("Gateway 报告响应超时")
        print(f"❌ [Gateway] 超时提示：{content}")

# ========== 主测试逻辑 ==========
async def run_test():
    await client.start(TESTER_TOKEN)
    
    # 等待用户操作（这里给 60 秒时间，期间监听消息）
    print("\n⏳ 等待测试消息... (60 秒超时)")
    await asyncio.sleep(60)
    
    # 分析结果
    print("\n" + "=" * 60)
    print("📊 测试结果分析")
    print("=" * 60)
    
    # 检查 Gateway ASK
    if results.gateway_ask:
        print(f"✅ Gateway ASK 已发送：request_id={results.gateway_ask.request_id}")
    else:
        print("❌ 未检测到 Gateway ASK 消息")
        results.errors.append("Gateway 未发送 ASK 协议消息")
    
    # 检查 Worker RESPONSE
    if results.worker_response:
        print(f"✅ Worker RESPONSE 已发送：request_id={results.worker_response.request_id}")
        # 检查 request_id 是否匹配
        if results.gateway_ask and results.worker_response.request_id == results.gateway_ask.request_id:
            print(f"✅ request_id 匹配：{results.gateway_ask.request_id}")
        else:
            print(f"❌ request_id 不匹配！Gateway: {results.gateway_ask.request_id if results.gateway_ask else 'N/A'}, Worker: {results.worker_response.request_id}")
            results.errors.append("request_id 不匹配")
    else:
        print("❌ 未检测到 Worker RESPONSE 消息")
        results.errors.append("Worker 未发送 RESPONSE 协议消息")
    
    # 检查重复响应
    if results.duplicate_responses > 0:
        print(f"❌ 检测到 {results.duplicate_responses} 次重复 RESPONSE")
        results.errors.append(f"Worker 重复响应 {results.duplicate_responses} 次")
    else:
        print("✅ 无重复响应")
    
    # 检查超时
    if results.timeout_occurred:
        print("❌ Gateway 报告超时")
        results.errors.append("Gateway 超时")
    else:
        print("✅ 无超时错误")
    
    # 检查最终回复
    if results.gateway_reply_to_user:
        print(f"✅ Gateway 最终回复用户：{results.gateway_reply_to_user[:50]}...")
    else:
        print("⚠️  未检测到 Gateway 最终回复用户（可能被协议头覆盖或未发送）")
    
    # 总结
    print("\n" + "=" * 60)
    if results.errors:
        print(f"❌ 测试失败，发现 {len(results.errors)} 个错误:")
        for err in results.errors:
            print(f"   - {err}")
    else:
        print("🎉 所有测试通过！协议链路完整，无超时、无重复。")
    
    await client.close()

if __name__ == "__main__":
    if not TESTER_TOKEN or not CHANNEL_ID:
        print("❌ 请设置环境变量 DISCORD_BOT_TOKEN 和 TEST_CHANNEL_ID")
        exit(1)
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n⏹️ 测试手动终止")
