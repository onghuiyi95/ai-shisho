"""彻底干净的 bot 启动器：
1. 杀掉所有 bot/run.py 进程（不论 python 来源：venv / uv / hermes）
2. 用项目 venv 的 python 启动唯一一个 run.py，env 完全剥离 Hermes 污染
3. 等待并验证单实例
"""
import os
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join(PROJ, ".venv", "Scripts", "python.exe")


def kill_all_bots():
    out = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore",
    ).stdout
    killed = []
    for line in out.splitlines():
        if "bot/run.py" in line and line.split():
            pid = line.split()[-1]
            try:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                killed.append(pid)
            except Exception:
                pass
    if killed:
        time.sleep(2)
    return killed


def clean_env():
    env = dict(os.environ)
    for k in list(env):
        if "hermes" in env[k].lower():
            env.pop(k)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONPATH"] = os.pathsep.join([PROJ, os.path.join(PROJ, ".venv", "Lib", "site-packages")])
    env["DATA_DIR"] = os.path.join(PROJ, "data")
    return env


def main():
    print("1) 杀掉所有旧 bot:", kill_all_bots())
    env = clean_env()
    # 用 venv python 直接起 run.py（不经 launch_bot，排除二次包装）
    p = subprocess.Popen(
        [VENV_PY, "-u", "bot/run.py"],
        cwd=PROJ,
        env=env,
        stdout=open(os.path.join(PROJ, "bot_clean.log"), "w"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    print(f"2) 启动 venv run.py pid={p.pid}")
    time.sleep(8)
    # 验证单实例（只数 venv 来源的 run.py）
    out = subprocess.run(
        ["wmic", "process", "where", "name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True,
    ).stdout
    venv_procs = [l.split()[-1] for l in out.splitlines()
                  if "bot/run.py" in l and "ai-shisho/.venv" in l.replace("\\", "/")]
    print(f"3) venv run.py 实例: {venv_procs} -> {'OK 单实例' if len(venv_procs)==1 else 'BUG'}")
    ns = subprocess.run(["netstat", "-an"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    print(f"4) Telegram 连接: {'已连接' if ('149.154' in ns and 'ESTABLISHED' in ns) else '未连接'}")


if __name__ == "__main__":
    main()
