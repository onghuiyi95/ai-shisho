"""以干净环境启动 AI 师匠 bot：剥离 Hermes 注入的 PYTHONPATH / venv 路径污染，
确保 bot 使用本项目 .venv 的自洽依赖（tokenizers 0.22.2 等），避免导入冲突崩溃。
用法： uv run python tools/launch_bot.py   （或 .venv/Scripts/python.exe tools/launch_bot.py）
"""
import os
import sys
import time
import subprocess

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(PROJ, ".venv", "Scripts", "python.exe")
LOG = os.path.join(PROJ, "bot_launch.log")


def _kill_other_bots(me):
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
            capture_output=True, text=True,
        ).stdout
    except Exception:
        return
    pids = []
    for line in out.splitlines():
        if "bot/run.py" in line:
            parts = line.split()
            if parts:
                try:
                    pid = int(parts[-1])
                    if pid != me:
                        pids.append(pid)
                except ValueError:
                    pass
    for pid in set(pids):
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)
        except Exception:
            pass
    if pids:
        time.sleep(2)


def main():
    me = os.getpid()
    _kill_other_bots(me)

    # 干净环境：剥离所有可能指向 Hermes venv 的变量
    env = dict(os.environ)
    for k in list(env):
        if "hermes" in env[k].lower():
            env.pop(k)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["DATA_DIR"] = os.path.join(PROJ, "data")
    # 仅保留本项目 venv 的 site-packages
    env["PYTHONPATH"] = os.pathsep.join([
        PROJ,
        os.path.join(PROJ, ".venv", "Lib", "site-packages"),
    ])

    log = open(LOG, "w")
    p = subprocess.Popen(
        [VENV_PY, "-u", "bot/run.py"],
        cwd=PROJ,
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    print(f"已启动 bot（pid {p.pid}）-> {LOG}")


if __name__ == "__main__":
    main()
