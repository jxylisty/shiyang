# -*- coding: utf-8 -*-
"""
暴露量估计服务：配料克重 × 药材-成分含量(%) → 每方各成分的估计摄入量(mg)
公式：摄入量mg = 克重g × 含量% × 1000/100 × 转移率(冲泡/炖煮默认保守 0.5)
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
                "SELECT compound_name, content_min_pct, content_max_pct "
                "FROM herb_compound_content WHERE herb_name=?", (m["name"],)).fetchall()
            for r in rows:
                lo = m["grams"] * r["content_min_pct"] / 100 * 1000 * TRANSFER_RATE
                hi = m["grams"] * r["content_max_pct"] / 100 * 1000 * TRANSFER_RATE
                out.append({"herb": m["name"], "grams": m["grams"],
                            "compound": r["compound_name"],
                            "est_mg_min": round(lo, 2), "est_mg_max": round(hi, 2)})
        out.sort(key=lambda x: -x["est_mg_max"])
        return {"transfer_rate": TRANSFER_RATE, "items": out[:15],
                "note": "估计值 = 克重 × 文献含量区间 × 50%转移率假设；仅代表数量级参考"}
    finally:
        conn.close()
