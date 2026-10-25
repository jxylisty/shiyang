# -*- coding: utf-8 -*-
"""
盘点：药食同源目录(106种) × 现有哮喘系统 herb 表(278味) 重合度
输出：docs/overlap_report.md + 控制台摘要
用法：python -X utf8 check_overlap.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent          # shiyang/
DB_PATH = ROOT.parent / "my-asthma-system" / "asthma-core" / "data" / "asthma_v2.db"
CATALOG = ROOT / "data" / "food_homology_catalog.json"
REPORT = ROOT / "docs" / "overlap_report.md"


def load_herbs(conn):
    rows = conn.execute(
        "SELECT id, name, IFNULL(alias,''), category FROM herb"
    ).fetchall()
    # 每味药材实际关联的化合物数（以关联表为准，不信冗余列）
    counts = dict(
        conn.execute(
            "SELECT herb_id, COUNT(DISTINCT compound_id) FROM rel_herb_compound GROUP BY herb_id"
        ).fetchall()
    )
    herbs = []
    for hid, name, alias, category in rows:
        alias_list = [a.strip() for a in alias.replace("；", ";").replace(",", ";").split(";") if a.strip()]
        herbs.append({"id": hid, "name": name, "aliases": alias_list,
                      "category": category, "compound_count": counts.get(hid, 0)})
    return herbs


def candidates(item):
    """目录条目的所有候选名：正式名 + 异名 + 去掉'鲜'前缀等变体"""
    names = [item["name"]] + item["aliases"]
    extra = []
    for n in names:
        if n.startswith("鲜"):
            extra.append(n[1:])
        extra.append(n.replace("（", "(").split("(")[0])  # 去括号限定语
    return [n for n in set(names + extra) if n]


def match(item, herbs):
    """返回 (匹配方式, [herb...])"""
    cands = candidates(item)
    by_name = {}
    for h in herbs:
        by_name.setdefault(h["name"], []).append(h)
    # 1) 精确匹配（候选名 == 药材名）
    exact = []
    for c in cands:
        exact.extend(by_name.get(c, []))
    if exact:
        return "精确", exact
    # 2) 包含匹配（双向，候选名长度>=2 防止单字误命中）
    fuzzy = []
    for h in herbs:
        hn = h["name"]
        for c in cands:
            if len(c) >= 2 and (c in hn or hn in c):
                fuzzy.append(h)
                break
    if fuzzy:
        return "模糊", fuzzy
    # 3) 药材别名匹配
    alias_hit = []
    for h in herbs:
        for a in h["aliases"]:
            for c in cands:
                if a and len(a) >= 2 and (a == c or a in c or c in a):
                    alias_hit.append(h)
                    break
            if alias_hit and alias_hit[-1] is h:
                break
    if alias_hit:
        return "别名", alias_hit
    return None, []


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = catalog["items"]
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    herbs = load_herbs(conn)
    print(f"目录条目: {len(items)} 种 | 现有药材: {len(herbs)} 味")

    matched, unmatched = [], []
    for item in items:
        how, hits = match(item, herbs)
        if hits:
            # 同名去重（一味药材可能被多个候选名命中）
            uniq = {h["id"]: h for h in hits}
            matched.append({"item": item, "how": how, "herbs": list(uniq.values())})
        else:
            unmatched.append(item)

    def herblink(h):
        return f"{h['name']}({h['compound_count']}个化合物)"

    lines = ["# 药食同源目录 × 现有药材库 重合度盘点", "",
             f"- 目录条目：**{len(items)}** 种（2002/2019/2023/2024 四批公告）",
             f"- 现有药材库：**{len(herbs)}** 味，化合物 {conn.execute('SELECT COUNT(*) FROM compound').fetchone()[0]} 个",
             f"- **命中：{len(matched)} 种（{len(matched)/len(items)*100:.0f}%）**，未命中：{len(unmatched)} 种", ""]

    total_compounds = set()
    lines += ["## 一、已命中（可直接进食疗/茶饮分析管线）", "",
              "| 目录物质 | 批次 | 匹配方式 | 命中药材 |", "|---|---|---|---|"]
    for m in sorted(matched, key=lambda x: -sum(h["compound_count"] for h in x["herbs"])):
        names = "、".join(herblink(h) for h in m["herbs"])
        lines.append(f"| {m['item']['name']} | {m['item']['batch']} | {m['how']} | {names} |")
        for h in m["herbs"]:
            for (cid,) in conn.execute(
                "SELECT compound_id FROM rel_herb_compound WHERE herb_id=?", (h["id"],)
            ):
                total_compounds.add(cid)

    lines += ["", "## 二、未命中（需要补数据或建普通食材表）", ""]
    if unmatched:
        by_batch = {}
        for it in unmatched:
            by_batch.setdefault(it["batch"], []).append(it["name"])
        for b in sorted(by_batch):
            lines.append(f"- **{b}年批次**：{'、'.join(by_batch[b])}")
    else:
        lines.append("无")

    lines += ["", "## 三、结论与下一步", "",
              f"- 命中的 {len(matched)} 种物质共关联 **{len(total_compounds)}** 个去重化合物，"
              f"其中高入血概率(prob_cctcm≥0.5)的：",
              f"  {conn.execute('SELECT COUNT(*) FROM compound WHERE id IN (%s) AND prob_cctcm>=0.5' % ','.join('?'*len(total_compounds)), tuple(total_compounds)).fetchone()[0] if total_compounds else 0} 个"
              if total_compounds else "",
              "- 未命中物质分两类处理：",
              "  1. 本质是药材但库里没有（如代代花、榧子）→ 用 TCMSP-Spider/TCMM 补成分数据后入 herb 表",
              "  2. 本质是食物（如蜂蜜、黑芝麻、赤小豆等已有条目除外的情况）→ 进新建 food 表，营养素走中国食物成分表",
              ""]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"命中 {len(matched)}/{len(items)} ({len(matched)/len(items)*100:.0f}%)，关联去重化合物 {len(total_compounds)} 个")
    print("未命中物质：", "、".join(it["name"] for it in unmatched) or "无")
    print(f"完整报告已写入: {REPORT}")


if __name__ == "__main__":
    main()
