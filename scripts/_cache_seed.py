# -*- coding: utf-8 -*-
"""
采集缓存入库/还原（让「新克隆仓库能离线重建知识库」成立）

背景（2026-11-06 实测）：扩容数据有两条来源——
  1. `data/cache/herb_ingest_*.json`：HERB API 的原始响应缓存（import_herbs_* 脚本读）
  2. `data/shiyang.db`：构建产物
两条都被 .gitignore 排除，且 HERB 接口的 POST 格式随时可能变（2026-11-06 实测：
  form-urlencoded 一律返回 null，必须 JSON body），**一旦外站变动，重建就彻底断链**。

因此把三份缓存以 gzip 形式放进仓库（`data/herb_ingest_*.json.gz`，共 2.6MB），
本模块负责在 `data/cache/` 里缺原始 JSON 时自动解压还原，脚本无需改动读法。

用法（脚本内）：
    from _cache_seed import ensure_cache
    ensure_cache(ROOT, "herb_ingest_20261105")   # -> data/cache/herb_ingest_20261105.json
"""
import gzip
from pathlib import Path


def ensure_cache(root: Path, stem: str) -> Path:
    """确保 <root>/data/cache/<stem>.json 存在；缺则从 <root>/data/<stem>.json.gz 还原。

    返回最终 JSON 路径（可能仍不存在——此时调用方按原有联网逻辑处理）。
    还原是幂等的：已存在就什么都不做，绝不覆盖现场采集到的新数据。
    """
    live = root / "data" / "cache" / f"{stem}.json"
    if live.exists():
        return live
    seed = root / "data" / f"{stem}.json.gz"
    if not seed.exists():
        return live
    live.parent.mkdir(parents=True, exist_ok=True)
    tmp = live.with_suffix(".json.restore-tmp")
    with gzip.open(seed, "rb") as src, open(tmp, "wb") as dst:
        dst.write(src.read())
    tmp.replace(live)
    print(f"[cache] 从 {seed.name} 还原 {live.relative_to(root)}"
          f"（{live.stat().st_size:,} bytes）")
    return live
