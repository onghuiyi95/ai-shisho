"""AI 师匠 — 统一命令行入口。
uv run python main.py scrape      # 抓取
uv run python main.py chunk       # 切分
uv run python main.py index       # 建向量索引
uv run python main.py ask "问题"   # 单条问答（本地测试）
uv run python main.py bot         # 启动 Telegram bot
"""
import sys
import os
import subprocess
import config as C

# 项目虚拟环境的 python 解释器与 site-packages（确保优先于 Hermes 自带环境，
# 避免 tokenizers 等依赖版本冲突）
_PROJ_PY = C.BASE / ".venv" / "Scripts" / "python.exe"
_PROJ_SP = C.BASE / ".venv" / "Lib" / "site-packages"


def run(module: str):
    env = dict(os.environ)
    # 项目根（找 config 模块）+ 项目 site-packages（优先依赖）一并置顶
    env["PYTHONPATH"] = os.pathsep.join([str(C.BASE), str(_PROJ_SP)])
    py = str(_PROJ_PY) if _PROJ_PY.exists() else sys.executable
    return subprocess.run([py, module], cwd=C.BASE, env=env)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "scrape":
        run("scraper/fetch.py")
    elif cmd == "chunk":
        run("rag/chunk.py")
    elif cmd == "index":
        run("rag/build_index.py")
    elif cmd == "ask":
        q = " ".join(args[1:]) or "青年应该如何面对失败？"
        from generator.shisho import Shisho
        print(Shisho().answer(q))
    elif cmd == "bot":
        run("bot/run.py")
    else:
        print("未知命令。可用：scrape / chunk / index / ask / bot")


if __name__ == "__main__":
    main()
