"""启动手机联调用的后端：监听 0.0.0.0 + 放行防火墙 + 打印手机可用的地址。

APP 内的接口地址是构建时写死的（scripts/build_app.py 的 --api），
所以联调前要先知道「手机该连哪个 IP」，再据此构建。

用法（Windows，需管理员权限才能加防火墙规则）：
    python -X utf8 scripts/start_backend_lan.py
    python -X utf8 scripts/start_backend_lan.py --no-firewall   # 已有规则时跳过
"""

import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8100


def lan_ips():
    """列出可能的局域网地址，并标注来源，方便判断哪一个手机能连上。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | "
             "ForEach-Object { $_.IPAddress + '|' + $_.InterfaceAlias }"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        ).stdout
    except Exception as e:  # 非 Windows 或 PowerShell 不可用
        print(f"（获取网卡失败：{e}）")
        return []

    rows = []
    for line in out.strip().splitlines():
        if "|" in line:
            ip, alias = line.split("|", 1)
            rows.append((ip.strip(), alias.strip()))

    def kind(item):
        ip, alias = item
        if "Tailscale" in alias:
            return 3
        if "vEthernet" in alias or "Hyper-V" in alias:
            return 2
        if ip.startswith("192.168.137."):
            return 1  # 移动热点网关
        return 0      # 普通 WLAN/以太网，最常用

    return sorted(rows, key=kind)


def ensure_firewall():
    rule = "Shiyang Backend 8100"
    check = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Get-NetFirewallRule -DisplayName '{rule}' -ErrorAction SilentlyContinue"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check.stdout.strip():
        print(f"[防火墙] 规则已存在：{rule}")
        return
    add = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"New-NetFirewallRule -DisplayName '{rule}' -Direction Inbound -LocalPort {PORT} "
         f"-Protocol TCP -Action Allow -Profile Private,Domain | Out-Null; 'ok'"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if "ok" in (add.stdout or ""):
        print(f"[防火墙] 已放行入站 {PORT}/tcp（仅专用/域网络）")
    else:
        err = (add.stderr or add.stdout or "").strip()[:200]
        print(f"[防火墙] 添加失败，需用管理员权限重跑：{err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-firewall", action="store_true", help="跳过防火墙规则")
    args = ap.parse_args()

    print("=" * 62)
    print("手机联调后端（监听 0.0.0.0:%d）" % PORT)
    print("=" * 62)

    ips = lan_ips()
    if ips:
        print("\n本机地址（按常用程度排序）：")
        for ip, alias in ips:
            note = ""
            if "Tailscale" in alias:
                note = "  ← 虚拟网，手机通常连不上"
            elif "vEthernet" in alias or "Hyper-V" in alias:
                note = "  ← 虚拟机网卡，不要用"
            elif ip.startswith("192.168.137."):
                note = "  ← 移动热点网关，手机需连本机热点"
            print(f"  http://{ip}:{PORT}/api/v1{note}")
        best = next((ip for ip, a in ips
                     if "Tailscale" not in a and "vEthernet" not in a and "Hyper-V" not in a
                     and not ip.startswith("192.168.137.")), None)
        if best:
            print(f"\n推荐：手机与本机连同一 WiFi 时用 http://{best}:{PORT}/api/v1")
            print(f"     用该地址重新构建 APP：python -X utf8 scripts/build_app.py --api http://{best}:{PORT}/api/v1")

    if not args.no_firewall:
        print()
        ensure_firewall()

    print("\n提示：WLAN 若为「公用网络」，Windows 会拦截入站。改为「专用网络」后重试：")
    print("     设置 → 网络和 Internet → WLAN → 当前网络 → 网络配置文件类型 → 专用")
    print("\n启动后端……\n")

    os.environ["SHIYANG_HOST"] = "0.0.0.0"
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn  # noqa: E402
    from app import main as app_main  # noqa: E402,F401

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
