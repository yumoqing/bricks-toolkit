"""bricks 前端工具包（Windows 原生实现，不依赖 bash）。

模块：
  build   构建 dist（与 bricks/bricks/build.sh 同一口径）
  serve   本地静态预览
  link    应用 wwwroot 挂载（Windows 目录 junction）
  cli     命令行入口
"""

__version__ = "1.0.0"
__all__ = ["__version__"]