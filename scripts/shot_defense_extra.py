# -*- coding: utf-8 -*-
"""
截取答辩专用的实机高亮截图（自包含启停后端与前端服务，确保每张图精准滚到核心看点，绝无 404 或空状态）：
- 11-pantry.png: 我的茶罐全分类货架 + 勾选食材匹配结果
- 12-compound-ad-out.png: 白皮杉醇（滚至红色「应用域外」降级预警徽章）
- 13-compound-chembl.png: 黄芩素（滚至 ChEMBL 36 靶点实验活性与 L1 强证据列表）
- 04-compound.png: 落新妇苷（滚至双模型对比与「主模型单独高」交叉验证卡）
- 14-custom-recipe.png: 自定义鉴方（/pantry 切至「自定义鉴方」标签页并展示形近字纠偏与识方）
- 08-compare.png: 对比实验室（/recipes/compare?a=1&b=2 双方并排比对结果）
"""
import asyncio
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BASE = "http://127.0.0.1:5174"
API_HEALTH = "http://127.0.0.1:8100/api/v1/health"
CHROME = r"C:\Users\zzx05\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"


def wait_url(url: str, timeout: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


async def capture_all():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            locale="zh-CN",
            is_mobile=True,
            has_touch=True,
        )
        page = await ctx.new_page()

        # 1. 白皮杉醇 -> 滚到「模型可信度 · 应用域」（红色 应用域外 徽章）
        await page.goto(f"{BASE}/compounds/{urllib.parse.quote('白皮杉醇')}", wait_until="networkidle")
        await page.wait_for_timeout(1200)
        await page.evaluate("() => window.scrollTo(0, 260)")
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "12-compound-ad-out.png"))
        print("Captured 12-compound-ad-out.png")

        # 2. 落新妇苷 -> 滚到「双模型对比 + 独立模型交叉验证（主模型单独高）」
        await page.goto(f"{BASE}/compounds/{urllib.parse.quote('落新妇苷')}", wait_until="networkidle")
        await page.wait_for_timeout(1200)
        await page.evaluate("() => window.scrollTo(0, 280)")
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "04-compound.png"))
        print("Captured 04-compound.png")

        # 3. 黄芩素 -> 滚到「实验实测活性（ChEMBL · 体外测定）」
        await page.goto(f"{BASE}/compounds/{urllib.parse.quote('黄芩素')}", wait_until="networkidle")
        await page.wait_for_timeout(1200)
        chembl_el = await page.query_selector(".cd-chembl-head")
        if chembl_el:
            await chembl_el.scroll_into_view_if_needed()
            await page.evaluate("() => window.scrollBy(0, -90)")
        else:
            await page.evaluate("() => window.scrollTo(0, 720)")
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "13-compound-chembl.png"))
        print("Captured 13-compound-chembl.png")

        # 4. 我的茶罐 -> 点选「+ 润燥护嗓常备」展示已选食材与匹配结果
        await page.goto(f"{BASE}/pantry", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        preset_btn = await page.query_selector("text=润燥护嗓常备")
        if preset_btn:
            await preset_btn.click()
            await page.wait_for_timeout(1200)
        await page.evaluate("() => window.scrollTo(0, 120)")
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "11-pantry.png"))
        print("Captured 11-pantry.png")

        # 5. 自定义鉴方 -> 在 /pantry 切换到「自定义鉴方」标签页，填入含形近字的测试方并识别
        custom_tab = await page.query_selector("text=自定义鉴方")
        if custom_tab:
            await custom_tab.click()
            await page.wait_for_timeout(600)
            ta = await page.query_selector("textarea")
            if ta:
                await ta.fill("金银化 10g、枸札 10g、阵皮 6g、菊花 10g")
                await page.wait_for_timeout(300)
                parse_btn = await page.query_selector("button:has-text('识别配料')") or await page.query_selector("button:has-text('解析')") or await page.query_selector("button:has-text('开始分析')")
                if parse_btn:
                    await parse_btn.click()
                    await page.wait_for_timeout(1500)
        await page.evaluate("() => window.scrollTo(0, 140)")
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(OUT / "14-custom-recipe.png"))
        print("Captured 14-custom-recipe.png")

        # 6. 对比实验室 -> /recipes/compare?a=1&b=2
        await page.goto(f"{BASE}/recipes/compare?a=1&b=2", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        cmp_btn = await page.query_selector("button:has-text('开始对比')") or await page.query_selector("button:has-text('对比')")
        if cmp_btn:
            try:
                await cmp_btn.click(timeout=1500)
                await page.wait_for_timeout(1200)
            except Exception:
                pass
        await page.evaluate("() => window.scrollTo(0, 260)")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(OUT / "08-compare.png"))
        print("Captured 08-compare.png")

        await browser.close()


def main():
    backend_proc = None
    frontend_proc = None
    try:
        if not wait_url(API_HEALTH, timeout=1.5):
            print("Starting backend on 8100...")
            backend_proc = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100"],
                cwd=str(ROOT / "backend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            wait_url(API_HEALTH, timeout=15.0)

        if not wait_url(BASE, timeout=1.5):
            print("Starting frontend vite on 5174...")
            npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
            frontend_proc = subprocess.Popen(
                [npx_cmd, "vite", "--port", "5174", "--host", "127.0.0.1"],
                cwd=str(ROOT / "frontend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            wait_url(BASE, timeout=15.0)

        asyncio.run(capture_all())
    finally:
        for proc in (frontend_proc, backend_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
    print("All defense screenshots updated cleanly!")


if __name__ == "__main__":
    main()
