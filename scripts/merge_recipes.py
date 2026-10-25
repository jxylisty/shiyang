# -*- coding: utf-8 -*-
"""
校验并合并采集到的方子数据 → data/recipes_v0.1.json + docs/方子库_v0.1.xlsx
规则：食材白名单校验、别名归一到库内药材名、体质/场景合法性、来源完整性
用法：python -X utf8 merge_recipes.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "recipes_raw"
CATALOG = json.loads((ROOT / "data" / "food_homology_catalog.json").read_text(encoding="utf-8"))

# ---- 库内已覆盖药材（74 种目录物质命中的 82 味药材，含 0 化合物的花椒/橘红标低） ----
COVERED = {h: True for h in [
    "生姜", "干姜", "黄精", "桃仁", "莱菔子", "化橘红", "地黄", "熟地黄", "佛手", "苦杏仁",
    "桔梗", "陈皮", "百合", "昆布", "香橼", "小茴香", "木瓜", "肉豆蔻", "大枣", "金银花",
    "鱼腥草", "胖大海", "桑叶", "菊花", "芥子", "紫苏子", "葛根", "芦根", "当归", "西红花",
    "山茱萸", "麦冬", "天冬", "马齿苋", "火麻仁", "甘草", "鸡内金", "郁李仁", "茯苓", "淡豆豉",
    "酸枣仁", "石斛", "天麻", "白芷", "肉桂", "枸杞子", "益智", "淡竹叶", "槐花", "蜂蜜",
    "广藿香", "草果", "党参", "丁香", "山药", "阿胶", "桑椹", "高良姜", "蒲公英", "姜黄",
    "肉苁蓉", "黄芪", "杜仲", "山楂", "乌梅", "玉竹", "牡蛎", "麦芽", "栀子", "紫苏叶",
    "白茅根", "薄荷", "薏苡仁", "西洋参",
]}
COVERED["花椒"] = False   # 库里有但 0 化合物
COVERED["橘红"] = False

# ---- 目录名/异名 → 库内药材名 归一映射 ----
CANONICAL = {
    "橘皮": "陈皮", "枣": "大枣", "红枣": "大枣", "黑枣": "大枣", "酸枣": "大枣",
    "枸杞": "枸杞子", "益智仁": "益智", "杜仲叶": "杜仲", "铁皮石斛": "石斛",
    "藿香": "广藿香", "黄芥子": "芥子", "芥子": "芥子", "紫苏籽": "紫苏子", "苏子": "紫苏子",
    "紫苏": "紫苏叶", "鲜芦根": "芦根", "鲜白茅根": "白茅根", "薏米": "薏苡仁",
    "桑葚": "桑椹", "桂圆": "龙眼肉", "西红花": "西红花", "藏红花": "西红花",
    "山奈": "山柰", "肉苁蓉（荒漠）": "肉苁蓉", "麦门冬": "麦冬", "天门冬": "天冬",
    "生地黄": "地黄", "白果": "白果", "银杏": "白果", "杭菊": "菊花", "贡菊": "菊花",
    "忍冬": "金银花", "八角": "八角茴香", "大茴香": "八角茴香", "橄榄": "青果",
    "胡麻": "黑芝麻", "鸡头米": "芡实", "红小豆": "赤小豆", "拐枣": "枳椇子",
    "陈皮": "陈皮", "生姜": "生姜", "干姜": "干姜", "蜂蜜": "蜂蜜", "蜜": "蜂蜜",
}
DIRECTORY_NAMES = {it["name"]: True for it in CATALOG["items"]}
for it in CATALOG["items"]:
    for a in it["aliases"]:
        CANONICAL.setdefault(a, it["name"])

NINE = ["平和", "气虚", "阳虚", "阴虚", "痰湿", "湿热", "血瘀", "气郁", "特禀"]
SCENES = ["护嗓润喉", "熬夜护眼", "换季调理", "助眠", "消化", "控糖轻养",
          "控油祛痘", "久坐通气", "情绪舒压", "经期温养"]
BANNED_WORDS = ["治疗", "疗效", "治愈", "抗癌", "降血糖", "降血压", "降血脂"]
TEAS = {"绿茶", "红茶", "普洱茶", "乌龙茶", "白茶", "茉莉花茶", "黑茶", "花茶"}

problems, recipes = [], []

def check_constitution(r, field):
    for c in r.get(field, []):
        if c not in NINE:
            problems.append(f"[{r['name']}] {field} 非法体质值: {c}")

def process(fp):
    if not fp.exists():
        problems.append(f"缺少采集文件: {fp.name}")
        return
    data = json.loads(fp.read_text(encoding="utf-8"))
    for r in data.get("recipes", []):
        # 必填字段
        for k in ["name", "type", "oneliner", "method", "contraindication", "source", "reference_url", "materials"]:
            if not r.get(k):
                problems.append(f"[{r.get('name','?')}] 缺必填字段 {k}")
                break
        # 名称去重
        if any(x["name"] == r["name"] for x in recipes):
            problems.append(f"重名方子: {r['name']}（{fp.stem}）")
            continue
        # 违禁词
        text = " ".join(str(r.get(k, "")) for k in ["oneliner", "description", "population"])
        for w in BANNED_WORDS:
            if w in text:
                problems.append(f"[{r['name']}] 含违禁词: {w}")
        check_constitution(r, "constitutions_suitable")
        check_constitution(r, "constitutions_unsuitable")
        # 场景
        for s in r.get("scenes", []):
            if s not in SCENES:
                problems.append(f"[{r['name']}] 新场景标签(需人工确认): {s}")
        # 食材白名单
        norm_mats, coverage = [], {"covered": 0, "directory_pending": 0, "food": 0, "tea": 0, "unknown": 0}
        for m in r["materials"]:
            name = CANONICAL.get(m["name"], m["name"])
            kind = m.get("kind", "")
            m = dict(m, name=name)
            if name in COVERED:
                m["kind"], m["analysis_ready"] = "药食同源", COVERED[name]
                coverage["covered"] += 1
            elif name in DIRECTORY_NAMES:
                m["kind"], m["analysis_ready"] = "药食同源", False
                m.setdefault("note", "")
                if "待补" not in m["note"]:
                    m["note"] = (m["note"] + "；" if m["note"] else "") + "成分数据待补"
                coverage["directory_pending"] += 1
            elif kind == "茶叶" or name in TEAS or name.endswith("茶"):
                m["kind"], m["analysis_ready"] = "茶叶", False
                coverage["tea"] += 1
            elif kind == "普通食物":
                m["analysis_ready"] = False
                coverage["food"] += 1
            else:
                coverage["unknown"] += 1
                problems.append(f"[{r['name']}] 白名单外食材: {m['name']} (kind={kind})")
            norm_mats.append(m)
        r["materials"] = norm_mats
        r["coverage"] = coverage
        r["status"] = "待核对"
        recipes.append(r)

process(RAW / "tea.json")
process(RAW / "diet.json")

# ---- 统计 ----
def pct(n, d):
    return f"{n}/{d} ({n/d*100:.0f}%)" if d else "-"

n_tea = sum(1 for r in recipes if r["type"] == "茶饮")
n_diet = sum(1 for r in recipes if r["type"] == "药膳")
full = [r for r in recipes if r["coverage"]["covered"] > 0 and r["coverage"]["unknown"] == 0
        and r["coverage"]["directory_pending"] == 0]
partial = [r for r in recipes if r["coverage"]["covered"] > 0 and (r["coverage"]["directory_pending"] or r["coverage"]["unknown"])]
scene_dist = {}
for r in recipes:
    for s in r["scenes"]:
        scene_dist[s] = scene_dist.get(s, 0) + 1
throat = sum(1 for r in recipes if "护嗓润喉" in r["scenes"])

# ---- 输出合并 JSON ----
out = {"version": "0.1", "generated": datetime.now().isoformat(timespec="seconds"),
       "note": "子智能体采集 + 脚本校验，全部 status=待核对，需导师口径确认后翻状态",
       "problems": problems, "recipes": recipes}
(ROOT / "data" / "recipes_v0.1.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

# ---- 输出 Excel ----
wb = Workbook()
HEADER_FILL = PatternFill("solid", fgColor="2E7D5B")
HEADER_FONT = Font(color="FFFFFF", bold=True)
PENDING_FILL = PatternFill("solid", fgColor="FFF7E6")

ws = wb.active
ws.title = "方子表"
headers = ["方名", "类型", "一句话功效", "详细描述", "做法", "时长", "适宜体质", "不宜体质", "场景",
           "适用人群", "禁忌提示", "配料数", "成分库覆盖", "出处", "来源链接", "状态"]
for c, h in enumerate(headers, 1):
    cell = ws.cell(1, c, h)
    cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    cell.alignment = Alignment(horizontal="center")
for i, r in enumerate(recipes, 2):
    cov = r["coverage"]
    cov_text = "全覆盖" if r in full else ("部分覆盖" if r in partial else "营养素视角")
    vals = [r["name"], r["type"], r["oneliner"], r.get("description", ""), r["method"],
            r.get("duration", ""), "、".join(r.get("constitutions_suitable", [])),
            "、".join(r.get("constitutions_unsuitable", [])), "、".join(r["scenes"]),
            r.get("population", ""), r["contraindication"], len(r["materials"]), cov_text,
            r["source"], r["reference_url"], r["status"]]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(i, c, v)
        if c == 16:
            cell.fill = PENDING_FILL
for c, w in zip(range(1, len(headers) + 1),
                [18, 8, 26, 40, 36, 12, 16, 14, 16, 20, 26, 8, 10, 30, 40, 8]):
    ws.column_dimensions[get_column_letter(c)].width = w
ws.freeze_panes = "A2"

ws2 = wb.create_sheet("配料表")
h2 = ["方名", "食材名", "类型", "克数(g)", "是否可选", "成分分析就绪", "备注"]
for c, h in enumerate(h2, 1):
    cell = ws2.cell(1, c, h)
    cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    cell.alignment = Alignment(horizontal="center")
row = 2
for r in recipes:
    for m in r["materials"]:
        for c, v in enumerate([r["name"], m["name"], m["kind"], m.get("grams"),
                               "可选" if m.get("optional") else "必选",
                               "是" if m.get("analysis_ready") else "否",
                               m.get("note", "")], 1):
            ws2.cell(row, c, v)
        row += 1
for c, w in zip(range(1, len(h2) + 1), [20, 12, 12, 10, 10, 12, 30]):
    ws2.column_dimensions[get_column_letter(c)].width = w
ws2.freeze_panes = "A2"

ws3 = wb.create_sheet("校验报告")
ws3.cell(1, 1, f"共 {len(problems)} 条问题").font = Font(bold=True)
for i, p in enumerate(problems, 2):
    ws3.cell(i, 1, p)
ws3.column_dimensions["A"].width = 100

xlsx = ROOT / "docs" / "方子库_v0.1.xlsx"
wb.save(xlsx)

print(f"茶饮 {n_tea} + 药膳 {n_diet} = {len(recipes)} 方")
print(f"配料 100% 成分库覆盖: {pct(len(full), len(recipes))} | 部分覆盖: {len(partial)} | 仅营养素视角: {len(recipes)-len(full)-len(partial)}")
print(f"护嗓润喉专区: {throat} 方 | 场景分布: {scene_dist}")
print(f"校验问题 {len(problems)} 条（详见 Excel 校验报告 sheet）")
print(f"输出: data/recipes_v0.1.json | {xlsx}")
