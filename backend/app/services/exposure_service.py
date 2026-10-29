# -*- coding: utf-8 -*-
"""
暴露量估计服务：配料克重 × 药材-成分含量(%) → 每方各成分的估计摄入量(mg)
公式：摄入量mg = 克重g × 含量% × 1000/100 × 转移率(冲泡/炖煮)
吸收期望mg = 摄入量mg × 入血概率(prob_cctcm, PU-Learning 预测) —— C级证据，页面须标注"预测"

转移率不再用单一常数，而是给三档情景（保守/基准/乐观）：
  低 0.3 / 中 0.5 / 高 0.7 —— 区间取自文献常见范围，与定量药理课件
  「不确定的输入取多个值跑一遍、输出区间而非单点」的规范一致。
含量本身也有 [min, max] 区间，两者组合即得每个成分的暴露量区间。
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

# 水提取转移率三档情景（保守假设，文献常见 0.3-0.7）
TRANSFER_LOW = 0.3
TRANSFER_BASE = 0.5
TRANSFER_HIGH = 0.7


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
                g = m["grams"]
                cmin = r["content_min_pct"] / 100 * 1000
                cmax = r["content_max_pct"] / 100 * 1000
                # 摄入量三档：含量区间 × 转移率区间 → 保守下界 / 基准 / 乐观上界
                lo = g * cmin * TRANSFER_LOW
                mid = g * ((cmin + cmax) / 2) * TRANSFER_BASE
                hi = g * cmax * TRANSFER_HIGH
                prob = r["prob_cctcm"]
                item = {"herb": m["name"], "grams": g,
                        "compound": r["compound_name"],
                        "est_mg_min": round(lo, 2),
                        "est_mg_base": round(mid, 2),
                        "est_mg_max": round(hi, 2)}
                # 入血概率能对上 compound 主表才给吸收期望，对不上的只给摄入量
                if prob is not None:
                    item["prob_cctcm"] = round(prob, 4)
                    item["absorbed_mg_min"] = round(lo * prob, 2)
                    item["absorbed_mg_base"] = round(mid * prob, 2)
                    item["absorbed_mg_max"] = round(hi * prob, 2)
                out.append(item)
        out.sort(key=lambda x: -x["est_mg_max"])
        return {
            "transfer_rate": TRANSFER_BASE,
            "transfer_scenarios": {"low": TRANSFER_LOW, "base": TRANSFER_BASE, "high": TRANSFER_HIGH},
            "items": out[:15],
            "note": "估计值 = 克重 × 文献含量区间 × 转移率（保守0.3/基准0.5/乐观0.7 三档）；"
                    "吸收期望 = 摄入量 × 入血概率（PU-Learning 模型预测，C级证据）；"
                    "仅代表数量级参考，不是药代动力学测定",
        }
    finally:
        conn.close()
