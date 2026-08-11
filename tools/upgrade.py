"""一键进化脚本：导入新书 → 切块 → 重建向量索引 → 重启 bot。

用法：
  uv run python tools/upgrade.py            # 完整流程（导入+切块+索引+重启）
  uv run python tools/upgrade.py --no-import # 跳过导入（只切块+索引+重启，比如改了 persona 后）
  uv run python tools/upgrade.py --no-restart # 只重建知识库，不重启 bot

说明：
  - 导入：遍历 importer/ 下未导入过的 EPUB（幂等，靠 imported_books.txt）
  - 切块：rag/chunk.py
  - 索引：rag/build_index.py（全量重建 Chroma 集合 ikeda）
  - 重启：结束旧 bot 进程，启动新 bot/run.py（单实例，依赖 bot_running.lock）
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
import config as C

VENV_PY = PROJ / ".venv" / "Scripts" / "python.exe"
VENV_SP = PROJ / ".venv" / "Lib" / "site-packages"


def _run_module(modpath: str, extra=None):
    """用 venv python 跑一个 .py 模块（其 __main__ 会执行）。"""
    cmd = [str(VENV_PY), modpath] + (extra or [])
    env = dict(os.environ)
    env["DATA_DIR"] = str(C.DATA_DIR)
    env["PYTHONPATH"] = os.pathsep.join([str(PROJ), str(VENV_SP)])
    print(f"\n>>> 运行 {modpath} ...")
    r = subprocess.run(cmd, cwd=str(PROJ), env=env, check=False)
    if r.returncode != 0:
        raise SystemExit(f"{modpath} 失败，退出码 {r.returncode}")


def _kill_bot():
    """结束所有 bot/run.py 进程（含 uv worker）。用 taskkill（Windows 自带，不依赖 psutil）。"""
    # 先用 wmic 找出 bot/run.py 的 pid
    out = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True,
    ).stdout
    pids = []
    for line in out.splitlines():
        if "bot/run.py" in line:
            # commandline 末尾是 pid
            parts = line.split()
            if parts:
                try:
                    pids.append(int(parts[-1]))
                except ValueError:
                    pass
    # 也用 taskkill 模糊匹配（按镜像名+命令行无法直接过滤，故用 pid）
    for pid in set(pids):
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)
    if pids:
        print(f"  已结束旧 bot 进程: {sorted(set(pids))}")
        time.sleep(2)
    # 清掉可能残留的锁（进程已死，pid 文件无意义）
    lock = PROJ / "bot.pid"
    if lock.exists():
        try:
            lock.unlink()
        except Exception:
            pass


def _launch_bot():
    log = open(PROJ / "bot_launch.log", "w")
    env = dict(os.environ)
    # 排除 Hermes 自身 venv 的路径注入，避免 ai-shisho 的 bot 误用 hermes 的包
    # （tokenizers/PIL 等版本冲突曾导致 bot 起不来）
    for k in list(env):
        if "hermes" in env[k].lower():
            env.pop(k)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["DATA_DIR"] = str(C.DATA_DIR)
    env["PYTHONPATH"] = os.pathsep.join([str(PROJ), str(VENV_SP)])
    p = subprocess.Popen(
        [str(VENV_PY), "bot/run.py"],
        cwd=str(PROJ),
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    print(f"  已启动新 bot（pid {p.pid}）")
    time.sleep(10)
    # 用 wmic 确认 bot/run.py 进程数（不依赖 psutil）
    out = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True,
    ).stdout
    procs = [ln for ln in out.splitlines() if "bot/run.py" in ln]
    print(f"  当前 bot/run.py 进程: {procs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-import", action="store_true", help="跳过导入新书")
    ap.add_argument("--no-restart", action="store_true", help="重建索引后不重启 bot")
    args = ap.parse_args()

    if not args.no_import:
        # 1) 导入新书（幂等）
        _run_module(str(PROJ / "importer" / "import_books.py"))

    # 2) 切块
    _run_module(str(PROJ / "rag" / "chunk.py"))

    # 3) 重建索引
    _run_module(str(PROJ / "rag" / "build_index.py"))

    if not args.no_restart:
        # 4) 重启 bot
        print("\n>>> 重启 bot ...")
        _kill_bot()
        _launch_bot()

    print("\n✅ 进化完成。")


if __name__ == "__main__":
    main()
