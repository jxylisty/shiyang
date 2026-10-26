# -*- coding: utf-8 -*-
"""
从 Wikimedia Commons 预拉取药材/食材真实照片 → frontend/public/img/materials/
- 每种物料搜 1 张图，优先 CC0/PD，其次 CC BY（记录作者与许可到 credits.json，页脚可展示）
- 只取 480px 缩略图（单张 <50KB），国内直连 Wikimedia 缩略域可能不稳，构建期拉取不走运行时
- 失败的物料跳过并记录，页面侧做无图兜底
用法：python -X utf8 fetch_material_images.py [--force]
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "img" / "materials"
OUT.mkdir(parents=True, exist_ok=True)

# 物料 → Commons 搜索词（英文命中率高；保守用学名/通用名）
MATERIALS = {
    # 药食同源（库内 34 味里最常用的）
    "枸杞子": "goji berries dried", "菊花": "chrysanthemum tea dried flowers",
    "金银花": "Lonicera japonica flowers", "陈皮": "dried tangerine peel",
    "山楂": "Crataegus pinnatifida fruit", "乌梅": "dried smoked plum umeboshi",
    "大枣": "jujube fruit dried", "生姜": "ginger root", "干姜": "dried ginger slices",
    "甘草": "Glycyrrhiza glabra root", "薄荷": "mentha leaves", "麦冬": "Ophiopogon japonicus",
    "桔梗": "Platycodon grandiflorus root", "胖大海": "Sterculia lychnophora seed",
    "百合": "lilium bulbs dried", "茯苓": "Poria cocos sclerotium",
    "薏苡仁": "coix seeds Job's tears", "黄芪": "Astragalus membranaceus root",
    "党参": "Codonopsis pilosula root", "当归": "Angelica sinensis root",
    "桑叶": "mulberry leaves", "桑椹": "mulberries fruit", "酸枣仁": "Ziziphus jujuba seeds",
    "莲子": "lotus seeds dried", "龙眼肉": "dried longan", "玉竹": "Polygonatum odoratum",
    "石斛": "Dendrobium officinale", "西洋参": "Panax quinquefolius root",
    "葛根": "kudzu root", "决明子": "Cassia tora seeds", "荷叶": "lotus leaf dried",
    "玫瑰花": "dried rose buds tea", "山药": "Chinese yam", "黄精": "Polygonatum sibiricum",
    "肉桂": "cinnamon sticks", "蒲公英": "dried dandelion root tea", "麦芽": "barley malt dried",
    # 常用普通食材（药膳）
    "雪梨": "Asian pear fruit", "莲藕": "lotus root", "银耳": "Tremella fuciformis",
    "冬瓜": "winter melon", "白萝卜": "daikon radish", "绿豆": "mung beans",
    "赤小豆": "adzuki beans", "粳米": "white rice grains", "小米": "foxtail millet grains",
    "红糖": "brown sugar block", "蜂蜜": "honey jar", "牛奶": "milk glass",
    "鸡蛋": "chicken eggs", "羊肉": "raw lamb meat", "鸡肉": "raw chicken meat",
    "鸭肉": "raw duck meat", "鲫鱼": "crucian carp fish", "猪骨": "pork bones raw",
    "核桃": "walnuts", "黑芝麻": "black sesame seeds", "板栗": "chestnuts",
    # 2026-10 补齐：方子库高频缺图配料（冰糖/枣/猪瘦肉等无药用图，用食材通用图）
    "冰糖": "rock sugar crystals", "枣": "jujube fruit dried",
    "铁皮石斛": "Dendrobium officinale stems", "芡实": "Euryale ferox seeds",
    "蜜枣": "candied jujube", "猪瘦肉": "raw pork tenderloin",
    "绿茶": "dried green tea leaves", "鲜芦根": "reed rhizome Phragmites",
    "当归": "Angelica sinensis dried root", "花生": "raw peanuts shelled",
    "佛手": "Buddha's hand citron", "天冬": "Asparagus root dried herb",
    "玉米须": "corn silk", "柚子": "pomelo fruit", "覆盆子": "raspberries",
    "海棠果": "crabapples fruit", "马蹄": "water chestnuts", "眉豆": "black-eyed peas",
    "猪脊骨": "pork spine bones raw", "椰子": "coconut", "木瓜": "papaya fruit",
    "地黄": "Rehmannia glutinosa root", "乌鸡": "silkie chicken raw",
    "排骨": "raw pork ribs", "猪肝": "raw pork liver", "菠菜": "spinach leaves",
    "红豆": "red beans adzuki", "猪肚": "raw pork stomach", "鲢鱼头": "fish head raw",
    "白糖": "white sugar", "猪肉": "raw pork meat",
    # 补搜词：首轮无命中/429 的品种
    "百合": "lilium bulb food", "天冬2": "Asparagus cochinchinensis dried",
    # 药材图鉴缺图 2 味（2026-10）
    "橘红": "dried tangerine peel", "花椒": "Sichuan peppercorns",
}

UA = {"User-Agent": "ShiyangStudentProject/0.2 (educational, non-commercial; contact: campus)"}
OK_LICENSES = ["CC0", "Public domain", "PD", "CC BY"]  # 按优先级：CC0 > PD > CC BY(需署名)
BAD_EXT = re.compile(r"\.(svg|pdf|djvu|ogv|webm|gif)$", re.I)


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def pick_image(keyword):
    """返回 {thumb, license, artist, title} 或 None"""
    d = api({
        "action": "query", "generator": "search",
        "gsrsearch": keyword, "gsrnamespace": 6, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 480, "format": "json",
    })
    pages = (d.get("query") or {}).get("pages") or {}
    best = None
    for p in pages.values():
        title = p.get("title", "")
        if BAD_EXT.search(title):
            continue
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()[:60]
        mime = ii.get("mime", "")
        if not mime.startswith("image/") or mime == "image/svg+xml":
            continue
        if not ii.get("thumburl"):
            continue
        lic_rank = next((i for i, ok in enumerate(OK_LICENSES) if lic.startswith(ok)), 99)
        if lic_rank == 99:
            continue
        cand = {"thumb": ii["thumburl"], "license": lic, "artist": artist, "title": title}
        if best is None or lic_rank < best["_rank"]:
            best = {**cand, "_rank": lic_rank}
        if best["_rank"] == 0:
            break
    if best:
        best.pop("_rank", None)
    return best


def main(force=False):
    credits, fetched, skipped = {}, 0, []
    for name, kw in MATERIALS.items():
        fp = OUT / f"{name}.jpg"
        if fp.exists() and not force:
            credits[name] = json.loads((OUT.parent / "credits.json").read_text(encoding="utf-8"))["credits"][name] if (OUT.parent / "credits.json").exists() and False else credits.get(name)
            continue
        try:
            info = pick_image(kw)
            if not info:
                skipped.append(name)
                print(f"× {name}: 无合适许可图片")
                continue
            req = urllib.request.Request(info["thumb"], headers=UA)
            data = urllib.request.urlopen(req, timeout=30).read()
            fp.write_bytes(data)
            credits[name] = {k: info[k] for k in ("license", "artist", "title")}
            fetched += 1
            print(f"✓ {name}: {info['license']} ({len(data)//1024}KB) {info['artist'][:24]}")
            time.sleep(0.4)  # 礼貌限速
        except Exception as e:
            skipped.append(name)
            print(f"× {name}: {str(e)[:60]}")

    (OUT.parent / "credits.json").write_text(
        json.dumps({"source": "Wikimedia Commons", "credits": credits}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n拉取 {fetched} 张 | 跳过 {len(skipped)} 个: {'、'.join(skipped) or '无'}")
    print(f"输出: {OUT} | 许可记录: {OUT.parent / 'credits.json'}")


if __name__ == "__main__":
    main("--force" in sys.argv)
