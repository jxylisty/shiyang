# -*- coding: utf-8 -*-
"""批次4落盘：健康报协和15方中合规10方+新华网杏梨润肺茶+人民网名中医茶；人民网七款安眠汤中合规7方+新华网酸枣仁百合汤"""
import json
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "recipes_raw"

def M(name, kind, grams=None, optional=False, note=""):
    return {"name": name, "kind": kind, "grams": grams, "optional": optional, "note": note}

XH = "中国医学科学院北京协和医院中医科（健康报《中式养生水，你喝对了吗》）"
XH_URL = "https://www.jkb.com.cn/TCM/2025/0328/501880.html"
RM7 = "人民网健康《睡眠不好 推荐七款安眠汤》（原源：家庭医生在线）"
RM7_URL = "http://health.people.com.cn/n1/2016/0629/c21471-28506404.html"
XHWW = "新华网转载《羊城晚报》（广东省第二中医院心血管科黄琳主任医师）"
XHWW_URL = "http://www.news.cn/health/20211103/c10883df0a934f39aaa9be56742b8b64/c.html"

TEA_ADD = [
    {"name": "陈皮蜂蜜柚子茶", "type": "茶饮", "oneliner": "理气化痰、清热润肠的果味茶参考",
     "description": "陈皮理气化痰，柚子清香润燥，配绿茶与蜂蜜；口感温和的日常理气茶。",
     "method": "陈皮、柚子肉与绿茶同泡，稍加蜂蜜调饮", "duration": "冲泡", "scenes": ["消化"],
     "constitutions_suitable": ["气郁", "痰湿"], "constitutions_unsuitable": [],
     "population": "餐后腹胀、痰多人群",
     "contraindication": "蜂蜜不耐高温，待温后加入；糖尿病人群少放蜂蜜",
     "source": XH, "reference_url": XH_URL, "status": "待核对",
     "materials": [M("陈皮", "药食同源", None, note="原文未标克数"), M("柚子", "普通食物", None, note="原文未标克数"), M("绿茶", "茶叶", None, note="原文未标克数"), M("蜂蜜", "药食同源", None, optional=True, note="少许调味")]},
    {"name": "协和补气茶", "type": "茶饮", "oneliner": "气虚人群的基础补气茶参考",
     "description": "黄芪补气升阳固表，配党参增强补气之力；适合乏力倦怠、易感冒的气虚人群。",
     "method": "煮茶或冲泡饮用", "duration": "煮泡", "scenes": ["换季调理"],
     "constitutions_suitable": ["气虚"], "constitutions_unsuitable": ["湿热"],
     "population": "乏力倦怠、虚汗多、怕风易感冒人群",
     "contraindication": "感冒发热期不宜；湿热壅盛者不宜",
     "source": XH + "（气虚证补气茶）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("黄芪", "药食同源", 12, note="原文10-15克取中值"), M("党参", "药食同源", 8, note="原文'参类6-10克'，取党参")]},
    {"name": "协和养血茶", "type": "茶饮", "oneliner": "血虚人群的气血双补茶参考",
     "description": "当归补血活血，龙眼肉养心血，大枣补中益气，黄芪益气生血；适合面色萎黄、头晕心悸人群。",
     "method": "代茶饮", "duration": "冲泡", "scenes": ["经期温养"],
     "constitutions_suitable": ["血瘀", "气虚"], "constitutions_unsuitable": ["湿热"],
     "population": "面色萎黄或苍白、头晕心悸、手足发麻人群",
     "contraindication": "感冒发热期不宜；孕妇咨询医师后使用",
     "source": XH + "（血虚证养血茶）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("大枣", "药食同源", 6), M("当归", "药食同源", 6), M("龙眼肉", "药食同源", 6, note="成分数据待补"), M("黄芪", "药食同源", 6)]},
    {"name": "山楂决明轻身饮", "type": "茶饮", "oneliner": "祛痰湿助消化的轻养基础方（仅录原文基础方）",
     "description": "山楂消食化积，决明子润肠清肝，陈皮理气；超重与代谢偏弱人群的代茶基础方，需配合运动。",
     "method": "代茶饮", "duration": "冲泡", "scenes": ["控糖轻养"],
     "constitutions_suitable": ["痰湿", "湿热"], "constitutions_unsuitable": [],
     "population": "超重、代谢偏慢、饮食油腻人群（配合锻炼）",
     "contraindication": "孕妇慎用；脾胃虚寒便溏者不宜；不能替代减重治疗",
     "source": XH + "（减脂代茶饮基础方；原文番泻叶加减项因安全性未收录）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("山楂", "药食同源", 10, note="原文生山楂"), M("决明子", "药食同源", 10, note="成分数据待补"), M("陈皮", "药食同源", 10)]},
    {"name": "滋阴生津润燥茶", "type": "茶饮", "oneliner": "阴虚口干人群的自选搭配润燥茶",
     "description": "麦冬、石斛养阴生津，芦根清热除烦；阴虚证口干、皮肤干燥、手足心热人群的轻养茶（原文为五味可选项，此处取目录内三味基础组方）。",
     "method": "冲泡或煎煮，代茶饮", "duration": "冲泡", "scenes": ["护嗓润喉"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "口干口渴、皮肤干燥、手足心热、夜间多汗人群",
     "contraindication": "脾胃虚寒便溏者不宜",
     "source": XH + "（阴虚润燥茶）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("麦冬", "药食同源", 8), M("石斛", "药食同源", 8), M("芦根", "药食同源", 8), M("胖大海", "药食同源", None, optional=True, note="原文：咽喉不适音哑者加")]},
    {"name": "温阳暖身茶", "type": "茶饮", "oneliner": "阳虚怕冷人群的温中助阳茶参考",
     "description": "肉桂温阳散寒，生姜温中止呕，龙眼肉、大枣补养气血；适合怕冷、手足冰凉、易腹泻的阳虚人群。",
     "method": "调配煮茶温服", "duration": "煮茶", "scenes": ["经期温养", "换季调理"],
     "constitutions_suitable": ["阳虚"], "constitutions_unsuitable": ["阴虚", "湿热"],
     "population": "怕冷、手足冰凉、易腹泻人群",
     "contraindication": "阴虚火旺者不宜；感冒发热期不宜；孕妇咨询医师后使用",
     "source": XH + "（阳虚温阳茶）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("龙眼肉", "药食同源", None, note="原文未标克数；成分数据待补"), M("肉桂", "药食同源", None, note="原文未标克数"), M("生姜", "药食同源", None, note="原文未标克数"), M("大枣", "药食同源", None, note="原文未标克数")]},
    {"name": "黄精桑椹固本茶", "type": "茶饮", "oneliner": "中老年补肾填精的轻养茶参考",
     "description": "黄精滋肾润脾，桑椹滋阴补血，覆盆子固肾缩尿；原文为五子类可选项，此处取目录内三味（菟丝子、沙苑子目录外未收录）。",
     "method": "煎煮或冲泡", "duration": "煎煮", "scenes": ["换季调理"],
     "constitutions_suitable": ["阴虚", "气虚"], "constitutions_unsuitable": ["痰湿"],
     "population": "腰腿酸痛、耳鸣、记忆力下降的中老年人群",
     "contraindication": "痰湿壅盛者不宜；腹泻者慎用",
     "source": XH + "（老年补肾茶可选目录内三味）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("黄精", "药食同源", 8), M("桑椹", "药食同源", 8), M("覆盆子", "药食同源", 8, note="成分数据待补")]},
    {"name": "春季桑叶疏风饮", "type": "茶饮", "oneliner": "清肝明目疏风的春季轻养茶",
     "description": "桑叶清肝明目、疏风；春季肝气偏旺、情绪急躁人群的简单茶方，脾虚者可加西洋参或大枣。",
     "method": "泡水饮服", "duration": "冲泡", "scenes": ["控糖轻养", "情绪舒压"],
     "constitutions_suitable": [], "constitutions_unsuitable": [],
     "population": "春季情绪急躁、用眼多人群",
     "contraindication": "脾胃虚寒者加西洋参同泡；孕期慎用",
     "source": XH + "（春季桑叶饮）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("桑叶", "药食同源", 4, note="原文3-5克取中值"), M("西洋参", "药食同源", 4, optional=True, note="原文：脾虚者加")]},
    {"name": "雪梨百合果茶", "type": "茶饮", "oneliner": "养阴润燥的秋季煮果茶",
     "description": "雪梨生津润燥，百合养阴清心，配海棠果煮茶；秋季干咳、咽干人群的温和果茶。",
     "method": "煮制果茶", "duration": "煮茶", "scenes": ["护嗓润喉", "换季调理"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": [],
     "population": "秋季咽干、易干咳人群",
     "contraindication": "脾胃虚寒便溏者少饮；糖尿病人群注意冰糖",
     "source": XH + "（秋季雪梨果茶）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("雪梨", "普通食物", None, note="原文未标克数"), M("百合", "药食同源", None, note="原文未标克数"), M("海棠果", "普通食物", None, note="原文'海棠'未标克数")]},
    {"name": "麦冬马蹄生津水", "type": "茶饮", "oneliner": "润肺生津的秋季煮水",
     "description": "麦冬养阴生津，马蹄（荸荠）清热生津；口鼻干燥人群的简单煮水。",
     "method": "麦冬与去皮马蹄煮水，加少许冰糖", "duration": "煮水", "scenes": ["护嗓润喉"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "秋季口鼻干燥人群",
     "contraindication": "脾胃虚寒者不宜多饮",
     "source": XH + "（秋季麦冬马蹄水）", "reference_url": XH_URL, "status": "待核对",
     "materials": [M("麦冬", "药食同源", 12, note="原文10-15克取中值"), M("马蹄", "普通食物", 200), M("冰糖", "普通食物", None, optional=True, note="少许")]},
    {"name": "杏梨润肺茶", "type": "茶饮", "oneliner": "生津润肺的秋冬煮茶",
     "description": "鸭梨生津润燥，甜杏仁润肺止咳，百合养阴清心；秋冬咽干轻咳人群的经典煮茶。",
     "method": "鸭梨切块与甜杏仁、百合加水煮沸后转小火慢炖20分钟，代茶饮", "duration": "炖20分钟", "scenes": ["护嗓润喉"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
     "population": "秋冬咽干、轻咳无痰人群",
     "contraindication": "杏仁须用甜杏仁并熟制；脾胃虚寒便溏者少饮",
     "source": "新华网《杏梨润肺茶》（中医推荐）", "reference_url": "http://www.xj.xinhuanet.com", "status": "待核对",
     "materials": [M("雪梨", "普通食物", 250, note="原文鸭梨1个"), M("苦杏仁", "药食同源", 10, note="原文甜杏仁10克（甜杏仁为本库'杏仁'条目）"), M("百合", "药食同源", 15)]},
    {"name": "菊杞桂圆滋补茶", "type": "茶饮", "oneliner": "名中医推荐的冬季滋补茶",
     "description": "菊花清肝明目，枸杞子滋补肝肾，桂圆养血安神，大枣补中益气；四味各10克的平和冬季滋补方。",
     "method": "开水冲泡代茶饮", "duration": "冲泡", "scenes": ["换季调理", "熬夜护眼"],
     "constitutions_suitable": ["平和", "气虚"], "constitutions_unsuitable": ["湿热"],
     "population": "冬季日常滋补、早白发、头晕目眩人群",
     "contraindication": "湿热内盛、糖尿病人群慎用桂圆大枣",
     "source": "人民网健康《名中医的冬季养生茶》", "reference_url": "http://health.people.com.cn/n1/2016/1218/c14739-28957737.html", "status": "待核对",
     "materials": [M("菊花", "药食同源", 10), M("枸杞子", "药食同源", 10), M("龙眼肉", "药食同源", 10, note="成分数据待补"), M("大枣", "药食同源", 10, note="原文红枣，按10克约2枚计")]},
]

DIET_ADD = [
    {"name": "桂圆莲子宁神汤", "type": "药膳", "oneliner": "养心宁神健脾的经典安眠甜汤",
     "description": "龙眼肉补益心脾、养血安神，莲子补心益脾、补肾固精；中老年人及长期失眠人群的经典甜汤。",
     "method": "桂圆与莲子煮成汤", "duration": "煮汤", "scenes": ["助眠"],
     "constitutions_suitable": ["气虚", "平和"], "constitutions_unsuitable": ["湿热"],
     "population": "中老年人、长期失眠多梦人群",
     "contraindication": "糖尿病人群注意加糖量；湿热内盛者不宜",
     "source": RM7 + "（桂圆莲子汤）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("龙眼肉", "药食同源", None, note="原文'二两'，产地计量口径不一未换算；成分数据待补"), M("莲子", "药食同源", None, note="原文'二两'未换算；成分数据待补")]},
    {"name": "百合鸡蛋安神汤", "type": "药膳", "oneliner": "清心安神的睡前蛋汤",
     "description": "百合清心润肺安神，鸡蛋滋阴养血；睡前一小时饮用的温和安神汤。",
     "method": "生百合蒸熟，加入蛋黄一个，以200毫升水搅匀，加少许冰糖煮沸后再以50毫升水搅匀，睡前一小时饮用", "duration": "蒸煮", "scenes": ["助眠"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": [],
     "population": "虚烦惊悸、入睡困难人群",
     "contraindication": "对鸡蛋过敏者禁用；睡前适量",
     "source": RM7 + "（安神汤）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("百合", "药食同源", 15, note="原文五钱约15克"), M("鸡蛋", "普通食物", 50, note="原文一个蛋黄"), M("冰糖", "普通食物", None, optional=True, note="少许")]},
    {"name": "百合绿豆清心乳", "type": "药膳", "oneliner": "夏夜清心除烦的安神甜汤",
     "description": "百合清心安神，绿豆清热除烦，牛奶助眠；夏季烦热难眠人群的经典甜汤。",
     "method": "百合、绿豆煮熟烂，服时加牛奶与少量冰糖", "duration": "煮汤", "scenes": ["助眠"],
     "constitutions_suitable": ["阴虚", "湿热"], "constitutions_unsuitable": ["阳虚"],
     "population": "夏季心烦睡不着的人群",
     "contraindication": "脾胃虚寒者不宜冰镇饮用；乳糖不耐者少加牛奶",
     "source": RM7 + "（百合绿豆乳）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("百合", "药食同源", 25), M("绿豆", "普通食物", 25), M("牛奶", "普通食物", 200, note="原文'加些牛奶'"), M("冰糖", "普通食物", None, optional=True, note="少量")]},
    {"name": "莲子煨瘦肉汤", "type": "药膳", "oneliner": "补心益脾的失眠食养汤",
     "description": "莲子补心益脾养血安神，瘦猪肉滋阴润燥；适合失眠伴气短乏力人群。",
     "method": "瘦猪肉片与莲子肉加水共煨炖至熟，调味服食", "duration": "煨炖", "scenes": ["助眠"],
     "constitutions_suitable": ["气虚", "阴虚"], "constitutions_unsuitable": [],
     "population": "失眠、气短乏力人群",
     "contraindication": "便秘腹胀者少食",
     "source": RM7 + "（莲子煨瘦肉，'五种食物'篇）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("猪瘦肉", "普通食物", 250), M("莲子", "药食同源", 50, note="成分数据待补")]},
    {"name": "百合安神粥", "type": "药膳", "oneliner": "清心安神的早晚养生粥",
     "description": "百合润肺清心，大米养胃；神经衰弱、更年期心悸失眠人群的早晚粥方。",
     "method": "百合清水浸泡半天去苦味，与大米共煮至粥成，加冰糖适量，早晚各服1次", "duration": "煮粥", "scenes": ["助眠"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": [],
     "population": "神经衰弱、更年期心悸失眠人群",
     "contraindication": "糖尿病人群注意冰糖",
     "source": RM7 + "（百合粥，'五种食物'篇）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("百合", "药食同源", 30), M("粳米", "普通食物", 100, note="原文大米"), M("冰糖", "普通食物", None, optional=True, note="适量")]},
    {"name": "桂圆花生鱼头汤", "type": "药膳", "oneliner": "心脾两虚人群的养血安神鱼汤",
     "description": "龙眼肉补益心脾养血安神，花生健脾养胃，鱼头补虚；心脾两虚、失眠多梦人群的食养汤。",
     "method": "花生浸泡1小时；姜片煎鱼头至微黄，冲入热水旺火煮5分钟；全部材料入锅炖约2.5小时", "duration": "炖2.5小时", "scenes": ["助眠", "经期温养"],
     "constitutions_suitable": ["气虚", "平和"], "constitutions_unsuitable": ["湿热"],
     "population": "心脾两虚、失眠多梦、健忘人群",
     "contraindication": "对鱼类过敏者禁用；痛风患者慎食鱼汤",
     "source": RM7 + "（桂圆花生鱼头汤，'五种食物'篇）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("鲢鱼头", "普通食物", 700, note="原文草鱼头700克"), M("花生", "普通食物", 30), M("龙眼肉", "药食同源", 20, note="成分数据待补"), M("大枣", "药食同源", 36, note="原文12个"), M("生姜", "药食同源", None, note="原文姜片适量")]},
    {"name": "核桃黑芝麻糊", "type": "药膳", "oneliner": "神经衰弱人群的健脑安神糊",
     "description": "核桃仁补肾健脑，黑芝麻滋补肝肾；心悸失眠、健忘人群的经典搭配。",
     "method": "核桃仁、黑芝麻炒熟研末，加白糖混匀，日服1次每服约10克", "duration": "研末冲服", "scenes": ["助眠", "熬夜护眼"],
     "constitutions_suitable": ["阴虚", "平和"], "constitutions_unsuitable": ["痰湿"],
     "population": "心悸失眠、健忘、脑力消耗大人群",
     "contraindication": "便溏腹泻者少食；糖尿病人群注意白糖",
     "source": RM7 + "（核桃黑芝麻，'五种食物'篇）", "reference_url": RM7_URL, "status": "待核对",
     "materials": [M("核桃", "普通食物", 50), M("黑芝麻", "药食同源", 50, note="成分数据待补"), M("白糖", "普通食物", 15, note="混匀后每服约10克")]},
    {"name": "酸枣仁百合瘦肉汤", "type": "药膳", "oneliner": "清热除烦的助眠瘦肉汤",
     "description": "酸枣仁养心安神，百合清心润肺；虚烦不眠人群的清润汤方。",
     "method": "枣仁洗净加水300毫升小火煮30分钟去渣取汁，再加百合与瘦肉同煮30分钟，调味喝汤吃肉", "duration": "煮1小时", "scenes": ["助眠"],
     "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": [],
     "population": "虚烦不眠、心神不宁人群",
     "contraindication": "严重失眠应就诊；风寒咳嗽者少食",
     "source": XHWW + "（酸枣仁百合汤）", "reference_url": XHWW_URL, "status": "待核对",
     "materials": [M("酸枣仁", "药食同源", 30), M("百合", "药食同源", 30), M("猪瘦肉", "普通食物", 50)]},
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

# 修正：杏梨润肺茶 reference_url 为站点首页占位，标注待补
fp = RAW / "tea.json"
data = json.loads(fp.read_text(encoding="utf-8"))
for r in data["recipes"]:
    if r["name"] == "杏梨润肺茶":
        r["reference_url"] = ""
        r["source"] += "；具体文章链接待补录（来源见新华网健康频道搜索'杏梨润肺茶'）"
fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("已修正杏梨润肺茶来源标注")
