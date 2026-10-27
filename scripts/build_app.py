"""把前端构建成可打进 5+App 的产物，并装配到 HBuilderX 壳工程。

背景（都是实测踩过的坑）：
1. 5+App 云打包禁止中文/全角文件名，而 `public/img/materials/` 下 82 张药材图是
   `乌梅.jpg` 这类中文名 → 构建时统一改名为 `m01.jpg` 这类 ASCII 名，并把
   「中文名 → ASCII 名」映射通过 VITE_MAT_MAP 注入前端（api/index.js 的 matImg 消费）。
   仓库里的原图不动，只在 app 产物里改名，web 版构建完全不受影响。
2. app 内是 file:// 环境，绝对路径 `/api/v1`、`/img/...` 全部失效 →
   vite 用 `--mode app`（base './' + hash 路由），API 地址靠 VITE_API_BASE 注入。

用法：
    python -X utf8 scripts/build_app.py --api http://192.168.1.5:8100/api/v1
    python -X utf8 scripts/build_app.py              # 默认沿用上次写入的地址
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
PUBLIC_MAT = FRONTEND / "public" / "img" / "materials"
DIST_APP = FRONTEND / "dist-app"
SHELL = ROOT.parent / "shiyang-app5"
API_CACHE = ROOT / "frontend" / ".app_api_base"


def build_mat_map():
    """中文图名 → mNN，按名称排序保证多次构建结果稳定。"""
    names = sorted(p.stem for p in PUBLIC_MAT.glob("*.jpg"))
    return {n: f"m{i:02d}" for i, n in enumerate(names, 1)}, names


def run_frontend_build(api_base, mat_map):
    env = dict(os.environ)
    env["VITE_API_BASE"] = api_base
    env["VITE_MAT_MAP"] = json.dumps(mat_map, ensure_ascii=False)
    print(f"[1/3] vite build --mode app  (API={api_base}, 图片映射 {len(mat_map)} 项)")
    proc = subprocess.run(
        ["npx", "vite", "build", "--mode", "app"],
        cwd=FRONTEND, env=env, shell=(os.name == "nt"),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:])
        sys.exit("前端构建失败")


def assemble(mat_map):
    """把产物铺进 5+App 项目根目录。

    5+App 的资源根就是项目目录本身（manifest 的 launch_path 为 "index.html"），
    不是 www/。曾把产物放 www/ 里，结果 app 启动的是根目录那个空模板 index.html，
    装上去白屏——云打包也不报错，只在真机上才看得出来。
    """
    # 清掉上次装配的内容（只清我们自己产出的，不碰 manifest.json / unpackage / 证书）
    for name in ("assets", "fonts", "img"):
        p = SHELL / name
        if p.exists():
            shutil.rmtree(p)
    # 5+App 项目创建时自带的空壳目录，产物会覆盖它们
    for name in ("css", "js"):
        p = SHELL / name
        if p.exists() and not any(p.iterdir()):
            shutil.rmtree(p)

    for item in DIST_APP.iterdir():
        dst = SHELL / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)

    mat_dir = SHELL / "img" / "materials"
    if mat_dir.exists():
        shutil.rmtree(mat_dir)
    mat_dir.mkdir(parents=True, exist_ok=True)
    for zh, ascii_name in mat_map.items():
        shutil.copy2(PUBLIC_MAT / f"{zh}.jpg", mat_dir / f"{ascii_name}.jpg")
    print(f"[2/3] 已装配到项目根目录，药材图 {len(mat_map)} 张改为 ASCII 名")


def write_api_cache(api_base):
    API_CACHE.write_text(api_base, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", help="后端地址，形如 http://192.168.1.5:8100/api/v1")
    args = ap.parse_args()

    api_base = args.api
    if not api_base:
        if API_CACHE.exists():
            api_base = API_CACHE.read_text(encoding="utf-8").strip()
            print(f"沿用上次的 API 地址：{api_base}")
        else:
            sys.exit("首次构建请用 --api 指定后端地址，例如 "
                     "--api http://192.168.1.5:8100/api/v1")

    mat_map, _ = build_mat_map()
    run_frontend_build(api_base, mat_map)
    assemble(mat_map)
    write_api_cache(api_base)
    print(f"[3/3] 完成：{SHELL}\n"
          "      下一步在 HBuilderX 里对该项目执行 发行 → 原生App-云打包")


if __name__ == "__main__":
    main()
