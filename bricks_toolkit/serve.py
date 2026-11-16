"""本地静态预览：把 dist/（或任意目录）用 HTTP 起来，便于在 Windows 上直接看 bricks 页面。"""

from __future__ import annotations

import functools
import http.server
import os
import socket
import socketserver


class _Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 开发预览：禁缓存，改了 dist 刷新就生效
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("[bricks serve] %s - %s" % (self.address_string(), fmt % args))


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return ""


def serve(directory: str, port: int = 8080, bind: str = "127.0.0.1") -> None:
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        raise FileNotFoundError("目录不存在：%s" % directory)
    handler = functools.partial(_Handler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((bind, port), handler) as httpd:
        print("[bricks serve] 根目录 %s" % directory)
        print("[bricks serve] 本机  http://127.0.0.1:%d/" % port)
        lan = _lan_ip()
        if lan and bind not in ("127.0.0.1", "localhost"):
            print("[bricks serve] 局域网 http://%s:%d/" % (lan, port))
        print("[bricks serve] Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[bricks serve] 已停止")