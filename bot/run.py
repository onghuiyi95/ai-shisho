"""Telegram Bot：AI 师匠。
命令：
  /start    欢迎
  /about    师匠是谁 / 知识库范围
  /source   切换是否显示引用来源链接
  /teach    教/纠正师匠：/teach <你的教导或反馈>  → 全局生效，注入后续对话
  /forget   收起当前对话记忆（前端"像忘了"，存档仍留 DB 供维护查阅）
  /wipe     彻底删除本聊天全部历史存档（慎用，仅维护用）
  /daily    今日一句（默认中文；/daily en 返回英文 Daily Encouragement）
用法： uv run python bot/run.py   （需先填 .env 的 TELEGRAM_BOT_TOKEN）
"""
# === 环境隔离加固：在任何第三方 import 前，剥离 Hermes/uv 污染，但保留标准库 ===
import sys
import os

_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENV_SP = os.path.join(_PROJ_ROOT, ".venv", "Lib", "site-packages")
# 1) 只删含 hermes / uv/python 的污染路径（保留标准库、venv、项目）
sys.path = [p for p in sys.path if not ("hermes" in p.lower() or "uv/python" in p.lower())]
# 2) 确保 venv site-packages 与项目根在最前
if _VENV_SP not in sys.path:
    sys.path.insert(0, _VENV_SP)
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)
# 3) 清环境变量污染
for _k in list(os.environ):
    if "hermes" in os.environ[_k].lower():
        os.environ.pop(_k, None)
os.environ.pop("PYTHONPATH", None)
os.environ.pop("PYTHONHOME", None)
os.environ["PYTHONPATH"] = os.pathsep.join([_PROJ_ROOT, _VENV_SP])

import asyncio
import json
import time

# 确保项目根目录在 sys.path 中（无论以 `python bot/run.py`、`uv run` 还是
# upgrade.py 子进程方式启动，都能正确 import config / generator 等模块）
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config as C
from generator.shisho import Shisho
from generator import memory_store as mem

shisho = Shisho()
INCLUDE_SOURCE = True  # 默认带来源；可用 /source 切换

_LOCK_PATH = C.BASE / "bot.pid"


def _kill_other_bots(me):
    """用 wmic 列出所有 python.exe 的命令行，杀掉命令行含 'bot/run.py' 且 pid != me 的进程。
    不依赖 psutil（在 Windows + detached/uv 子进程下 import 会失败）。"""
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


def _acquire_lock():
    """单实例（自清理，Windows + uv 环境兼容）：
    启动时杀掉所有「其他」bot/run.py 进程（排除自己），
    确保全局只有一个 bot 在 polling，避免抢同一 Telegram token。
    然后写入自己的 pid 文件。使用 wmic/taskkill（不依赖 psutil）。"""
    me = os.getpid()
    _kill_other_bots(me)
    _LOCK_PATH.write_text(str(me))
    return True


def _debug(chat_id, hist_len, msg, phase=""):
    try:
        with open(C.BASE / "bot_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[chat] pid={os.getpid()} chat={chat_id} hist_len={hist_len} {phase}msg={msg!r}\n")
    except Exception:
        pass


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "我是「AI 师匠」。\n"
        "我把池田大作先生（1928–2023）的箴言、随笔、对谈与生平，"
        "汇成一座小小的知识库，再以他温暖人本的精神与你对话。\n\n"
        "有什么在心里盘桓的事，尽管说吧——关于人生、低谷、青年、希望、和平，都可以。\n"
        "命令：/about 了解我 ｜ /source 切换引用来源 ｜ /teach 教我一点 ｜ /forget 收起记忆 ｜ /wipe 彻底清除 ｜ /daily 今日一句(可加 en)"
    )


async def about(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "【AI 师匠】\n"
        "以池田大作的思想内核与语言风格行事的对话导师。\n"
        "不是宗教权威，而是人本主义精神与温暖陪伴的承载者。\n\n"
        f"知识库说明：{C.KB_SCOPE_NOTE}\n"
        "底层：本地 Chroma 向量检索 + Cloudflare Workers AI 生成。"
    )


async def toggle_source(update: Update, _: ContextTypes.DEFAULT_TYPE):
    global INCLUDE_SOURCE
    INCLUDE_SOURCE = not INCLUDE_SOURCE
    await update.message.reply_text(f"引用来源显示：{'开' if INCLUDE_SOURCE else '关'}")


async def teach(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/teach", "", 1).strip()
    if not text:
        await update.message.reply_text(
            "用法：/teach <你对师匠的教导或反馈>\n"
            "例如：/teach 回答要简短，不要长篇大论\n"
            "例如：/teach 第一次见面不要说教，像朋友寒暄就好"
        )
        return
    tid = mem.add_teaching(text)
    await update.message.reply_text(f"记下了（第 {tid} 条教导）。以后我会照此与你相处。")


_QUOTES_CACHE = None


def _load_quotes():
    global _QUOTES_CACHE
    if _QUOTES_CACHE is None:
        qp = C.BASE / "data" / "daily_quotes" / "quotes.json"
        if qp.exists():
            import json as _json
            _QUOTES_CACHE = _json.loads(qp.read_text(encoding="utf-8"))
        else:
            _QUOTES_CACHE = []
    return _QUOTES_CACHE


async def daily(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """今日一句。默认中文（encouragements）；/daily en 返回英文 Daily Encouragement。"""
    arg = update.message.text.replace("/daily", "", 1).strip().lower()
    quotes = _load_quotes()
    now = time.localtime()
    if arg == "en":
        en_path = C.BASE / "data" / "daily_quotes" / "daily_encouragement_en.json"
        if not en_path.exists() or not quotes:
            await update.message.reply_text("每日英文鼓励库尚未就绪。")
            return
        en = json.loads(en_path.read_text(encoding="utf-8"))
        hit = next((q for q in en if q["month"] == now.tm_mon and q["day"] == now.tm_mday), None)
        if not hit:
            await update.message.reply_text("今天没有对应的每日鼓励，但师匠想对你说：\n" + en[0]["text"])
            return
        src = f"\n— {hit['source']}" if hit.get("source") else ""
        await update.message.reply_text(
            f"【Daily Encouragement】{hit['month']}/{hit['day']}\n\n{hit['text']}{src}"
        )
        return
    # 默认中文
    if not quotes:
        await update.message.reply_text("每日一句库尚未就绪，请先导入。")
        return
    hit = next((q for q in quotes if q["month"] == now.tm_mon and q["day"] == now.tm_mday), None)
    if not hit:
        await update.message.reply_text("今天没有对应的每日一句，但师匠想对你说：\n" + quotes[0]["text"])
        return
    await update.message.reply_text(
        f"【每日一句】{hit['month']}月{hit['day']}日\n\n{hit['text']}"
    )


async def forget(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    mem.forget_active(cid)
    await update.message.reply_text(
        "好的，我们之间的对话记忆已收起——往前的聊天从眼前淡去了，我们从头聊起吧。\n"
        "（注：这些内容仍存档在数据库里供维护查阅，并未真正删除；如需彻底清除请用 /wipe。）"
    )


async def wipe(update: Update, _: ContextTypes.DEFAULT_TYPE):
    cid = str(update.effective_chat.id)
    mem.clear_all(cid)
    await update.message.reply_text("已彻底清除我们之间的全部对话存档（含历史留档）。")


async def chat(update: Update, _: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    if not user_msg:
        return
    cid = str(update.effective_chat.id)
    history = mem.load_history(cid)
    _debug(cid, len(history), user_msg, phase="in ")

    wait = await update.message.reply_text("师匠正在倾听……")
    try:
        reply = await asyncio.to_thread(shisho.answer, user_msg, chat_id=cid)
    except Exception as e:
        reply = f"方才有些迟滞（{e}）。朋友，请再对我说一次你的心里话。"
    # 持久化历史
    mem.append_turn(cid, "user", user_msg)
    mem.append_turn(cid, "assistant", reply)
    _debug(cid, len(mem.load_history(cid)), user_msg, phase="out ")

    # 长消息分包
    MAX = 4000
    parts = [reply[i:i + MAX] for i in range(0, len(reply), MAX)]
    await wait.delete()
    for p in parts:
        await update.message.reply_text(p)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    from telegram.error import Conflict
    err = context.error
    if isinstance(err, Conflict):
        # 另一个实例/探测抢了 getUpdates 流：忽略，polling 会自动恢复重连
        return
    import traceback
    print("Bot error:", repr(err))
    traceback.print_exception(type(err), err, err.__traceback__)


def main():
    lock_fd = _acquire_lock()  # 占位，持有至进程结束
    if not C.TELEGRAM_BOT_TOKEN:
        raise SystemExit("请先在 .env 填入 TELEGRAM_BOT_TOKEN（从 @BotFather 获取）")
    app = Application.builder().token(C.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("source", toggle_source))
    app.add_handler(CommandHandler("teach", teach))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("forget", forget))
    app.add_handler(CommandHandler("wipe", wipe))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_error_handler(error_handler)
    print("AI 师匠 Bot 启动中……")
    app.run_polling()


if __name__ == "__main__":
    main()
