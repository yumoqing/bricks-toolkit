"""CI 冒烟：起 bricks serve，确认能取到 dist/bricks.js。

用法：python tests/ci_serve.py [--repo _bricks] [--port 8123]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="_bricks")
    ap.add_argument("--port", type=int, default=8123)
    a = ap.parse_args()

    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "serve.log")
    log = open(log_path, "wb")
    p = subprocess.Popen([sys.executable, "-m", "bricks_toolkit.cli", "serve",
                          "--repo", a.repo, "--dir", os.path.join(a.repo, "dist"),
                          "--port", str(a.port)], stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/bricks.js" % a.port, timeout=3) as r:
                    body = r.read()
                    print("serve 返回 %s，%d 字节" % (r.status, len(body)))
                    return 0 if (r.status == 200 and len(body) > 500000) else 1
            except Exception:            # noqa: BLE001
                continue
        print("serve 超时")
        return 1
    finally:
        p.terminate()
        log.close()
        try:
            p.wait(timeout=10)
        except Exception:                # noqa: BLE001
            p.kill()


if __name__ == "__main__":
    sys.exit(main())
