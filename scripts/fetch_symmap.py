# -*- coding: utf-8 -*-
"""拉取 SymMap v2 SMHB 药材表（703 味，含中文性味/归经/别名），供中文性味归经展示用。

用途：backend/app/services/herb_service.py 的 _load_symmap_dict() 会优先读本地
data/symmap_smhb_v2.xlsx，不存在才联网。本脚本用于首次准备或更新这份数据。

数据来源：SymMap v2.0 (http://www.symmap.org/)，学术用途免费。
许可：SymMap 供学术研究使用；本项目为大创课题（非商业），符合其使用条件。
若未来商业化须重新确认授权。

用法：
    python -X utf8 scripts/fetch_symmap.py
    python -X utf8 scripts/fetch_symmap.py --force   # 强制重新下载
"""
import argparse
import sys
from pathlib import Path

import requests

URL = "http://www.symmap.org/static/download/V2.0/SymMap%20v2.0%2C%20SMHB%20file.xlsx"
OUT = Path(__file__).resolve().parents[1] / "data" / "symmap_smhb_v2.xlsx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="已有文件也重新下载")
    args = ap.parse_args()

    if OUT.exists() and not args.force:
        print(f"已存在，跳过：{OUT}（{OUT.stat().st_size} bytes）")
        return 0

    print(f"下载 {URL} …")
    try:
        r = requests.get(URL, timeout=120)
        r.raise_for_status()
    except Exception as e:
        print(f"下载失败：{e}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(r.content)
    print(f"已保存：{OUT}（{len(r.content)} bytes）")

    # 立即校验能否解析，避免存下一个坏文件
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "app"))
        from services import herb_service as hs
        d = hs._parse_symmap_xlsx(OUT)
        print(f"解析校验通过：{len(d)} 味药")
        if len(d) < 500:
            print("警告：解析出的药材数异常偏少，文件可能不完整", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"解析校验失败：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
