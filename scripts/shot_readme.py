"""README 展示图抓取（Playwright，移动端视口）。

用法（后端 8100 + 前端 5174 需已运行）：
    python -X utf8 scripts/shot_readme.py

产物写入 docs/screenshots/（PNG 入仓库，供 README 引用）。
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = os.environ.get("SHOT_BASE", "http://127.0.0.1:5174")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots")

# (文件名, 路径, 等待选择器, 额外等待毫秒)
PAGES = [
    ("01-home.png", "/", "text=食养有据", 1600),
    ("02-recipes.png", "/recipes", ".recipe-row, .van-card, [class*=recipe]", 1200),
    ("03-recipe-detail.png", "/recipes/1", "text=银菊利咽茶", 2000),
    ("04-compound.png", "/compounds/落新妇苷", "text=落新妇苷", 1800),
    ("05-chem-map.png", "/chem-map", "canvas, svg", 2200),
    ("06-quiz.png", "/quiz", "text=体质", 1400),
    ("07-herbs.png", "/herbs", "text=药材", 1400),
    ("08-compare.png", "/recipes/compare", "text=对比", 1600),
    ("09-assistant.png", "/assistant", "text=问一问", 1400),
    ("10-openapi.png", "/open-api", "text=API", 1400),
]


def find_chromium():
    """Python playwright 的浏览器版本号可能与本机已装的对不上，故直接找已装 chrome.exe。"""
    explicit = os.environ.get("SHOT_CHROME")
    if explicit:
        return explicit
    root = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ms-playwright")
    if not os.path.isdir(root):
        return None
    for d in sorted(os.listdir(root), reverse=True):
        exe = os.path.join(root, d, "chrome-win64", "chrome.exe")
        if os.path.exists(exe):
            return exe
    return None


async def main():
    os.makedirs(OUT, exist_ok=True)
    chrome = find_chromium()
    if chrome:
        print(f"使用浏览器：{chrome}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chrome) if chrome else await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            locale="zh-CN",
            is_mobile=True,
            has_touch=True,
        )
        page = await ctx.new_page()
        failed = []
        for name, path, selector, wait_ms in PAGES:
            url = BASE + path
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                except Exception:
                    print(f"  [warn] {name}: selector not found ({selector})，仍截图")
                await page.wait_for_timeout(wait_ms)
                await page.screenshot(path=os.path.join(OUT, name), full_page=False)
                print(f"  [ok] {name}  <- {path}")
            except Exception as e:
                failed.append((name, str(e)))
                print(f"  [FAIL] {name}: {e}")
        await browser.close()
        if failed:
            print("\n失败项：")
            for n, e in failed:
                print(f"  {n}: {e}")
            sys.exit(1)
    print(f"\n完成，输出目录：{OUT}")


asyncio.run(main())
