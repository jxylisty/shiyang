# -*- coding: utf-8 -*-
"""批次3落盘：深圳卫健委四季茶疗+人民日报海外版四季茶+宁夏医科大学+健康报；修正港中大粥来源"""
import json
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "recipes_raw"

def M(name, kind, grams=None, optional=False, note=""):
    return {"name": name, "kind": kind, "grams": grams, "optional": optional, "note": note}

SZ = "深圳市中医院黄淑芬（深圳市卫健委'四季药膳茶疗'）"
SZ_URL = "http://wjw.sz.gov.cn/ztzl/jkkp/jkcs/content/post_11116470.html"
RM = "《人民日报海外版》2018-02-03（北京朝阳区中医医院王红蕊）"
RM_URL = "http://paper.people.com.cn/rmrbhwb/html/2018-02/03/content_1834580.htm"

TEA_ADD = [
    {"name": "黄芪芡实杞菊茶", "type": "茶饮",
     "oneliner": "春季轻养的经典四味茶参考",
     "description": "黄芪补气固表，芡实健脾固肾，枸杞子滋补肝肾，菊花清肝明目；深圳市中医院推荐的春季茶疗方。",
     "method": "材料浸泡30分钟，连水入养生壶煲20-30分钟（1-2人份）", "duration": "煲20-30分钟", "scenes": ["换季调理", "熬夜护眼"],
     "constitutions_suitable": ["气虚", "平和"], "constitutions_unsuitable": ["湿热"],
     "population": "换季易感、日常轻养人群",
     "contraindication": "感冒发热期不宜；湿热壅盛者慎用黄芪",
     "source": SZ + "（春季方）", "reference_url": SZ_URL, "status": "待核对",
     "materials": [M("黄芪", "药食同源", 17, note="原文15-20克取中值"), M("芡实", "药食同源", 12, note="原文10-15克取中值；成分数据待补"), M("枸杞子", "药食同源", 10), M("菊花", "药食同源", 10)]},
    {"name": "黄芪玫瑰开郁茶", "type": "茶饮",
     "oneliner": "疏肝解郁的春季情绪舒压茶参考",
     "description": "黄芪健脾补中，玫瑰花行气解郁，陈皮理气，枸杞子养肝；适合春困情绪低落、压力大人群。",
     "method": "代茶饮，沸水冲泡", "duration": "冲泡", "scenes": ["情绪舒压"],
     "constitutions_suitable": ["气郁", "气虚"], "constitutions_unsuitable": ["阴虚"],
     "population": "压力大、情绪压抑的职场人群",
     "contraindication": "月经量多者经期暂停玫瑰花；阴虚火旺者慎用黄芪",
     "source": RM + "（春季方）", "reference_url": RM_URL, "status": "待核对",
     "materials": [M("黄芪", "药食同源", None, note="原文未标克数"), M("玫瑰花", "普通食物", None, note="非目录内花材，民间食养常用"), M("陈皮", "药食同源", None, note="原文未标克数"), M("枸杞子", "药食同源", None, note="原文'枸杞'未标克数")]},
    {"name": "山楂荷叶轻暑饮", "type": "茶饮",
     "oneliner": "清热解暑利湿的夏日茶参考",
     "description": "山楂消食化滞，荷叶清暑利湿，薏苡仁清暑健脾；夏日暑湿重的轻养搭配。",
     "method": "代茶饮，沸水冲泡或煮饮", "duration": "冲泡", "scenes": ["控糖轻养", "消化"],
     "constitutions_suitable": ["痰湿", "湿热"], "constitutions_unsuitable": [],
     "population": "夏季暑湿、饮食油腻人群",
     "contraindication": "孕妇慎用薏苡仁、山楂；脾胃虚寒者不宜",
     "source": RM + "（夏季方，山楂荷叶饮）", "reference_url": RM_URL, "status": "待核对",
     "materials": [M("山楂", "药食同源", None, note="原文未标克数"), M("荷叶", "药食同源", None, note="原文未标克数；成分数据待补"), M("薏苡仁", "药食同源", None, note="原文'薏仁米'未标克数")]},
    {"name": "百合麦冬润燥饮", "type": "茶饮",
     "oneliner": "清热润燥的秋季轻养茶参考",
     "description": "百合养阴润肺清心，麦冬益胃生津除烦，菊花清解余热；秋季防燥的平和搭配。",
     "method": "代茶饮，沸水冲泡", "duration": "冲泡", "scenes": ["护嗓润喉", "换季调理"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "秋季咽干、熬夜上火的上班族",
     "contraindication": "脾胃虚寒便溏者不宜",
     "source": RM + "（秋季方，百合麦冬饮）", "reference_url": RM_URL, "status": "待核对",
     "materials": [M("百合", "药食同源", None, note="原文未标克数"), M("麦冬", "药食同源", None, note="原文未标克数"), M("菊花", "药食同源", None, note="原文'少许'未标克数")]},
    {"name": "姜枣桂圆陈皮茶", "type": "茶饮",
     "oneliner": "温经养胃驱寒的冬季暖茶参考",
     "description": "生姜温中散寒，龙眼肉补心血，大枣补中益气，陈皮理气防滞；四味性温，寒冬暖身。",
     "method": "代茶饮，沸水冲泡或煮饮", "duration": "冲泡", "scenes": ["经期温养", "换季调理"],
     "constitutions_suitable": ["阳虚", "气虚"], "constitutions_unsuitable": ["湿热", "阴虚"],
     "population": "畏寒、手脚偏凉人群冬季日常",
     "contraindication": "阴虚火旺、湿热内盛者不宜；感冒发热期不宜",
     "source": RM + "（冬季方）", "reference_url": RM_URL, "status": "待核对",
     "materials": [M("生姜", "药食同源", None, note="原文未标克数"), M("龙眼肉", "药食同源", None, note="原文'桂圆'未标克数；成分数据待补"), M("大枣", "药食同源", None, note="原文未标克数"), M("陈皮", "药食同源", None, note="原文未标克数")]},
    {"name": "洋参菊花轻养茶", "type": "茶饮",
     "oneliner": "补气养阴清热的日常轻养茶",
     "description": "西洋参补气养阴、清热生津，配菊花清肝明目；适合疲劳咽干的气阴两虚人群。",
     "method": "沸水冲泡，可加冰糖适量", "duration": "冲泡", "scenes": ["换季调理", "熬夜护眼"],
     "constitutions_suitable": ["气虚", "阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "疲劳、咽干、用眼多人群",
     "contraindication": "脾胃虚寒者不宜；不宜与藜芦同用",
     "source": "宁夏医科大学中医学院养生科普", "reference_url": "http://www.nxmu.edu.cn/nxykdxhuiyizhongyi/info/1048/1493.htm", "status": "待核对",
     "materials": [M("西洋参", "药食同源", 6), M("菊花", "药食同源", None, note="原文5朵"), M("冰糖", "普通食物", None, optional=True, note="适量")]},
    {"name": "古法酸梅茶", "type": "茶饮",
     "oneliner": "生津解渴的经典酸梅汤配方（健康报剂量版）",
     "description": "乌梅生津敛阴，山楂消食，陈皮理气，甘草调和；即传统酸梅汤，夏季冰镇风味更佳。",
     "method": "煮水代茶，加冰糖适量", "duration": "煮水", "scenes": ["消化"],
     "constitutions_suitable": [], "constitutions_unsuitable": [],
     "population": "夏季口干、食欲不振人群",
     "contraindication": "胃酸过多者不宜；感冒发热期不宜",
     "source": "健康报《中式养生水，你喝对了吗》酸梅茶剂量", "reference_url": "https://www.jkb.com.cn/TCM/2025/0328/501880.html", "status": "待核对",
     "materials": [M("乌梅", "药食同源", 35, note="原文30-40克取中值"), M("山楂", "药食同源", 15, note="原文10-20克取中值"), M("陈皮", "药食同源", 15, note="原文10-20克取中值"), M("甘草", "药食同源", 4.5, note="原文3-6克取中值"), M("冰糖", "普通食物", None, optional=True, note="适量")]},
]

DIET_ADD = [
    {"name": "冬瓜薏苡仁陈皮鸭汤", "type": "药膳",
     "oneliner": "滋阴养胃、健脾利水的夏季祛暑汤",
     "description": "薏苡仁健脾利湿，冬瓜清热祛暑，鸭肉滋阴，陈皮理气；深圳市中医院推荐的夏季汤方（3-4人份）。",
     "method": "薏苡仁浸泡半小时；全部材料入砂锅大火煲开转小火1.5小时，加盐调味", "duration": "煲1.5小时", "scenes": ["换季调理"],
     "constitutions_suitable": ["痰湿", "阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "夏季暑湿、身体困重人群",
     "contraindication": "孕妇不建议饮用（原文：薏苡仁性凉）",
     "source": SZ + "（夏季方）", "reference_url": SZ_URL, "status": "待核对",
     "materials": [M("薏苡仁", "药食同源", 50), M("冬瓜", "普通食物", 500), M("陈皮", "药食同源", 6, note="原文5-8克取中值"), M("鸭肉", "普通食物", 500), M("生姜", "药食同源", 6, note="原文2片"), M("蜜枣", "普通食物", 15, note="原文1颗")]},
]

for fname, adds in (("tea.json", TEA_ADD), ("diet.json", DIET_ADD)):
    fp = RAW / fname
    data = json.loads(fp.read_text(encoding="utf-8"))
    existing = {r["name"] for r in data["recipes"]}
    added = 0
    for r in adds:
        if r["name"] not in existing:
            data["recipes"].append(r)
            added += 1
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{fname}: +{added}，现共 {len(data['recipes'])} 条")

# 修正：玫瑰茯苓养颜粥 的来源 URL 原为占位，改为待补
fp = RAW / "diet.json"
data = json.loads(fp.read_text(encoding="utf-8"))
for r in data["recipes"]:
    if r["name"] == "玫瑰茯苓养颜粥":
        r["reference_url"] = ""
        r["source"] = "香港中文大学中医学院专栏推荐（华何与博士）转引；具体文章链接待补录"
fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("已修正玫瑰茯苓养颜粥来源标注")
