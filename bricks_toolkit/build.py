"""bricks 构建核心（Windows 原生，不依赖 bash/cat/cp）。

与 bricks/bricks/build.sh 保持同一口径：
  1. 按 build.sh 里 SOURCES="..." 的**顺序**把源文件逐字节拼成 dist/bricks.js
  2. 把 css/ imgs/ examples/ 3parties/ docs/ i18n/ 与 *.tmpl 复制进 dist/
源文件清单只认 build.sh（唯一事实源）；build.cmd 里的旧清单是历史包袱，doctor 会提示漂移。
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import time

DIST_DIRNAME = "dist"


def find_repo_root(start: str = ".") -> str:
    """向上找包含 bricks/build.sh 的目录；返回绝对路径，找不到抛 FileNotFoundError。"""
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, "bricks", "build.sh")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise FileNotFoundError(
                "没找到 bricks 仓库根（需要 <root>/bricks/build.sh）：从 %s 向上都没找到" % os.path.abspath(start))
        cur = parent


def parse_sources(build_sh_path: str) -> list:
    """从 build.sh 的 SOURCES="..." 解析源文件顺序（处理 \\ 续行、tab、多余空白）。"""
    with open(build_sh_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    m = re.search(r'SOURCES="([^"]*)"', text, re.S)
    if not m:
        raise ValueError("%s 里没有 SOURCES=\"...\" 定义，无法确定源文件顺序" % build_sh_path)
    raw = m.group(1).replace("\\\r\n", " ").replace("\\\n", " ").replace("\\\r", " ")
    return raw.split()


def parse_cmd_sources(build_cmd_path: str) -> list:
    """解析旧 build.cmd 的 set SOURCES=（仅用于漂移提示）。"""
    try:
        with open(build_cmd_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []
    m = re.search(r"set\s+SOURCES=([^\r\n]*)", text, re.I)
    return m.group(1).split() if m else []


def _copy_tree(src: str, dst: str) -> int:
    """等价 cp -a src/* dst/：递归复制内容，覆盖同名文件。返回复制文件数。"""
    n = 0
    os.makedirs(dst, exist_ok=True)
    for base, _dirs, files in os.walk(src):
        rel = os.path.relpath(base, src)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(base, f), os.path.join(target, f))
            n += 1
    return n


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(repo: str, clean: bool = False, check: bool = False, log=print) -> dict:
    """构建 dist。返回 {ok, dist, sources, js_bytes, sha256, copied, missing, warnings}。"""
    repo = os.path.abspath(repo)
    src_dir = os.path.join(repo, "bricks")
    dist = os.path.join(repo, DIST_DIRNAME)
    build_sh = os.path.join(src_dir, "build.sh")

    sources = parse_sources(build_sh)
    missing = [s for s in sources if not os.path.isfile(os.path.join(src_dir, s))]
    if missing:
        raise FileNotFoundError("build.sh 声明的源文件缺失 %d 个：%s" % (len(missing), ", ".join(missing[:8])))

    if clean and os.path.isdir(dist):
        shutil.rmtree(dist)
        log("[bricks] clean: 删除旧 dist")
    os.makedirs(dist, exist_ok=True)

    # 1) 拼接 bricks.js（逐字节，顺序同 build.sh）
    out_js = os.path.join(dist, "bricks.js")
    total = 0
    with open(out_js, "wb") as out:
        for name in sources:
            path = os.path.join(src_dir, name)
            with open(path, "rb") as fh:
                data = fh.read()
            out.write(data)
            total += len(data)
    log("[bricks] bricks.js: %d 个源文件 -> %d 字节" % (len(sources), total))

    # 2) 静态资产（同 build.sh 的 cp -a 顺序）
    copied = 0
    warnings = []
    plan = [
        (os.path.join(src_dir, "css"), os.path.join(dist, "css"), True),
        (os.path.join(src_dir, "imgs"), os.path.join(dist, "imgs"), True),
        (os.path.join(repo, "examples"), os.path.join(dist, "examples"), True),
        (os.path.join(repo, "3parties"), os.path.join(dist, "3parties"), True),
        (os.path.join(repo, "docs"), os.path.join(dist, "docs"), True),
        (os.path.join(repo, "i18n"), os.path.join(dist, "i18n"), True),
    ]
    for src, dst, required in plan:
        if not os.path.isdir(src):
            if required:
                warnings.append("缺目录：%s（build.sh 里会 cp 失败）" % src)
            continue
        n = _copy_tree(src, dst)
        copied += n
        log("[bricks] %-9s -> dist/%-9s %d 个文件" % (os.path.basename(src), os.path.basename(dst), n))

    # 3) *.tmpl 直接放 dist 根
    tmpl = [f for f in os.listdir(src_dir) if f.endswith(".tmpl")]
    for f in tmpl:
        shutil.copy2(os.path.join(src_dir, f), os.path.join(dist, f))
    if not tmpl:
        warnings.append("bricks/ 下没有 *.tmpl（header/footer 模板缺失时页面会 500）")
    copied += len(tmpl)
    log("[bricks] tmpl: %s" % (", ".join(tmpl) or "(无)"))

    # 4) 完整性自检
    if total < 200_000:
        warnings.append("bricks.js 只有 %d 字节，明显偏小（正常 ~550KB），源清单可能不全" % total)
    if check:
        node = shutil.which("node")
        if node:
            import subprocess
            p = subprocess.run([node, "--check", out_js], capture_output=True, text=True)
            if p.returncode != 0:
                warnings.append("node --check 失败：%s" % (p.stderr or p.stdout).strip()[:300])
                log("[bricks] node --check FAILED")
            else:
                log("[bricks] node --check 通过")
        else:
            warnings.append("没有 node，跳过语法自检")

    # 5) 旧 build.cmd 漂移提示
    cmd = os.path.join(src_dir, "build.cmd")
    if os.path.isfile(cmd):
        old = parse_cmd_sources(cmd)
        if old and old != sources:
            warnings.append("build.cmd 的 SOURCES 已过期（%d 个 vs build.sh %d 个）——别用它构建，用 `bricks build`"
                            % (len(old), len(sources)))

    return {
        "ok": not warnings,
        "dist": dist,
        "sources": len(sources),
        "js_bytes": total,
        "sha256": _sha256(out_js),
        "copied": copied,
        "missing": missing,
        "warnings": warnings,
    }


def dist_status(repo: str) -> dict:
    """dist 现状：是否存在、bricks.js 大小/哈希、比最新源文件新还是旧。"""
    repo = os.path.abspath(repo)
    dist = os.path.join(repo, DIST_DIRNAME)
    js = os.path.join(dist, "bricks.js")
    if not os.path.isfile(js):
        return {"exists": False, "stale": True, "reason": "dist/bricks.js 不存在"}
    newest_src, newest_name = 0.0, ""
    for base, _d, files in os.walk(os.path.join(repo, "bricks")):
        for f in files:
            p = os.path.join(base, f)
            m = os.path.getmtime(p)
            if m > newest_src:
                newest_src, newest_name = m, os.path.relpath(p, repo)
    js_m = os.path.getmtime(js)
    files = sum(len(f) for _, _, f in os.walk(dist))
    return {
        "exists": True,
        "dist": dist,
        "js_bytes": os.path.getsize(js),
        "sha256": _sha256(js),
        "files": files,
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(js_m)),
        "stale": newest_src > js_m + 1,
        "newest_source": newest_name,
        "newest_source_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest_src)) if newest_src else "",
    }