#!/usr/bin/env python3
"""
Phoenix Core - 审计日志 Web API (FastAPI)

功能:
1. 审计日志查询 API
2. 按用户/时间/类型筛选
3. 导出 JSON/CSV
4. 简单统计面板

Usage:
    uvicorn phoenix_core.audit_api:app --reload --port 8000
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from phoenix_core.audit_logger import AuditLogger, AuditEntry, get_audit_logger
from phoenix_core.core_brain import CoreBrain, get_brain

logger = logging.getLogger(__name__)

# 初始化 FastAPI 应用
app = FastAPI(
    title="Phoenix Core Audit API",
    description="审计日志查询和导出 API",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
_audit_logger: Optional[AuditLogger] = None
_brain: Optional[CoreBrain] = None


def get_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = get_audit_logger()
    return _audit_logger


def get_brain_instance() -> CoreBrain:
    global _brain
    if _brain is None:
        _brain = get_brain()
    return _brain


# ============ 主页面 ============

@app.get("/", response_class=HTMLResponse, tags=["Web"])
async def root():
    """Dashboard - 审计日志面板"""
    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Phoenix Core - 审计日志面板</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 {
                color: #333;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #007bff;
            }
            .header-actions {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                align-items: center;
            }
            .btn-nav {
                padding: 10px 20px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-size: 14px;
                border: none;
                cursor: pointer;
            }
            .btn-nav:hover { background: #0056b3; }
            .filters {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .filters h3 { margin-bottom: 15px; color: #555; }
            .filter-row {
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                align-items: flex-end;
            }
            .filter-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            .filter-group label {
                font-size: 12px;
                color: #666;
                font-weight: 500;
            }
            .filter-group input, .filter-group select {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            .filter-group input:focus, .filter-group select:focus {
                outline: none;
                border-color: #007bff;
            }
            .btn {
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: background 0.2s;
            }
            .btn-primary { background: #007bff; color: white; }
            .btn-primary:hover { background: #0056b3; }
            .btn-secondary { background: #6c757d; color: white; }
            .btn-secondary:hover { background: #545b62; }
            .btn-success { background: #28a745; color: white; }
            .btn-success:hover { background: #1e7e34; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .stat-card h4 { color: #666; font-size: 13px; margin-bottom: 10px; }
            .stat-card .value { font-size: 28px; font-weight: bold; color: #333; }
            .stat-card.type-message .value { color: #007bff; }
            .stat-card.type-operation .value { color: #28a745; }
            .stat-card.type-error .value { color: #dc3545; }
            .stat-card.type-alert .value { color: #ffc107; }
            .logs-table {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .logs-table table { width: 100%; border-collapse: collapse; }
            .logs-table th {
                background: #f8f9fa;
                padding: 12px 15px;
                text-align: left;
                font-weight: 600;
                color: #555;
                border-bottom: 2px solid #dee2e6;
            }
            .logs-table td {
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
                font-size: 14px;
            }
            .logs-table tr:hover { background: #f8f9fa; }
            .entry-type {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            .entry-type.message { background: #e7f3ff; color: #007bff; }
            .entry-type.operation { background: #e8f5e9; color: #28a745; }
            .entry-type.error { background: #ffebee; color: #dc3545; }
            .entry-type.alert { background: #fff3e0; color: #ff9800; }
            .content {
                max-width: 400px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .timestamp {
                font-family: "Monaco", "Consolas", monospace;
                font-size: 13px;
                color: #666;
            }
            .pagination {
                display: flex;
                justify-content: center;
                gap: 10px;
                padding: 20px;
                align-items: center;
            }
            .pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
            .loading { text-align: center; padding: 40px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-actions">
                <h1>🔍 Phoenix Core - 审计日志面板</h1>
                <button class="btn-nav" onclick="window.open('/chat', '_blank')">💬 大脑对话框</button>
            </div>

            <div class="filters">
                <h3>筛选条件</h3>
                <div class="filter-row">
                    <div class="filter-group">
                        <label for="user_id">用户 ID</label>
                        <input type="text" id="user_id" placeholder="输入用户 ID">
                    </div>
                    <div class="filter-group">
                        <label for="request_id">请求 ID</label>
                        <input type="text" id="request_id" placeholder="输入请求 ID">
                    </div>
                    <div class="filter-group">
                        <label for="entry_type">类型</label>
                        <select id="entry_type">
                            <option value="">全部</option>
                            <option value="message">消息</option>
                            <option value="operation">操作</option>
                            <option value="error">错误</option>
                            <option value="alert">告警</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="limit">条数</label>
                        <select id="limit">
                            <option value="50">50</option>
                            <option value="100" selected>100</option>
                            <option value="200">200</option>
                            <option value="500">500</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <button class="btn btn-primary" onclick="searchLogs()">查询</button>
                    </div>
                    <div class="filter-group">
                        <button class="btn btn-secondary" onclick="resetFilters()">重置</button>
                    </div>
                    <div class="filter-group">
                        <button class="btn btn-success" onclick="exportLogs()">导出 JSON</button>
                    </div>
                </div>
            </div>

            <div class="stats" id="stats">
                <div class="stat-card">
                    <h4>总日志数</h4>
                    <div class="value" id="stat-total">-</div>
                </div>
                <div class="stat-card type-message">
                    <h4>消息</h4>
                    <div class="value" id="stat-message">-</div>
                </div>
                <div class="stat-card type-operation">
                    <h4>操作</h4>
                    <div class="value" id="stat-operation">-</div>
                </div>
                <div class="stat-card type-error">
                    <h4>错误</h4>
                    <div class="value" id="stat-error">-</div>
                </div>
                <div class="stat-card type-alert">
                    <h4>告警</h4>
                    <div class="value" id="stat-alert">-</div>
                </div>
            </div>

            <div class="logs-table">
                <table>
                    <thead>
                        <tr>
                            <th>时间</th>
                            <th>类型</th>
                            <th>用户 ID</th>
                            <th>请求 ID</th>
                            <th>内容</th>
                        </tr>
                    </thead>
                    <tbody id="logs-body">
                        <tr><td colspan="5" class="loading">加载中...</td></tr>
                    </tbody>
                </table>
                <div class="pagination">
                    <button class="btn btn-secondary" id="prev-btn" onclick="prevPage()">上一页</button>
                    <span id="page-info">第 1 页</span>
                    <button class="btn btn-secondary" id="next-btn" onclick="nextPage()">下一页</button>
                </div>
            </div>
        </div>

        <script>
            let currentPage = 1;
            const pageSize = 100;

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            async function fetchLogs() {
                const params = new URLSearchParams();
                const user_id = document.getElementById('user_id').value;
                const request_id = document.getElementById('request_id').value;
                const entry_type = document.getElementById('entry_type').value;
                const limit = document.getElementById('limit').value;

                if (user_id) params.append('user_id', user_id);
                if (request_id) params.append('request_id', request_id);
                if (entry_type) params.append('entry_type', entry_type);
                if (limit) params.append('limit', limit);

                const tbody = document.getElementById('logs-body');
                tbody.innerHTML = '<tr><td colspan="5" class="loading">加载中...</td></tr>';

                try {
                    const response = await fetch(`/api/audit/logs?${params}`);
                    const data = await response.json();

                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="loading">暂无数据</td></tr>';
                        return;
                    }

                    tbody.innerHTML = data.map(entry => `
                        <tr>
                            <td class="timestamp">${entry.timestamp.replace('T', ' ')}</td>
                            <td><span class="entry-type ${entry.entry_type}">${entry.entry_type}</span></td>
                            <td>${entry.user_id || '-'}</td>
                            <td>${entry.request_id || '-'}</td>
                            <td class="content" title="${escapeHtml(entry.content)}">${escapeHtml(entry.content)}</td>
                        </tr>
                    `).join('');

                    updateStats(data);

                } catch (error) {
                    tbody.innerHTML = `<tr><td colspan="5" class="loading" style="color:red">加载失败：${error.message}</td></tr>`;
                }
            }

            async function fetchStats() {
                try {
                    const response = await fetch('/api/audit/stats');
                    const stats = await response.json();
                    document.getElementById('stat-total').textContent = stats.total || 0;
                    document.getElementById('stat-message').textContent = stats.message || 0;
                    document.getElementById('stat-operation').textContent = stats.operation || 0;
                    document.getElementById('stat-error').textContent = stats.error || 0;
                    document.getElementById('stat-alert').textContent = stats.alert || 0;
                } catch (error) {
                    console.error('Failed to fetch stats:', error);
                }
            }

            function updateStats(data) {
                const stats = { message: 0, operation: 0, error: 0, alert: 0 };
                data.forEach(entry => {
                    if (stats[entry.entry_type] !== undefined) {
                        stats[entry.entry_type]++;
                    }
                });
                document.getElementById('stat-message').textContent = stats.message;
                document.getElementById('stat-operation').textContent = stats.operation;
                document.getElementById('stat-error').textContent = stats.error;
                document.getElementById('stat-alert').textContent = stats.alert;
                document.getElementById('stat-total').textContent = data.length;
            }

            function searchLogs() {
                currentPage = 1;
                fetchLogs();
            }

            function resetFilters() {
                document.getElementById('user_id').value = '';
                document.getElementById('request_id').value = '';
                document.getElementById('entry_type').value = '';
                document.getElementById('limit').value = '100';
                fetchLogs();
            }

            async function exportLogs() {
                const params = new URLSearchParams();
                const user_id = document.getElementById('user_id').value;
                const request_id = document.getElementById('request_id').value;
                const entry_type = document.getElementById('entry_type').value;

                if (user_id) params.append('user_id', user_id);
                if (request_id) params.append('request_id', request_id);
                if (entry_type) params.append('entry_type', entry_type);

                try {
                    const response = await fetch(`/api/audit/export?${params}`);
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `audit_export_${new Date().toISOString().slice(0,10)}.json`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                } catch (error) {
                    alert('导出失败：' + error.message);
                }
            }

            function prevPage() {
                if (currentPage > 1) {
                    currentPage--;
                    fetchLogs();
                }
            }

            function nextPage() {
                currentPage++;
                fetchLogs();
            }

            // 初始化
            fetchStats();
            fetchLogs();

            // 自动刷新 (每 30 秒)
            setInterval(fetchStats, 30000);
        </script>
    </body>
    </html>
    """
    return html


# ============ 大脑对话框页面 ============

@app.get("/chat", response_class=HTMLResponse, tags=["Web"])
async def chat_page():
    """大脑对话框页面"""
    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Phoenix Core - 大脑对话框</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #1a1a2e;
                padding: 20px;
                color: #eee;
                min-height: 100vh;
            }
            .container { max-width: 900px; margin: 0 auto; }
            .header-actions {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                align-items: center;
            }
            .btn-nav {
                padding: 10px 20px;
                background: #00d9ff;
                color: #1a1a2e;
                text-decoration: none;
                border-radius: 6px;
                font-size: 14px;
                border: none;
                cursor: pointer;
                font-weight: 600;
            }
            .btn-nav:hover { background: #00b8d9; }
            h1 {
                color: #00d9ff;
                margin-bottom: 10px;
                padding-bottom: 10px;
                border-bottom: 2px solid #00d9ff;
                text-shadow: 0 0 10px rgba(0, 217, 255, 0.3);
            }
            .subtitle { color: #888; margin-bottom: 20px; font-size: 14px; }
            .chat-container {
                background: #16213e;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 217, 255, 0.1);
                overflow: hidden;
                border: 1px solid #0f3460;
            }
            .chat-messages {
                height: 500px;
                overflow-y: auto;
                padding: 20px;
                background: #0f1b2e;
            }
            .message {
                margin-bottom: 15px;
                display: flex;
                flex-direction: column;
            }
            .message.user { align-items: flex-end; }
            .message.brain { align-items: flex-start; }
            .message-content {
                max-width: 80%;
                padding: 12px 18px;
                border-radius: 12px;
                line-height: 1.5;
            }
            .message.user .message-content {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .message.brain .message-content {
                background: #1a365d;
                color: #e2e8f0;
                border-left: 3px solid #00d9ff;
            }
            .message-meta {
                font-size: 11px;
                color: #666;
                margin-top: 4px;
                padding: 0 8px;
            }
            .typing-indicator {
                display: flex;
                gap: 4px;
                padding: 12px 18px;
            }
            .typing-indicator span {
                width: 8px;
                height: 8px;
                background: #00d9ff;
                border-radius: 50%;
                animation: bounce 1.4s infinite ease-in-out both;
            }
            .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
            .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
            @keyframes bounce {
                0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
                40% { transform: scale(1); opacity: 1; }
            }
            .chat-input-container {
                padding: 15px 20px;
                background: #16213e;
                border-top: 1px solid #0f3460;
                display: flex;
                gap: 12px;
            }
            .chat-input {
                flex: 1;
                padding: 14px 18px;
                border: 2px solid #0f3460;
                border-radius: 25px;
                background: #0f1b2e;
                color: #fff;
                font-size: 14px;
                resize: none;
            }
            .chat-input:focus { outline: none; border-color: #00d9ff; }
            .chat-input::placeholder { color: #4a5568; }
            .send-btn {
                width: 48px;
                height: 48px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%);
                color: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .send-btn:hover { transform: scale(1.05); box-shadow: 0 4px 15px rgba(0, 217, 255, 0.4); }
            .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .quick-actions {
                padding: 12px 20px;
                background: #1a2744;
                border-top: 1px solid #0f3460;
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }
            .quick-action-btn {
                padding: 6px 14px;
                border: 1px solid #0f3460;
                border-radius: 16px;
                background: transparent;
                color: #00d9ff;
                font-size: 12px;
                cursor: pointer;
            }
            .quick-action-btn:hover { background: #0f3460; }
            .status-bar {
                padding: 8px 20px;
                background: #0f1b2e;
                border-top: 1px solid #0f3460;
                font-size: 12px;
                color: #666;
                display: flex;
                justify-content: space-between;
            }
            .status-indicator {
                display: inline-block;
                width: 8px;
                height: 8px;
                background: #10b981;
                border-radius: 50%;
                margin-right: 6px;
                animation: pulse 2s infinite;
            }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-actions">
                <button class="btn-nav" onclick="window.location.href='/'">📊 审计日志</button>
            </div>
            <h1>🧠 Phoenix Core - 大脑对话框</h1>
            <p class="subtitle">与 Phoenix Core 主大脑直接对话 · 意图识别 · 任务拆解 · 智能编排</p>

            <div class="chat-container">
                <div class="chat-messages" id="chat-messages">
                    <div class="message brain">
                        <div class="message-content">
                            你好！我是 Phoenix Core 主大脑 🧠<br><br>
                            我可以帮你：
                            • 意图识别与任务拆解
                            • 多 Bot 协作编排
                            • 查询审计日志与任务状态<br><br>
                            有什么可以帮你的？
                        </div>
                        <div class="message-meta">刚刚</div>
                    </div>
                </div>

                <div class="quick-actions">
                    <button class="quick-action-btn" onclick="sendQuick('你好')">👋 打招呼</button>
                    <button class="quick-action-btn" onclick="sendQuick('帮我查订单 #12345')">📦 查订单</button>
                    <button class="quick-action-btn" onclick="sendQuick('今天有什么任务？')">📋 查任务</button>
                    <button class="quick-action-btn" onclick="sendQuick('查看最近的错误日志')">⚠️ 查错误</button>
                </div>

                <div class="chat-input-container">
                    <textarea class="chat-input" id="chat-input" placeholder="输入你的问题或指令..." rows="1"></textarea>
                    <button class="send-btn" id="send-btn" onclick="sendMessage()">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z"/>
                        </svg>
                    </button>
                </div>

                <div class="status-bar">
                    <span><span class="status-indicator"></span>大脑已连接</span>
                    <span id="request-status">就绪</span>
                </div>
            </div>
        </div>

        <script>
            const messagesContainer = document.getElementById('chat-messages');
            const chatInput = document.getElementById('chat-input');
            const sendBtn = document.getElementById('send-btn');
            const requestStatus = document.getElementById('request-status');
            let isProcessing = false;

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            function appendMessage(content, isUser = false, requestId = '') {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isUser ? 'user' : 'brain'}`;
                const timestamp = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
                messageDiv.innerHTML = `
                    <div class="message-content">${escapeHtml(content)}</div>
                    <div class="message-meta">${isUser ? '你' : '大脑'} · ${timestamp}${requestId ? ' · ID: ' + requestId : ''}
                    </div>`;
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            function showTypingIndicator() {
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message brain';
                typingDiv.id = 'typing-indicator';
                typingDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
                messagesContainer.appendChild(typingDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            function removeTypingIndicator() {
                const el = document.getElementById('typing-indicator');
                if (el) el.remove();
            }

            async function sendMessage() {
                const message = chatInput.value.trim();
                if (!message || isProcessing) return;

                appendMessage(message, true);
                chatInput.value = '';
                isProcessing = true;
                sendBtn.disabled = true;
                requestStatus.textContent = '处理中...';
                showTypingIndicator();

                try {
                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message, user_id: 'web-' + Date.now() })
                    });
                    const data = await response.json();
                    removeTypingIndicator();
                    if (data.success) {
                        appendMessage(data.response, false, data.request_id);
                        requestStatus.textContent = '完成';
                    } else {
                        appendMessage('⚠️ ' + data.message, false);
                        requestStatus.textContent = '失败';
                    }
                } catch (error) {
                    removeTypingIndicator();
                    appendMessage('❌ 请求失败：' + error.message, false);
                    requestStatus.textContent = '错误';
                } finally {
                    isProcessing = false;
                    sendBtn.disabled = false;
                    requestStatus.textContent = '就绪';
                }
            }

            function sendQuick(text) {
                chatInput.value = text;
                sendMessage();
            }

            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        </script>
    </body>
    </html>
    """
    return html


# ============ Chat API ============

@app.post("/api/chat", tags=["Chat"])
async def chat_with_brain(request: dict):
    """与大脑对话"""
    message = request.get("message", "")
    user_id = request.get("user_id", "web-user")

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    try:
        brain = get_brain_instance()
        response = await brain.process(message, user_id)
        return {
            "success": response.success,
            "response": response.message,
            "request_id": response.request_id,
            "task_id": response.task_id,
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "success": False,
            "message": f"大脑思考中... ({str(e)[:100]})",
            "request_id": f"err-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }


# ============ Audit API ============

@app.get("/api/audit/logs", tags=["API"])
async def list_audit_logs(
    user_id: Optional[str] = Query(None, description="用户 ID"),
    request_id: Optional[str] = Query(None, description="请求 ID"),
    entry_type: Optional[str] = Query(None, description="日志类型"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO 格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO 格式)"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
):
    """查询审计日志"""
    audit_logger = get_logger()

    try:
        if request_id:
            entries = audit_logger.query_by_request(request_id)
        elif user_id:
            entries = audit_logger.query_by_user(user_id, limit)
        elif start_time and end_time:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            entries = audit_logger.query_by_time_range(start, end, entry_type)
        elif entry_type:
            if entry_type == "error":
                entries = audit_logger.query_errors(limit=limit)
            else:
                end = datetime.now()
                start = end - timedelta(days=1)
                entries = audit_logger.query_by_time_range(start, end, entry_type)[:limit]
        else:
            end = datetime.now()
            start = end - timedelta(hours=24)
            entries = audit_logger.query_by_time_range(start, end, None)[:limit]

        return [entry.to_dict() for entry in entries[:limit]]

    except Exception as e:
        logger.error(f"查询审计日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/stats", tags=["API"])
async def get_audit_stats():
    """获取审计日志统计"""
    audit_logger = get_logger()

    try:
        end = datetime.now()
        start = end - timedelta(hours=24)
        all_entries = audit_logger.query_by_time_range(start, end)

        stats = {
            "total": len(all_entries),
            "message": sum(1 for e in all_entries if e.entry_type == "message"),
            "operation": sum(1 for e in all_entries if e.entry_type == "operation"),
            "error": sum(1 for e in all_entries if e.entry_type == "error"),
            "alert": sum(1 for e in all_entries if e.entry_type == "alert"),
            "time_range": {
                "start": start.isoformat(),
                "end": end.isoformat()
            }
        }
        return stats

    except Exception as e:
        logger.error(f"获取统计失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/export", tags=["API"])
async def export_audit_logs(
    user_id: Optional[str] = Query(None, description="用户 ID"),
    request_id: Optional[str] = Query(None, description="请求 ID"),
    entry_type: Optional[str] = Query(None, description="日志类型"),
):
    """导出审计日志为 JSON"""
    audit_logger = get_logger()

    try:
        if request_id:
            entries = audit_logger.query_by_request(request_id)
        elif user_id:
            entries = audit_logger.query_by_user(user_id, limit=1000)
        else:
            end = datetime.now()
            start = end - timedelta(days=7)
            entries = audit_logger.query_by_time_range(start, end, entry_type)

        data = [entry.to_dict() for entry in entries]

        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": f"attachment; filename=audit_export_{datetime.now().strftime('%Y%m%d')}.json"
            }
        )

    except Exception as e:
        logger.error(f"导出审计日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/errors", tags=["API"])
async def list_errors(
    request_id: Optional[str] = Query(None, description="请求 ID"),
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
):
    """查询错误日志"""
    audit_logger = get_logger()

    try:
        entries = audit_logger.query_errors(request_id, limit)
        return [entry.to_dict() for entry in entries]

    except Exception as e:
        logger.error(f"查询错误日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", tags=["Health"])
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "phoenix-core-audit-api"}


# ============ 主程序 ============

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print("=" * 60)
    print("Phoenix Core - 审计日志 Web API")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:8000")
    print("大脑对话框：http://localhost:8000/chat")
    print("API 文档：http://localhost:8000/docs")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
