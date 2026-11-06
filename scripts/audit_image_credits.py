# -*- coding: utf-8 -*-
"""
图片许可核查与缺口标注（2026-11-06）

结论先说：2026-10 那批 82 张图里有 81 条 credits 记成 null，**无法可靠回填**。
原因（已实测）：本地存的是 480px 缩略图，其 sha1 与原图不同，Commons 的
`list=allimages&aisha1=` 只能按**原图** sha1 精确命中（实测 5 张里 1 张）；
按搜索词重查会拿到**另一张图**（实测「枸杞子」重搜首条不是当初那张），
那样补出来的署名是错的——比留空更糟。

因此本脚本不做「推测式回填」，只做两件事：
  1. **核查**：报告每张图的署名状态（ok / missing），以及许可类型分布
  2. **标记缺口**：把无法确认的记入 `credits[name].license = "unverified"` 之类
     的显式状态，避免「null 看着像没记录」被误读成「已记录且无要求」

处置建议（写进 docs）：
  - 81 张历史图若要在公网/答辩材料里展示，须**重新抓一次**（重抓会重写 credits，
    图片内容可能变化但署名与图必然对应），或直接 `--force` 全量重抓一遍。
  - `fetch_material_images.py --force` 就是这条路径：重下图 + 重记署名，
    保证「图 ↔ 署名」一致。代价是部分图会换成另一张（同样合规的）照片。

用法：
    python -X utf8 scripts/audit_image_credits.py
    python -X utf8 scripts/audit_image_credits.py --mark-missing   # 写 unverified 标记
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
IMGDIR = ROOT / "frontend" / "public" / "img" / "materials"
CREDITS = ROOT / "frontend" / "public" / "img" / "credits.json"


def main():
    mark = "--mark-missing" in sys.argv
    data = json.loads(CREDITS.read_text(encoding="utf-8"))
    credits = data.get("credits") or {}
    imgs = sorted(f.stem for f in IMGDIR.glob("*.jpg"))

    ok, missing = [], []
    for n in imgs:
        c = credits.get(n)
        if isinstance(c, dict) and c.get("license"):
            ok.append(n)
        else:
            missing.append(n)

    print(f"图片 {len(imgs)} 张 | 署名齐全 {len(ok)} | 缺署名 {len(missing)}")
    if missing:
        print(f"\n[缺署名]（旧批次 2026-10，无法可靠回填，需 --force 重抓）：")
        for n in missing:
            print("  ", n)
        print("\n  → 处理方式：python -X utf8 scripts/fetch_material_images.py --force")
        print("     全量重下图并重写署名，保证「图↔署名」一致（部分图会换成另一张同样合规的照片）")

    lic = Counter((credits.get(n) or {}).get("license", "?")
                  for n in imgs if isinstance(credits.get(n), dict))
    print("\n许可分布（已记录部分）：")
    for k, v in lic.most_common():
        print(f"  {k or '?':<20} {v}")

    if mark and missing:
        for n in missing:
            credits[n] = {"license": "unverified",
                          "artist": None,
                          "title": None,
                          "note": "旧批次未记录署名，无法可靠回填；重抓可修复"}
        data["credits"] = credits
        CREDITS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n已给 {len(missing)} 条写 unverified 标记（语义：署名未知，非「无署名要求」）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
