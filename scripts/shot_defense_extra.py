# -*- coding: utf-8 -*-
"""
截取答辩专用的实机高亮截图：
- 11-pantry.png: 我的茶罐 105 味全分类货架与悬浮配伍底栏
- 12-compound-ad-out.png: 白皮杉醇（红色应用域外降级徽章）
- 13-compound-chembl.png: 黄芩素（ChEMBL 36 靶点实验活性与 L1 强证据）
- 14-custom-recipe.png: 拍照识方与形近字纠偏
- 15-elder-home.png: 长辈大字高对比适老模式实机展示
"""
import asyncio
import os
import urllib.parse
from playwright.async_api import async_playwright

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots")
BASE = "http://127.0.0.1:5174"
CHROME = r"C:\Users\zzx05\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"

EXTRA_PAGES = [
    ("11-pantry.png", "/pantry", 2000),
    ("12-compound-ad-out.png", f"/compounds/{urllib.parse.quote('白皮杉醇')}", 2000),
    ("13-compound-chembl.png", f"/compounds/{urllib.parse.quote('黄芩素')}", 2000),
    ("14-custom-recipe.png", "/custom-recipe", 2000),
]

async def main():
    os.makedirs(OUT, exist_ok=True)
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
        for name, path, wait_ms in EXTRA_PAGES:
            try:
                await page.goto(BASE + path, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(wait_ms)
                target = os.path.join(OUT, name)
                await page.screenshot(path=target, full_page=False)
                print(f"Captured {name} successfully!")
            except Exception as e:
                print(f"Error capturing {name}: {e}")

        # 捕获长辈适老模式
        try:
            await page.goto(BASE + "/", wait_until="networkidle")
            # 通过导航栏或点击触发适老模式
            btn = await page.query_selector("text=长辈") or await page.query_selector("[title*=适老]") or await page.query_selector(".elder-toggle")
            if btn:
                await btn.click()
                await page.wait_for_timeout(1000)
            else:
                await page.evaluate("() => { localStorage.setItem('shiyang_elder_mode', '1'); document.documentElement.classList.add('elder'); }")
                await page.reload(wait_until="networkidle")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(OUT, "15-elder-home.png"), full_page=False)
            print("Captured 15-elder-home.png successfully!")
        except Exception as e:
            print(f"Error capturing elder home: {e}")

        await browser.close()
    print("Done capturing defense extra screenshots!")

if __name__ == "__main__":
    asyncio.run(main())
