"""把 APK 通过局域网发到手机上：起一个只读的下载站。

手机和电脑连同一个 WiFi，手机浏览器打开脚本打印的地址，点一下就能下载安装。
比微信/QQ传文件更省事：不用登录、不用扫码、不受「非 APK 文件」限制。

用法：
    python -X utf8 scripts/serve_apk.py
    python -X utf8 scripts/serve_apk.py --port 8200

安全提示：只监听局域网、只提供 APK 下载页，不带目录列表；用完 Ctrl+C 关掉。
"""

import argparse
import http.server
import socket
import socketserver
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APK_DIR = ROOT.parent / "shiyang-app5" / "unpackage" / "release" / "apk"

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>食养有据 · 安装包下载</title>
<style>
 body{{margin:0;font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;
      background:#f4f7f5;color:#1f2d26;display:flex;min-height:100vh;
      align-items:center;justify-content:center;padding:24px}}
 .card{{background:#fff;border-radius:16px;padding:28px 24px;max-width:420px;width:100%;
        box-shadow:0 4px 24px rgba(45,106,79,.12)}}
 h1{{font-size:19px;margin:0 0 6px}}
 p{{font-size:13px;line-height:1.7;color:#5a6b62;margin:0 0 18px}}
 a.btn{{display:block;text-align:center;background:#2d6a4f;color:#fff;text-decoration:none;
        padding:14px;border-radius:10px;font-size:16px;font-weight:600}}
 a.btn:active{{background:#245741}}
 .meta{{margin-top:14px;font-size:12px;color:#8a9a92;text-align:center}}
 .warn{{margin-top:16px;padding:10px 12px;background:#fff8e6;border-radius:8px;
        font-size:12px;line-height:1.6;color:#8a6d1f}}
</style></head>
<body><div class="card">
 <h1>食养有据 · Android 安装包</h1>
 <p>药食同源食疗·茶饮有效成分分析平台</p>
 <a class="btn" href="/{name}" download>下载 APK（{size}）</a>
 <div class="meta">{name}</div>
 <div class="warn">安装时若提示"未知来源"，在系统设置里允许浏览器安装应用即可。
 本平台内容为健康参考信息，不构成医疗建议。</div>
</div></body></html>
"""


def lan_ip():
    """挑一个手机能连到的地址：优先普通 WLAN/以太网。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | "
             "ForEach-Object { $_.IPAddress + '|' + $_.InterfaceAlias }"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        ).stdout
        cands = []
        for line in out.strip().splitlines():
            if "|" not in line:
                continue
            ip, alias = (s.strip() for s in line.split("|", 1))
            if "Tailscale" in alias or "vEthernet" in alias or "Hyper-V" in alias:
                continue
            if ip.startswith("192.168.137."):
                continue
            cands.append(ip)
        if cands:
            return cands[0]
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def latest_apk():
    if not APK_DIR.exists():
        return None
    apks = sorted(APK_DIR.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
    return apks[0] if apks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8200)
    args = ap.parse_args()

    apk = latest_apk()
    if not apk:
        raise SystemExit(f"没找到 APK，先打包：{APK_DIR}")

    size = f"{apk.stat().st_size / 1048576:.1f} MB"
    page = PAGE.format(name=apk.name, size=size).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return
            if self.path == f"/{apk.name}":
                data = apk.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Disposition", f'attachment; filename="{apk.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                print(f"  ← 已发送 {len(data) / 1048576:.1f} MB")
                return
            self.send_error(404)

        def log_message(self, fmt, *a):
            print(f"  [{self.address_string()}] {fmt % a}")

    ip = lan_ip()
    print("=" * 60)
    print(" 手机下载地址（手机与本机需连同一 WiFi）")
    print(f"   http://{ip}:{args.port}/")
    print(f" 文件：{apk.name}（{size}）")
    print(" 用完按 Ctrl+C 停止")
    print("=" * 60)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", args.port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
