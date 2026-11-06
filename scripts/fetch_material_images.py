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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "img" / "materials"
OUT.mkdir(parents=True, exist_ok=True)

# 物料 → Commons 搜索词（英文命中率高；保守用学名/通用名）
# 值可以是 str 或 list[str]：按序尝试，前一个搜不到可用图就试下一个。
# 2026-11-06 实测规律：带限定词（dried/rhizome/slices）会把结果压进文献扫描区，
# 纯学名反而命中率高（24 项里 22 项靠学名救回，多数是 CC0）。
MATERIALS = {
    # 药食同源（库内 34 味里最常用的）
    "枸杞子": "goji berries dried", "菊花": "chrysanthemum tea dried flowers",
    "金银花": "Lonicera japonica flowers", "陈皮": "dried tangerine peel",
    "山楂": "Crataegus pinnatifida fruit",
    "乌梅": ["dried smoked plum umeboshi", "Prunus mume dried", "umeboshi"],
    "大枣": "jujube fruit dried", "生姜": "ginger root", "干姜": "dried ginger slices",
    "甘草": "Glycyrrhiza glabra root", "薄荷": "mentha leaves", "麦冬": "Ophiopogon japonicus",
    "桔梗": "Platycodon grandiflorus root", "胖大海": "Sterculia lychnophora seed",
    "百合": "lilium bulbs dried", "茯苓": "Poria cocos sclerotium",
    "薏苡仁": "coix seeds Job's tears",
    "黄芪": ["Astragalus membranaceus", "Astragalus membranaceus root"],
    "党参": "Codonopsis pilosula root",
    "桑叶": "mulberry leaves", "桑椹": "mulberries fruit", "酸枣仁": "Ziziphus jujuba seeds",
    "莲子": "lotus seeds dried", "龙眼肉": "dried longan", "玉竹": "Polygonatum odoratum",
    "石斛": "Dendrobium officinale", "西洋参": "Panax quinquefolius root",
    "葛根": "kudzu root", "决明子": "Cassia tora seeds", "荷叶": "lotus leaf dried",
    "玫瑰花": "dried rose buds tea", "山药": "Chinese yam", "黄精": "Polygonatum sibiricum",
    "肉桂": "cinnamon sticks",
    "蒲公英": ["Taraxacum officinale flower", "dried dandelion root tea"],
    "麦芽": "barley malt dried",
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
    "花生": "raw peanuts shelled",
    "佛手": "Buddha's hand citron", "天冬": "Asparagus root dried herb",
    "玉米须": "corn silk", "柚子": "pomelo fruit", "覆盆子": "raspberries",
    "海棠果": "crabapples fruit", "马蹄": "water chestnuts", "眉豆": "black-eyed peas",
    "椰子": "coconut", "木瓜": "papaya fruit",
    "乌鸡": "silkie chicken raw",
    "排骨": "raw pork ribs", "猪肝": "raw pork liver", "菠菜": "spinach leaves",
    "红豆": "red beans adzuki", "猪肚": "raw pork stomach", "鲢鱼头": "fish head raw",
    "白糖": "white sugar", "猪肉": "raw pork meat",
    # 补搜词：首轮无命中/429 的品种
    "天冬2": "Asparagus cochinchinensis dried",
    # 药材图鉴缺图 2 味（2026-10）
    "橘红": "dried tangerine peel", "花椒": "Sichuan peppercorns",

    # ===== 2026-11-06 扩容后补齐（药食同源目录 105 味，此前 63 味无图）=====
    # 用学名/通用名做搜索词，命中率高于中文名直译；这批图源仍为 Wikimedia Commons，
    # 许可与署名照旧写入 credits.json（CC BY / CC BY-SA 类，页脚可展示）。
    # —— 扩容新增药材 ——
    "丁香": "Syzygium aromaticum dried buds cloves",
    "八角茴香": "Illicium verum star anise",
    "刀豆": "Canavalia gladiata sword bean",
    "小茴香": "Foeniculum vulgare fennel seeds",
    "马齿苋": "Portulaca oleracea purslane",
    "火麻仁": "Cannabis sativa seeds hemp",
    "白芷": "Angelica dahurica root",
    "白果": "Ginkgo biloba seeds",
    "白扁豆": "Lablab purpureus hyacinth bean seeds",
    "白扁豆花": "Lablab purpureus flower",
    "肉豆蔻": "Myristica fragrans nutmeg",
    "余甘子": "Phyllanthus emblica Indian gooseberry",
    "杏仁": "Prunus armeniaca apricot kernels",
    "沙棘": ["sea buckthorn fruit", "Hippophae rhamnoides berries"],
    "牡蛎": "oyster shell dried",
    "昆布": "Saccharina japonica dried kelp",
    "罗汉果": "Siraitia grosvenorii monk fruit dried",
    "青果": "Canarium album Chinese olive fruit",
    "鱼腥草": "Houttuynia cordata herb",
    "香橼": "Citrus medica citron fruit",
    "桃仁": "Prunus persica peach kernels",
    "益智仁": "Alpinia oxyphylla dried fruit",
    "莱菔子": ["Raphanus sativus seeds", "radish seed"],
    "菊苣": "Cichorium intybus chicory root",
    "黄芥子": "Brassica juncea mustard seeds",
    "紫苏": "Perilla frutescens leaves",
    "紫苏籽": "Perilla frutescens seeds",
    "黑胡椒": "Piper nigrum black peppercorns",
    "槐花": "Sophora japonica flowers",
    "榧子": "Torreya grandis seeds",
    "藿香": "Agastache rugosa herb",
    "山柰": "Kaempferia galanga rhizome",
    "西红花": "Crocus sativus saffron threads",
    "姜黄": "Curcuma longa turmeric rhizome",
    "荜茇": ["Piper longum dried", "long pepper spice"],
    "灵芝": "Ganoderma lucidum Lingzhi mushroom",
    "山茱萸": "Cornus officinalis dried fruit",
    "杜仲叶": "Eucommia ulmoides leaves",
    "阿胶": "Ejiao donkey hide gelatin",
    # —— 普通食材补 3 味（第一轮补图时用，纯学名/通用名兜底）——
    "猪瘦肉": ["pork tenderloin", "raw pork meat"],
    "猪肚": ["pork stomach", "pork offal"],
    "猪脊骨": ["pork ribs", "pork spine"],

    # ===== 第二轮补图（2026-11-06）：首轮失败的 24 项，改用纯学名 =====
    # 说明：带 dried/rhizome 等限定词的搜索会把 Commons 结果压到文献扫描区，
    # 纯学名命中率高得多。这里用 list 保留原词作首选、学名作回退。
    "天麻": ["Gastrodia elata", "Gastrodia elata rhizome dried"],
    "栀子": ["Gardenia jasminoides", "Gardenia jasminoides fruit dried"],
    "砂仁": ["Amomum villosum", "Amomum villosum dried fruit"],
    "槐米": ["Sophora japonica flower", "Sophora japonica buds"],
    "薤白": ["Allium macrostemon", "Allium macrostemon bulbs"],
    "草果": ["Amomum tsaoko", "Amomum tsaoko dried fruit"],
    "肉苁蓉": ["Cistanche deserticola", "Cistanche deserticola dried stem"],
    "化橘红": ["Citrus maxima peel", "Citrus grandis peel"],
    "鸡内金": ["chicken gizzard", "chicken gizzard lining dried"],
    "郁李仁": ["Prunus japonica", "Prunus japonica seeds"],
    "枳椇子": ["Hovenia dulcis", "Hovenia dulcis seeds"],
    "香薷": ["Elsholtzia ciliata", "Elsholtzia ciliata herb"],
    "小蓟": ["Cirsium setosum", "Cirsium setosum thistle herb"],
    "乌梢蛇": ["Zaocys dhumnades", "Ptyas dhumnades snake"],
    "代代花": ["Citrus aurantium flower", "Citrus aurantium amara flower"],
    "鲜白茅根": ["Imperata cylindrica", "Imperata cylindrica root"],
    "蒲公英根": ["Taraxacum root", "dandelion root dried"],
    "当归": ["Angelica sinensis", "Dried angelica slices"],
    "地黄": ["Rehmannia glutinosa plant", "Rehmannia glutinosa"],
    "天冬": ["Asparagus cochinchinensis", "Asparagus cochinchinensis root dried"],

    # ===== 第三轮：词表漏收的 3 味（2026-11-06 覆盖率核查发现）=====
    "淡竹叶": ["Lophatherum gracile", "Lophatherum"],
    "淡豆豉": ["fermented soybean", "douchi"],
    "高良姜": ["Alpinia officinarum", "Alpinia officinarum rhizome"],
}

UA = {"User-Agent": "ShiyangStudentProject/0.3 (https://github.com/jxylisty/shiyang; educational, non-commercial)"}
# 按优先级：CC0 > PD > CC BY > CC BY-SA（后两者必须署名，credits.json 已记录）
# 注意：CC BY-SA 是 Commons 上最常见的可用许可，原白名单漏掉了它，
# 导致「无合适许可图片」大量误判（2026-11-06 实测修正）。
OK_LICENSES = ["CC0", "Public domain", "PD", "CC BY-SA", "CC BY"]
BAD_EXT = re.compile(r"\.(svg|pdf|djvu|ogv|webm|gif)$", re.I)
# 搜索命中里混着大量扫描书页/文献插图/地图——许可虽是 PD，但图不可用（是书页不是实物照）。
# 2026-11-06 实测：当归/地黄/猪瘦肉等「无图」正是这一类把候选位占满了。
BAD_TITLE = re.compile(
    r"(\(IA |hand-?book|catalogue|catalog of|treatise|journal|"
    r"bulletin|florist|illustrat|plate|map of|cookery|a complete guide|"
    r"OJ L |EUR \d{4}|regulation|directive|specification|"
    r"phrenolog|almanac|encyclop|dictionar|annual report|"
    r"stamp|seed packet|print\.jpg|drawing|water colour|watercolor|"
    r"painting|engraving|lithograph|Naturalis Biodiversity|RMNH\.ART|"
    r"MET DP|herbaria|BHL|NARA|"
    r"\.pdf|\.djvu|^File:IA )", re.I)


def api(params, retries=4):
    """调 Commons API。429/5xx 指数退避重试——批量拉 60+ 味时必踩限流，
    原来一次就放弃，导致大半物料被误记为「无图」。"""
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
            wait = 3 * (2 ** i)  # 3s, 6s, 12s, 24s
            print(f"    · {e.code} 限流，{wait}s 后重试 ({i+1}/{retries})")
            time.sleep(wait)
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def pick_image(keyword):
    """返回 {thumb, license, artist, title} 或 None"""
    d = api({
        "action": "query", "generator": "search",
        "gsrsearch": keyword, "gsrnamespace": 6, "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 480, "format": "json",
    })
    pages = (d.get("query") or {}).get("pages") or {}
    best = None
    for p in pages.values():
        title = p.get("title", "")
        if BAD_EXT.search(title) or BAD_TITLE.search(title):
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
    credits_file = OUT.parent / "credits.json"
    # 先读回已有署名再合并，否则跳过项会被 None 覆盖、抹掉 CC BY 的署名义务
    credits = {}
    if credits_file.exists():
        try:
            credits = json.loads(credits_file.read_text(encoding="utf-8")).get("credits") or {}
        except (ValueError, OSError):
            credits = {}
    fetched, skipped = 0, []
    for name, kw in MATERIALS.items():
        fp = OUT / f"{name}.jpg"
        if fp.exists() and not force:
            continue
        kws = kw if isinstance(kw, (list, tuple)) else [kw]
        try:
            info = None
            for k in kws:
                info = pick_image(k)
                if info:
                    break
            if not info:
                skipped.append(name)
                print(f"× {name}: 无合适许可图片")
                continue
            data = None
            for attempt in range(3):
                try:
                    req = urllib.request.Request(info["thumb"], headers=UA)
                    data = urllib.request.urlopen(req, timeout=40).read()
                    break
                except Exception as de:
                    if attempt == 2:
                        raise de
                    time.sleep(3 * (attempt + 1))
            # 统一转成真 JPEG：Commons 的 "缩略图" 对 PNG 原图仍返回 PNG
            # （实测 丁香/桔梗/白糖/雪梨 四张是 PNG 存成 .jpg，体积 90-330KB）。
            # 浏览器虽能显示，但格式名与内容不符、体积也大 3-8 倍。
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(data))
                if im.mode != "RGB":
                    im = im.convert("RGB")
                if im.width > 480:
                    im.thumbnail((480, 480), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=85, optimize=True)
                data = buf.getvalue()
            except Exception:
                pass  # 无 PIL 或解码失败时按原字节写入（前端仍能显示）
            fp.write_bytes(data)
            credits[name] = {k: info[k] for k in ("license", "artist", "title")}
            fetched += 1
            print(f"✓ {name}: {info['license']} ({len(data)//1024}KB) {info['artist'][:24]}")
            time.sleep(1.2)  # 礼貌限速：0.4s 实测会触发 429
        except Exception as e:
            skipped.append(name)
            print(f"× {name}: {str(e)[:60]}")

    credits_file.write_text(
        json.dumps({"source": "Wikimedia Commons", "credits": credits}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n拉取 {fetched} 张 | 跳过 {len(skipped)} 个: {'、'.join(skipped) or '无'}")
    print(f"输出: {OUT} | 许可记录: {credits_file}")


if __name__ == "__main__":
    main("--force" in sys.argv)
