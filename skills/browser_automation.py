#!/usr/bin/env python3
"""
Browser Automation Skill for Phoenix Core

基于 Vibium 的浏览器自动化技能，所有 Bot 都可以使用。

功能:
- 打开网页
- 点击元素
- 填写表单
- 截图
- 执行 JavaScript

使用示例:
    from skills.browser_automation import BrowserSkill

    browser = BrowserSkill()
    await browser.open("https://github.com")
    await browser.click("a[href='/login']")
    await browser.fill("input#login_field", "username")
    await browser.screenshot("github-login.png")
"""

import asyncio
import vibium
from typing import Optional
from pathlib import Path


class BrowserSkill:
    """浏览器自动化技能"""

    def __init__(self, headless: bool = False):
        """
        初始化浏览器技能

        Args:
            headless: 是否无头模式（默认 False，显示浏览器）
        """
        self.headless = headless
        self.browser = None
        self.page = None

    async def start(self):
        """启动浏览器"""
        if self.browser is None:
            self.browser = await vibium.start_browser(headless=self.headless)
            self.page = await self.browser.new_page()
        return self

    async def stop(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None

    async def open(self, url: str):
        """打开网页"""
        await self.start()
        await self.page.goto(url)
        return self

    async def click(self, selector: str):
        """点击元素"""
        await self.page.click(selector)
        return self

    async def fill(self, selector: str, text: str):
        """填写输入框"""
        await self.page.fill(selector, text)
        return self

    async def type_text(self, selector: str, text: str):
        """模拟键盘输入（逐字输入）"""
        await self.page.type(selector, text)
        return self

    async def screenshot(self, path: str):
        """截图"""
        await self.page.screenshot(path=path)
        return path

    async def evaluate(self, js_code: str):
        """执行 JavaScript 代码"""
        result = await self.page.evaluate(js_code)
        return result

    async def wait(self, selector: str, timeout: int = 30000):
        """等待元素出现"""
        await self.page.wait_for_selector(selector, timeout=timeout)
        return self

    async def wait_for_navigation(self):
        """等待页面导航完成"""
        await self.page.wait_for_load_state("networkidle")
        return self

    async def get_text(self, selector: str) -> str:
        """获取元素文本"""
        element = await self.page.query_selector(selector)
        if element:
            return await element.text_content()
        return ""

    async def get_html(self) -> str:
        """获取页面 HTML"""
        return await self.page.content()

    async def press_key(self, key: str):
        """按下键盘"""
        await self.page.keyboard.press(key)
        return self


# 快捷函数
async def open_browser(url: str = "about:blank", headless: bool = False) -> BrowserSkill:
    """快速打开浏览器"""
    browser = BrowserSkill(headless=headless)
    await browser.start()
    if url != "about:blank":
        await browser.open(url)
    return browser


# CLI 入口
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("用法：python3 browser_automation.py <URL>")
            print("示例：python3 browser_automation.py https://github.com")
            sys.exit(1)

        url = sys.argv[1]
        browser = await open_browser(url)
        print(f"已打开：{url}")
        print("按 Ctrl+C 关闭浏览器")

        try:
            await asyncio.sleep(60)  # 保持浏览器打开 60 秒
        except KeyboardInterrupt:
            pass
        finally:
            await browser.stop()

    asyncio.run(main())
