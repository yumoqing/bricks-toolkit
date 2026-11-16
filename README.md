# bricks-toolkit — bricks 前端的 Windows 原生工具包

把 bricks 的构建/预览/挂载从 bash 脚本改成 Windows 原生实现：不需要 git-bash、不需要 `cat`/`cp -a`/`ln -s`，
纯 Python 标准库（`bricks.exe` 由 venv 提供）。

## 为什么

`bricks/bricks/build.sh` 用 `cat SOURCES > dist/bricks.js` + `cp -a` 拼装 dist，Windows 上要靠 git-bash；
仓库里那份 `build.cmd` 的源清单停在 29 个文件（`build.sh` 已经是 93 个），用它构建会得到**残缺的 bricks.js**。
本工具包以 `build.sh` 的 `SOURCES="..."` 为唯一事实源，产出与 bash 构建**逐字节一致**的 dist。

## 安装

```bat
python -m venv %LOCALAPPDATA%\hermes\vendor\bricks-toolkit\venv
%LOCALAPPDATA%\hermes\vendor\bricks-toolkit\venv\Scripts\python.exe -m pip install -e D:\work\repos\bricks-toolkit
```

（本机已装好，并把 `bricks.cmd` 放进 `D:\hermes\hermes-agent\.hermes\bin`，在 PATH 上。）

## 用法

```bat
bricks build  --repo D:\work\repos\bricks            :: 拼 dist（等价 build.sh）
bricks build  --repo D:\work\repos\bricks --clean --check --strict
bricks doctor --repo D:\work\repos\bricks            :: 体检：源清单/缺文件/dist 新鲜度/模板/旧 build.cmd 漂移
bricks serve  --repo D:\work\repos\bricks --port 8080 --bind 0.0.0.0
bricks link   D:\work\myapp                          :: 建 junction wwwroot\bricks -> <repo>\dist
bricks link   D:\work\myapp --force                  :: 覆盖指向别处的旧链接
bricks unlink D:\work\myapp
bricks --version
```

在仓库目录里可以省略 `--repo`（向上自动查找 `<root>/bricks/build.sh`）。

## 命令与实现

| 命令 | 做什么 | 与 bash 版的对应 |
|---|---|---|
| `build` | 按 `build.sh` 的 SOURCES 顺序逐字节拼接 `dist/bricks.js`；复制 `css imgs examples 3parties docs i18n *.tmpl` | `bricks/build.sh` 的 `cat` + `cp -a` |
| `build --clean` | 构建前清空 dist（避免删源后残留旧文件） | bash 版没有，建议加上 |
| `build --check` | `node --check dist/bricks.js` 语法自检 | 无 |
| `doctor` | 源清单解析、缺文件、dist 是否落后于源码、模板缺失、`build.cmd` 漂移、node 是否存在 | 无 |
| `serve` | 禁缓存静态服务器，本机/局域网预览 dist | 原 workflow 靠部署到服务器看页面 |
| `link` | Windows 目录 junction（`mklink /J`，无需管理员、可跨盘）；POSIX 用符号链接 | `ln -sf ../pkgs/bricks/dist wwwroot/bricks` |

## 与部署流程的衔接

部署规范里 bricks 那一步原本是「进模块 → mkdir dist → bash build.sh → ln -sfn dist wwwroot/bricks」，
Windows 上改成：

```bat
bricks build --repo <bricks 仓库> --clean
bricks link  <应用根目录>
```

Linux 部署机仍走原 `build.sh`（或把本工具包装进去用 `python -m bricks_toolkit.cli build`），两条路产物一致。

## 验证口径（本机实测）

```bat
bash build.sh                       :: 参考产物
bricks build --clean                :: 本工具产物
```
两者 `dist/` 比对：**738 个文件、0 字节差异**，`bricks.js` 均为 621592 字节，sha256 `81ed0029…`。
另外验证了 `serve`（HTTP 200 取到 bricks.js 与 3parties 资源）、`link`（junction 建立/幂等/可读/可 unlink）。

## 已知边界

- 源清单只认 `build.sh`：如果哪天 SOURCES 移到别处，`doctor` 会直接报错而不是猜。
- 不处理 `.min.js` 压缩（原 build.sh 里 uglify 那行是注释掉的），需要压缩自行接 uglify/esbuild。
- `link` 在 Windows 上建的是 junction（同盘跨盘都行），不是符号链接；删除要用 `bricks unlink` 或 `rmdir`，`rm -rf` 语义不同。