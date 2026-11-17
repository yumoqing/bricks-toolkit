"""bricks 命令行入口。

  bricks build    [--repo DIR] [--clean] [--check]
  bricks doctor   [--repo DIR]
  bricks serve    [--repo DIR] [--dir DIR] [--port N] [--bind ADDR]
  bricks link     <app_root> [--repo DIR] [--name bricks] [--force]
  bricks unlink   <app_root> [--name bricks]
  bricks version
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .build import build, dist_status, find_repo_root, parse_cmd_sources, parse_sources
from .link import link, unlink


def _repo(args) -> str:
    return os.path.abspath(args.repo) if getattr(args, "repo", None) else find_repo_root(os.getcwd())


def cmd_build(args) -> int:
    repo = _repo(args)
    r = build(repo, clean=args.clean, check=args.check)
    print("[bricks] dist -> %s" % r["dist"])
    print("[bricks] bricks.js %d 字节  sha256=%s" % (r["js_bytes"], r["sha256"][:16]))
    for w in r["warnings"]:
        print("[bricks][WARN] %s" % w)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    print("[bricks] 构建完成（%d 源文件，%d 静态文件）" % (r["sources"], r["copied"]))
    return 0 if not args.strict or not r["warnings"] else 2


def cmd_doctor(args) -> int:
    repo = _repo(args)
    print("[bricks] 仓库 %s" % repo)
    st = dist_status(repo)
    problems = []
    src_dir = os.path.join(repo, "bricks")
    sources = parse_sources(os.path.join(src_dir, "build.sh"))
    missing = [s for s in sources if not os.path.isfile(os.path.join(src_dir, s))]
    print("[bricks] build.sh 源清单 %d 个；缺文件 %d 个" % (len(sources), len(missing)))
    if missing:
        problems.append("源文件缺失：%s" % ", ".join(missing[:8]))
    cmd = os.path.join(src_dir, "build.cmd")
    if os.path.isfile(cmd):
        old = parse_cmd_sources(cmd)
        if old and old != sources:
            problems.append("build.cmd 的 SOURCES 已过期（%d vs %d）——用 `bricks build`，别用 build.cmd"
                            % (len(old), len(sources)))
    for t in ("header.tmpl", "footer.tmpl"):
        if not os.path.isfile(os.path.join(src_dir, t)):
            problems.append("缺模板 %s" % t)
    if not st.get("exists"):
        problems.append(st.get("reason", "dist 不存在"))
        print("[bricks] dist：不存在")
    else:
        print("[bricks] dist：%d 个文件，bricks.js %d 字节，构建于 %s%s"
              % (st["files"], st["js_bytes"], st["mtime"], "（落后于源码）" if st["stale"] else ""))
        if st["stale"]:
            problems.append("dist 落后于源码（最新改动 %s @ %s）" % (st["newest_source"], st["newest_source_time"]))
        if st["js_bytes"] < 200_000:
            problems.append("bricks.js 只有 %d 字节，疑似缺源" % st["js_bytes"])
    if os.name != "nt":
        print("[bricks] 注意：当前不是 Windows，link 用符号链接")
    print("[bricks] node: %s" % ("有" if _which("node") else "无（跳过语法自检）"))
    if problems:
        print("[bricks] 发现 %d 个问题：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("[bricks] 体检通过")
    return 0


def cmd_serve(args) -> int:
    from .serve import serve
    repo = _repo(args)
    directory = os.path.abspath(args.dir) if args.dir else os.path.join(repo, "dist")
    serve(directory, port=args.port, bind=args.bind)
    return 0


def cmd_link(args) -> int:
    repo = _repo(args)
    target = os.path.abspath(args.dist) if args.dist else os.path.join(repo, "dist")
    r = link(args.app_root, target, name=args.name, force=args.force)
    return 0 if r["ok"] else 1


def cmd_unlink(args) -> int:
    return 0 if unlink(args.app_root, name=args.name) else 1


def _which(name: str):
    import shutil
    return shutil.which(name)


def _utf8_console() -> None:
    """Windows 老控制台默认 cp1252，打印中文/箭头会 UnicodeEncodeError；强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_console()
    ap = argparse.ArgumentParser(prog="bricks", description="bricks 前端 Windows 原生工具包")
    ap.add_argument("--version", action="version", version="bricks-toolkit %s" % __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="构建 dist（等价 bricks/build.sh，不依赖 bash）")
    p.add_argument("--repo", default=None, help="bricks 仓库根（默认向上查找）")
    p.add_argument("--clean", action="store_true", help="构建前清空 dist")
    p.add_argument("--check", action="store_true", help="用 node --check 校验 bricks.js 语法")
    p.add_argument("--strict", action="store_true", help="有警告即返回非 0")
    p.add_argument("--json", action="store_true", help="附带 JSON 结果")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("doctor", help="体检：源清单、dist 新鲜度、模板、旧 build.cmd 漂移")
    p.add_argument("--repo", default=None)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("serve", help="本地静态预览 dist/")
    p.add_argument("--repo", default=None)
    p.add_argument("--dir", default=None, help="要服务目录（默认 <repo>/dist）")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 时局域网可访问")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("link", help="把 dist 挂到应用 wwwroot/<name>（Windows junction）")
    p.add_argument("app_root")
    p.add_argument("--repo", default=None)
    p.add_argument("--dist", default=None, help="目标目录（默认 <repo>/dist）")
    p.add_argument("--name", default="bricks")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("unlink", help="移除 wwwroot/<name> 链接")
    p.add_argument("app_root")
    p.add_argument("--name", default="bricks")
    p.set_defaults(func=cmd_unlink)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, FileExistsError, OSError, ValueError) as e:
        print("[bricks][ERROR] %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())