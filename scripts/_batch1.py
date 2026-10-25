# -*- coding: utf-8 -*-
"""批次1落盘：主会话直接采集的茶饮10方 + 药膳5方（来源见各条 reference_url）"""
import json
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "recipes_raw"

def M(name, kind, grams=None, optional=False, note=""):
    return {"name": name, "kind": kind, "grams": grams, "optional": optional, "note": note}

TEA_ADD = [
    {   # 深圳市中医院 药膳食疗
        "name": "酸枣仁百合安睡茶", "type": "茶饮",
        "oneliner": "养心安神的睡前轻养茶参考",
        "description": "酸枣仁养肝宁心安神，百合清心润燥；中医常用于虚烦失眠、心悸多梦人群的食养参考。",
        "method": "酸枣仁捣碎，与百合先浸泡30分钟，养生壶水煎20分钟，睡前1-2小时温饮",
        "duration": "水煎20分钟", "scenes": ["助眠"],
        "constitutions_suitable": ["阴虚", "气虚"], "constitutions_unsuitable": [],
        "population": "入睡困难、多梦易醒人群",
        "contraindication": "孕妇及严重失眠者应就诊辨证；当晚忌浓茶咖啡",
        "source": "深圳市中医院药膳食疗科普《酸枣仁百合茶》", "reference_url": "https://www.szszyy.cn/HealthEducation3889/info.aspx?itemid=46483052&lcid=118",
        "status": "待核对",
        "materials": [M("酸枣仁", "药食同源", 20, note="原文：稍捣碎"), M("百合", "药食同源", 10), M("冰糖", "普通食物", None, optional=True, note="少量，按个人喜好")],
    },
    {   # 首都医科大学附属北京友谊医院 中医科
        "name": "清咽利喉饮", "type": "茶饮",
        "oneliner": "清热生津的利咽护嗓茶参考",
        "description": "金银花清热解毒，麦冬养阴生津，桔梗、甘草利咽，乌梅生津；适合用嗓过度、咽干咽痒人群。",
        "method": "药材过水去杂，带盖大口杯沸水冲泡焖10-30分钟，每日一剂多次泡服至无味",
        "duration": "焖泡10-30分钟", "scenes": ["护嗓润喉"],
        "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
        "population": "教师、主播等用嗓过度人群，咽干咽痒者",
        "contraindication": "脾胃虚寒易腹泻者慎用；咽喉肿痛持续应就诊",
        "source": "首都医科大学附属北京友谊医院中医科《常用代茶饮方药》（主治医师吴冬月）", "reference_url": "https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202307/t20230725_3206796.html",
        "status": "待核对",
        "materials": [M("金银花", "药食同源", 6), M("麦冬", "药食同源", 6), M("桔梗", "药食同源", 6), M("乌梅", "药食同源", 6), M("甘草", "药食同源", 3)],
    },
    {
        "name": "祛湿消肿饮", "type": "茶饮",
        "oneliner": "健脾祛湿的利水轻养茶参考",
        "description": "茯苓健脾渗湿，薏苡仁利水，荷叶升清降浊；适合身体困重、晨起面肿腿沉的痰湿人群。",
        "method": "药材过水，养生壶加500毫升水烧开后煎煮10-15分钟，代茶频饮",
        "duration": "煎煮10-15分钟", "scenes": ["消化"],
        "constitutions_suitable": ["痰湿"], "constitutions_unsuitable": ["阴虚"],
        "population": "湿气重、晨起困重浮肿人群",
        "contraindication": "孕妇慎用薏苡仁；阴虚津亏者不宜",
        "source": "首都医科大学附属北京友谊医院中医科《常用代茶饮方药》", "reference_url": "https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202307/t20230725_3206796.html",
        "status": "待核对",
        "materials": [M("茯苓", "药食同源", 10), M("薏苡仁", "药食同源", 20, note="原文：生薏米"), M("荷叶", "药食同源", 10, note="成分数据待补"), M("玉米须", "普通食物", 10, note="民间代茶食材，非目录内")],
    },
    {
        "name": "轻身消脂饮", "type": "茶饮",
        "oneliner": "利湿健脾的轻体茶参考（原方名：减肥降脂饮，表述已按合规调整）",
        "description": "荷叶升清化浊，山楂消食化积，陈皮理气健脾；适合饮食油腻、体重偏重人群的日常轻养参考。",
        "method": "药材过水，沸水冲泡焖10-30分钟或煎煮10-15分钟，代茶频饮",
        "duration": "焖泡10-30分钟", "scenes": ["控糖轻养"],
        "constitutions_suitable": ["痰湿"], "constitutions_unsuitable": [],
        "population": "饮食油腻、久坐少动、体重偏重人群",
        "contraindication": "孕妇慎用；脾胃虚寒者不宜长期饮；不能替代减重治疗",
        "source": "首都医科大学附属北京友谊医院中医科《常用代茶饮方药》（原方名'减肥降脂饮'）", "reference_url": "https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202307/t20230725_3206796.html",
        "status": "待核对",
        "materials": [M("荷叶", "药食同源", 10, note="成分数据待补"), M("山楂", "药食同源", 10, note="原文：生山楂"), M("陈皮", "药食同源", 10)],
    },
    # ---- 安徽省庐江县人民医院中医科 15款代茶饮（茶包形式，原文未公布克数）----
    {
        "name": "荷叶山楂利湿茶", "type": "茶饮",
        "oneliner": "健脾化湿利水的轻养茶参考",
        "description": "荷叶化湿升清，山楂消食化积，陈皮理气健脾，决明子润肠；适合脾虚湿盛人群。",
        "method": "茶包1袋沸水焖泡10分钟，可反复加水冲泡",
        "duration": "焖泡10分钟", "scenes": ["消化"],
        "constitutions_suitable": ["痰湿"], "constitutions_unsuitable": [],
        "population": "脾虚湿盛、身体困重人群",
        "contraindication": "脾胃虚寒者禁用（原文）；孕妇慎用",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("荷叶", "药食同源", None, note="原文茶包形式未标克数；成分数据待补"), M("山楂", "药食同源", None, note="原文未标克数"), M("陈皮", "药食同源", None, note="原文未标克数"), M("决明子", "药食同源", None, note="原文未标克数；成分数据待补")],
    },
    {
        "name": "玉竹石斛润肺茶", "type": "茶饮",
        "oneliner": "滋阴润肺的清润茶参考",
        "description": "玉竹养阴润燥，百合清心润肺，石斛益胃生津；适合长期接触尘雾、油烟环境人群的润养参考。",
        "method": "茶包1-2袋沸水焖泡10分钟，可反复冲泡",
        "duration": "焖泡10分钟", "scenes": ["护嗓润喉"],
        "constitutions_suitable": ["阴虚"], "constitutions_unsuitable": ["阳虚"],
        "population": "长期接触尘雾、油烟环境人群，咽干口燥者",
        "contraindication": "脾胃虚寒者禁用（原文）",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("玉竹", "药食同源", None, note="原文茶包形式未标克数"), M("百合", "药食同源", None, note="原文未标克数"), M("石斛", "药食同源", None, note="原文未标克数")],
    },
    {
        "name": "桑椹枸杞养发饮", "type": "茶饮",
        "oneliner": "滋补肝肾的头发养护茶参考",
        "description": "桑椹滋阴补血，枸杞子滋补肝肾；中医认为发为血之余、肾其华在发，适合头发早白稀疏人群的日常滋养参考。",
        "method": "茶包1-2袋沸水焖泡10分钟，可反复冲泡",
        "duration": "焖泡10分钟", "scenes": ["情绪舒压"],
        "constitutions_suitable": ["阴虚", "血瘀"], "constitutions_unsuitable": ["痰湿"],
        "population": "头发稀少、早白人群",
        "contraindication": "脾胃虚寒便溏者慎用；肝肾功能异常者禁用（原文）",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》（原方名'桑葚枸杞生发饮'）", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("桑椹", "药食同源", None, note="原文未标克数"), M("枸杞子", "药食同源", None, note="原文未标克数")],
    },
    {
        "name": "西洋参石斛补气茶", "type": "茶饮",
        "oneliner": "补气养阴的亚健康轻养茶参考",
        "description": "西洋参补气养阴清热，石斛益胃生津；适合疲劳、口干的亚健康人群温和调养。",
        "method": "茶包1-2袋沸水焖泡10分钟，可反复冲泡",
        "duration": "焖泡10分钟", "scenes": ["换季调理"],
        "constitutions_suitable": ["气虚", "阴虚"], "constitutions_unsuitable": ["阳虚"],
        "population": "疲劳乏力、咽干口燥的亚健康人群",
        "contraindication": "脾胃虚寒者禁用（原文）；不宜与藜芦同用",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("西洋参", "药食同源", None, note="原文未标克数"), M("石斛", "药食同源", None, note="原文未标克数")],
    },
    {
        "name": "乌梅消暑饮", "type": "茶饮",
        "oneliner": "生津解渴的传统乌梅饮参考",
        "description": "乌梅生津敛阴，山楂消食化积，陈皮理气；夏季冰镇后即为传统酸梅汤风味。",
        "method": "茶包1袋加冷水适量大火煮开，加冰糖调味",
        "duration": "煮沸", "scenes": ["消化"],
        "constitutions_suitable": [], "constitutions_unsuitable": [],
        "population": "夏季燥热、口干人群",
        "contraindication": "脾胃虚寒、肝肾功能异常者禁用（原文）；感冒发热期不宜",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》（乌梅饮）", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("乌梅", "药食同源", None, note="原文未标克数"), M("山楂", "药食同源", None, note="原文未标克数"), M("陈皮", "药食同源", None, note="原文未标克数"), M("冰糖", "普通食物", None, optional=True, note="适量调味")],
    },
    {
        "name": "陈皮茯苓健脾祛湿茶", "type": "茶饮",
        "oneliner": "健脾祛湿的基础轻养茶参考",
        "description": "陈皮理气健脾燥湿，茯苓健脾渗湿；两味皆为药食同源经典健脾组合，适合湿气重人群日常饮用。",
        "method": "茶包1-2袋沸水焖泡10分钟，可反复冲泡",
        "duration": "焖泡10分钟", "scenes": ["消化"],
        "constitutions_suitable": ["痰湿"], "constitutions_unsuitable": ["湿热"],
        "population": "湿气重、脘腹胀满人群",
        "contraindication": "实热、湿热、阴虚内热者禁用（原文）",
        "source": "安徽省庐江县人民医院中医科《15款中药代茶饮》", "reference_url": "https://www.ahljyy.com/display.asp?id=10970",
        "status": "待核对",
        "materials": [M("陈皮", "药食同源", None, note="原文未标克数"), M("茯苓", "药食同源", None, note="原文未标克数")],
    },
]

DIET_ADD = [
    # ---- 广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水 ----
    {
        "name": "莲藕双豆百合猪骨汤", "type": "药膳",
        "oneliner": "初秋祛湿润燥的家常煲汤参考",
        "description": "莲藕熟用健脾开胃，赤小豆利水祛湿，百合润肺清心，陈皮理气；初秋暑湿未清时的一道平和家常汤。",
        "method": "全部材料入锅，加水煲汤约1.5小时，加盐调味（2-3人份）",
        "duration": "煲1.5小时", "scenes": ["换季调理"],
        "constitutions_suitable": ["痰湿", "平和"], "constitutions_unsuitable": [],
        "population": "初秋日常家庭饮用人群",
        "contraindication": "高尿酸、痛风人群少喝老火汤（原文通用提示）",
        "source": "广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水", "reference_url": "https://gdcmm.gzucm.edu.cn/info/1010/4147.htm",
        "status": "待核对",
        "materials": [M("莲藕", "普通食物", 375, note="原文250-500g取中值"), M("赤小豆", "药食同源", 40, note="原文30-50g取中值；成分数据待补"), M("眉豆", "普通食物", 40, note="原文30-50g取中值；非目录内，家常豆类"), M("猪脊骨", "普通食物", 400), M("百合", "药食同源", 60, note="原文鲜百合1个约60g"), M("陈皮", "药食同源", 3, note="原文1瓣"), M("蜜枣", "普通食物", 15, note="原文1枚")],
    },
    {
        "name": "莲子莲藕水鸭汤", "type": "药膳",
        "oneliner": "滋阴补虚、养心安神的秋季炖汤参考",
        "description": "水鸭滋阴，莲子养心安神，百合润肺，炒薏米祛湿，陈皮理气；中秋时节防治秋乏秋燥的平和滋补汤。",
        "method": "全部材料入锅加水，煲汤约1.5小时，加盐调味（2-3人份）",
        "duration": "煲1.5小时", "scenes": ["换季调理", "助眠"],
        "constitutions_suitable": ["阴虚", "平和"], "constitutions_unsuitable": ["阳虚"],
        "population": "秋乏、秋燥人群",
        "contraindication": "高尿酸、痛风人群少喝老火汤；脾胃虚寒者少饮",
        "source": "广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水", "reference_url": "https://gdcmm.gzucm.edu.cn/info/1010/4147.htm",
        "status": "待核对",
        "materials": [M("莲子", "药食同源", 20, note="成分数据待补"), M("莲藕", "普通食物", 400, note="原文2-3节约400g"), M("百合", "药食同源", 60, note="原文鲜百合1个"), M("鸭肉", "普通食物", 600, note="原文鸭半只"), M("陈皮", "药食同源", 3, note="原文1瓣"), M("薏苡仁", "药食同源", 20, note="原文炒薏米"), M("蜜枣", "普通食物", 15, note="原文1枚"), M("生姜", "药食同源", 9, note="原文3片")],
    },
    {
        "name": "椰子木瓜银耳猪骨汤", "type": "药膳",
        "oneliner": "补益肺气、健脾固肾的美容养颜汤参考",
        "description": "椰子水清甜生津，木瓜和胃化湿，银耳滋阴润肤，芡实、莲子健脾固肾；秋季日常滋润养颜的家常汤。",
        "method": "全部材料入锅加水，煲汤约1.5小时，加盐调味（2-3人份）",
        "duration": "煲1.5小时", "scenes": ["控油祛痘"],
        "constitutions_suitable": ["平和", "阴虚"], "constitutions_unsuitable": [],
        "population": "秋季皮肤干燥、日常养颜需求人群",
        "contraindication": "高尿酸、痛风人群少喝老火汤",
        "source": "广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水", "reference_url": "https://gdcmm.gzucm.edu.cn/info/1010/4147.htm",
        "status": "待核对",
        "materials": [M("椰子", "普通食物", 500, note="原文椰子1个"), M("芡实", "药食同源", 15, note="成分数据待补"), M("莲子", "药食同源", 15, note="原文去芯；成分数据待补"), M("木瓜", "普通食物", 500, note="原文木瓜1个"), M("猪骨", "普通食物", 400), M("银耳", "普通食物", 10, note="滋阴润肤主料之一"), M("大枣", "药食同源", 9, note="原文红枣3枚去核"), M("生姜", "药食同源", 6, note="原文2片")],
    },
    {
        "name": "淮山地黄栗子煲鸡", "type": "药膳",
        "oneliner": "健脾胃、滋阴益气的深秋平补汤参考",
        "description": "山药健脾益气，熟地黄滋阴养血，板栗补肾强筋，茯苓、莲子、芡实健脾祛湿，陈皮理气；深秋平补的经典搭配。",
        "method": "全部材料入锅加水，煲汤约1.5小时，加盐调味（2-3人份）",
        "duration": "煲1.5小时", "scenes": ["换季调理"],
        "constitutions_suitable": ["气虚", "阴虚"], "constitutions_unsuitable": ["湿热"],
        "population": "深秋体虚、脾胃虚弱人群",
        "contraindication": "湿盛中满、腹胀者少饮；高尿酸痛风人群少喝老火汤",
        "source": "广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水", "reference_url": "https://gdcmm.gzucm.edu.cn/info/1010/4147.htm",
        "status": "待核对",
        "materials": [M("鸡肉", "普通食物", 600, note="原文鸡半只"), M("山药", "药食同源", 50, note="原文淮山药"), M("熟地黄", "药食同源", 15), M("板栗", "普通食物", 200, note="去壳去皮"), M("大枣", "药食同源", 9, note="原文若干，按3枚计"), M("茯苓", "药食同源", 15, note="原文白茯苓"), M("莲子", "药食同源", 15, note="原文建莲；成分数据待补"), M("芡实", "药食同源", 15, note="成分数据待补"), M("陈皮", "药食同源", 2, note="原文1/8个")],
    },
    {
        "name": "石斛洋参炖乌鸡", "type": "药膳",
        "oneliner": "益气生津、养阴润燥的清炖汤参考",
        "description": "石斛益胃生津，西洋参补气养阴，乌鸡滋阴补血；滋补而不腻，适合秋冬抗燥、皮肤干燥与咽干人群。",
        "method": "全部材料隔水清炖约2小时，加盐调味（2-3人份）",
        "duration": "炖2小时", "scenes": ["换季调理", "经期温养"],
        "constitutions_suitable": ["阴虚", "气虚"], "constitutions_unsuitable": ["阳虚"],
        "population": "秋冬咽干皮肤干燥、月经量少人群的滋养参考",
        "contraindication": "感冒发热期不宜；脾胃虚寒便溏者慎用",
        "source": "广东省中西医结合医院治未病中心（广东中医药博物馆发布）秋季药膳汤水", "reference_url": "https://gdcmm.gzucm.edu.cn/info/1010/4147.htm",
        "status": "待核对",
        "materials": [M("乌鸡", "普通食物", 250), M("石斛", "药食同源", 6, note="原文2-3粒"), M("西洋参", "药食同源", 5), M("生姜", "药食同源", 3, note="原文1片"), M("蜜枣", "普通食物", 15, note="原文1枚")],
    },
]

# ---- 合并写盘 ----
tea_fp = RAW / "tea.json"
data = json.loads(tea_fp.read_text(encoding="utf-8"))
existing = {r["name"] for r in data["recipes"]}
added = 0
for r in TEA_ADD:
    if r["name"] not in existing:
        data["recipes"].append(r)
        added += 1
tea_fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"tea.json: +{added}，现共 {len(data['recipes'])} 条")

diet_fp = RAW / "diet.json"
if diet_fp.exists():
    ddata = json.loads(diet_fp.read_text(encoding="utf-8"))
else:
    ddata = {"agent_note": "药膳方采集 v0.1 全部待人工核对", "recipes": []}
dexisting = {r["name"] for r in ddata["recipes"]}
dadded = 0
for r in DIET_ADD:
    if r["name"] not in dexisting:
        ddata["recipes"].append(r)
        dadded += 1
diet_fp.write_text(json.dumps(ddata, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"diet.json: +{dadded}，现共 {len(ddata['recipes'])} 条")
