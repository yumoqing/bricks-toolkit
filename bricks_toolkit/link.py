"""应用 wwwroot 挂载：把 bricks 的 dist 接到应用 wwwroot/bricks。

Windows 用目录 junction（mklink /J，无需管理员、跨盘可用），Linux/macOS 用符号链接。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _is_windows() -> bool:
    return os.name == "nt"


def is_junction(path: str) -> bool:
    if not _is_windows() or not os.path.isdir(path):
        return False
    try:
        p = subprocess.run(["cmd", "/c", "dir", "/a:l", os.path.dirname(os.path.abspath(path))],
                           capture_output=True, text=True, encoding="mbcs", errors="replace")
    except OSError:
        return False
    return os.path.basename(os.path.abspath(path)).upper() in (p.stdout or "").upper() and "<JUNCTION>" in (p.stdout or "").upper()


def readlink(path: str) -> str:
    try:
        return os.path.realpath(path)
    except OSError:
        return ""


def link(app_root: str, target: str, name: str = "bricks", force: bool = False, log=print) -> dict:
    """在 <app_root>/wwwroot/<name> 建指向 target 的链接。返回 {ok, link, target, note}。"""
    app_root = os.path.abspath(app_root)
    target = os.path.abspath(target)
    wwwroot = os.path.join(app_root, "wwwroot")
    link_path = os.path.join(wwwroot, name)

    if not os.path.isdir(target):
        raise FileNotFoundError("目标目录不存在：%s（先跑 bricks build）" % target)
    if not os.path.isdir(app_root):
        raise FileNotFoundError("应用根目录不存在：%s" % app_root)
    os.makedirs(wwwroot, exist_ok=True)

    if os.path.lexists(link_path):
        current = os.path.realpath(link_path)
        if os.path.normcase(current) == os.path.normcase(os.path.realpath(target)):
            return {"ok": True, "link": link_path, "target": target, "note": "已存在且指向同一目标（未改动）"}
        if not force:
            raise FileExistsError("%s 已存在且指向 %s；加 --force 覆盖" % (link_path, current))
        if os.path.isdir(link_path) and not os.path.islink(link_path):
            shutil.rmtree(link_path)          # junction/普通目录
        else:
            os.unlink(link_path)

    if _is_windows():
        p = subprocess.run(["cmd", "/c", "mklink", "/J", link_path, target],
                           capture_output=True, text=True, encoding="mbcs", errors="replace")
        if p.returncode != 0:
            raise OSError("mklink /J 失败：%s" % ((p.stdout or "") + (p.stderr or "")).strip()[:300])
        note = "已建目录 junction（mklink /J）"
    else:
        os.symlink(target, link_path, target_is_directory=True)
        note = "已建符号链接"

    ok = os.path.isfile(os.path.join(link_path, "bricks.js"))
    log("[bricks link] %s -> %s" % (link_path, target))
    log("[bricks link] %s" % note)
    if not ok:
        log("[bricks link] 警告：链接下没有 bricks.js，检查 dist 是否构建过")
    return {"ok": ok, "link": link_path, "target": target, "note": note}


def unlink(app_root: str, name: str = "bricks", log=print) -> bool:
    link_path = os.path.join(os.path.abspath(app_root), "wwwroot", name)
    if not os.path.lexists(link_path):
        log("[bricks unlink] 不存在：%s" % link_path)
        return False
    if os.path.isdir(link_path) and not os.path.islink(link_path):
        os.rmdir(link_path)                   # junction 只能 rmdir
    else:
        os.unlink(link_path)
    log("[bricks unlink] 已移除 %s" % link_path)
    return True