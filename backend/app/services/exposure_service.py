# -*- coding: utf-8 -*-
"""
暴露量估计服务：配料克重 × 药材-成分含量(%) → 每方各成分的估计摄入量(mg)
公式：摄入量mg = 克重g × 含量% × 1000/100 × 转移率(冲泡/炖煮默认保守 0.5)
吸收期望mg = 摄入量mg × 入血概率(prob_cctcm, PU-Learning 预测) —— C级证据，页面须标注"预测"
结果为保守估计区间 [min, max]，页面标注"估计值"。
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"
TRANSFER_RATE = 0.5  # 水提取转移率（保守假设，文献常见 0.3-0.7）


def estimate(recipe_id: int) -> dict | None:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        mats = conn.execute(
            "SELECT m.name, m.grams, m.material_type FROM rel_recipe_material m "
            "WHERE m.recipe_id=?", (recipe_id,)).fetchall()
        if not mats:
            return None
        out = []
        for m in mats:
            if m["material_type"] != "herb" or not m["grams"] or m["grams"] <= 0:
                continue
            rows = conn.execute(
                "SELECT hc.compound_name, hc.content_min_pct, hc.content_max_pct, "
                "c.prob_cctcm "
                "FROM herb_compound_content hc "
                "LEFT JOIN compound c ON c.name = hc.compound_name "
                "WHERE hc.herb_name=?", (m["name"],)).fetchall()
            for r in rows:
                lo = m["grams"] * r["content_min_pct"] / 100 * 1000 * TRANSFER_RATE
                hi = m["grams"] * r["content_max_pct"] / 100 * 1000 * TRANSFER_RATE
                prob = r["prob_cctcm"]
                item = {"herb": m["name"], "grams": m["grams"],
                        "compound": r["compound_name"],
                        "est_mg_min": round(lo, 2), "est_mg_max": round(hi, 2)}
                # 入血概率能对上 compound 主表才给吸收期望，对不上的只给摄入量
                if prob is not None:
                    # 概率保留 4 位，吸收期望用全精度计算，避免二次舍入误差
                    item["prob_cctcm"] = round(prob, 4)
                    item["absorbed_mg_min"] = round(lo * prob, 2)
                    item["absorbed_mg_max"] = round(hi * prob, 2)
                out.append(item)
        out.sort(key=lambda x: -x["est_mg_max"])
        return {"transfer_rate": TRANSFER_RATE, "items": out[:15],
                "note": "估计值 = 克重 × 文献含量区间 × 50%转移率假设；"
                        "吸收期望 = 摄入量 × 入血概率（PU-Learning 模型预测，C级证据）；"
                        "仅代表数量级参考"}
    finally:
        conn.close()
