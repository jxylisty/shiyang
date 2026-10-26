# -*- coding: utf-8 -*-
"""
填充 food 表 nutrient_json（每 100g 可食部基础五项 + 亮点说明）
数据口径：《中国食物成分表（第 6 版）》公开常见值的约值，供科普展示，非精确营养计算。
用法：
    python scripts/fill_nutrients.py           # 幂等：已有值的条目跳过
    python scripts/fill_nutrients.py --force   # 全部覆盖重写
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "shiyang.db"

SOURCE = "《中国食物成分表（第6版）》常见值，约值，每100g可食部"


def N(energy, protein, fat, carb, fiber, highlight):
    return {
        "energy_kcal": energy, "protein_g": protein, "fat_g": fat,
        "carb_g": carb, "fiber_g": fiber, "highlight": highlight, "source": SOURCE,
    }


# key 与 food.name 一致；缺项用 None 占位（前端按「未收录」处理）
DATA = {
    # 谷物
    "小米":   N(361, 9.0, 3.1, 73.5, 1.6, "B族维生素与铁含量高于精白米"),
    "粳米":   N(346, 7.7, 0.6, 77.9, 0.6, "易消化的主食基底"),
    "红豆":   N(324, 20.2, 0.6, 55.7, 7.7, "高钾高纤维，利水消肿经典食材"),
    "绿豆":   N(329, 21.6, 0.8, 55.6, 6.4, "夏季清热经典，蛋白与B族维生素丰富"),
    "眉豆":   N(326, 18.6, 1.1, 60.0, 6.6, "健脾化湿的豆类，膳食纤维丰富"),
    # 蔬菜
    "冬瓜":   N(12, 0.4, 0.2, 2.6, 0.7, "热量极低、水分高达96%，利水消肿"),
    "白萝卜": N(23, 0.9, 0.1, 5.0, 1.0, "芥子油苷来源，膳食纤维促进肠道蠕动"),
    "莲藕":   N(73, 1.9, 0.2, 16.4, 1.2, "维生素C与多酚类丰富，熟藕淀粉质温和"),
    "菠菜":   N(28, 2.6, 0.3, 4.5, 1.7, "叶酸、胡萝卜素与钾的优质来源"),
    "马蹄":   N(61, 1.2, 0.2, 14.2, 1.1, "水分足、清甜，含磷与膳食纤维"),
    # 水果
    "雪梨":   N(50, 0.4, 0.2, 13.3, 3.0, "水分超85%，传统润燥水果"),
    "柚子":   N(42, 0.8, 0.2, 9.5, 0.4, "维生素C含量高（约23mg/100g）"),
    "椰子":   N(241, 4.0, 12.1, 31.3, 4.7, "椰肉脂肪与中链脂肪酸较丰富"),
    "海棠果": N(73, 0.3, 0.2, 19.2, 1.7, "含果胶与有机酸"),
    # 肉禽
    "乌鸡":   N(111, 22.3, 2.3, 0.3, 0, "蛋白质高、脂肪低的滋补禽肉"),
    "鸡肉":   N(167, 19.3, 9.4, 1.3, 0, "优质蛋白与烟酸来源"),
    "鸭肉":   N(240, 15.5, 19.7, 0.2, 0, "B族维生素与不饱和脂肪酸较丰富"),
    "羊肉":   N(203, 19.0, 14.1, 0, 0, "富铁富锌的温补红肉"),
    "猪瘦肉": N(143, 20.3, 6.2, 1.5, 0, "优质蛋白与B1（硫胺素）来源"),
    "猪肝":   N(129, 19.3, 3.5, 5.0, 0, "铁与维生素A含量突出的内脏（注意频次）"),
    "猪肚":   N(110, 15.2, 5.1, 0.7, 0, "蛋白较高的内脏食材"),
    "排骨":   N(278, 16.7, 23.1, 0.7, 0, "炖汤风味佳，脂肪含量较高"),
    "猪骨":   N(None, None, None, None, None, "以矿物质溶出为主，营养以汤中少量蛋白为限"),
    "猪脊骨": N(None, None, None, None, None, "以矿物质溶出为主，营养以汤中少量蛋白为限"),
    # 水产
    "鲫鱼":   N(108, 17.1, 2.7, 3.8, 0, "优质蛋白与不饱和脂肪酸，传统催乳食材"),
    "鲢鱼头": N(None, None, None, None, None, "以炖汤风味与少量蛋白为主"),
    # 其他
    "鸡蛋":   N(144, 13.3, 8.8, 2.8, 0, "全价优质蛋白与卵磷脂来源"),
    "牛奶":   N(54, 3.0, 3.2, 3.4, 0, "钙（约104mg/100g）与优质蛋白来源"),
    "银耳":   N(261, 10.0, 1.7, 67.3, 30.4, "银耳多糖丰富（干重），泡发后热量低"),
    "板栗":   N(214, 4.2, 0.7, 46.0, 1.7, "淀粉与钾丰富，维生素C含量在坚果中突出"),
    "核桃":   N(646, 14.9, 58.8, 9.6, 9.5, "α-亚麻酸（omega-3）植物来源代表"),
    "花生":   N(574, 24.8, 44.3, 21.7, 5.5, "蛋白与维生素E、烟酸丰富"),
    "玉米须": N(None, None, None, None, None, "传统利水茶饮用料，无常规食物成分数据"),
    # 茶叶
    "绿茶":   N(None, None, None, None, None, "冲饮为主，儿茶素等多酚类见成分库分析"),
    # 调味
    "冰糖":   N(397, 0, 0, 99.3, 0, "精制糖，主要提供甜味与能量"),
    "白糖":   N(400, 0, 0, 99.9, 0, "精制糖，主要提供甜味与能量"),
    "红糖":   N(389, 0.7, 0, 96.6, 0, "保留少量矿物质（铁、钙）的粗制糖"),
    "蜜枣":   N(321, 1.1, 0.3, 84.4, 1.6, "糖分高，少量膳食纤维"),
    "玫瑰花": N(None, None, None, None, None, "香料花材，以挥发油与多酚类为主，无常规成分数据"),
}


def main():
    force = "--force" in sys.argv
    if not DB.exists():
        print(f"数据库不存在: {DB}")
        sys.exit(1)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    foods = conn.execute("SELECT id,name,nutrient_json FROM food").fetchall()
    hit, skip, miss = 0, 0, []
    for f in foods:
        d = DATA.get(f["name"])
        if not d:
            miss.append(f["name"])
            continue
        if f["nutrient_json"] and not force:
            skip += 1
            continue
        conn.execute("UPDATE food SET nutrient_json=? WHERE id=?",
                     (json.dumps(d, ensure_ascii=False), f["id"]))
        hit += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM food WHERE nutrient_json IS NOT NULL AND nutrient_json!=''").fetchone()[0]
    conn.close()
    print(f"本次写入 {hit} 条，跳过已有 {skip} 条，未收录 {len(miss)} 条：{'、'.join(miss) or '无'}")
    print(f"food 表现有营养数据 {total}/{len(foods)} 条")


if __name__ == "__main__":
    main()
