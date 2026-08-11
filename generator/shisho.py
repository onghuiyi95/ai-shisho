"""生成层：检索 RAG 片段 + 调用 Cloudflare Workers AI 生成师匠式回复。"""
import json
import os
import time
from pathlib import Path

import requests

import config as C
from rag.retrieve import Retriever
from generator.realtime import detect_realtime, get_datetime, get_weather, _looks_like_place


def load_system_prompt() -> str:
    parts = []
    # 1) 池田认知操作系统（蒸馏自公开语料的五层框架，优先）
    skill = Path(__file__).resolve().parent.parent / "skills" / "ikeda-perspective" / "SKILL.md"
    if skill.exists():
        parts.append(skill.read_text(encoding="utf-8"))
    # 2) 陪伴基调 persona（暖意、身份、边界）
    if C.SYSTEM_PROMPT_FILE.exists():
        parts.append(C.SYSTEM_PROMPT_FILE.read_text(encoding="utf-8"))
    if not parts:
        return "你是 AI 师匠，以池田大作的精神与风格回应。"
    return "\n\n---\n\n".join(parts)


class Shisho:
    def __init__(self):
        self.retriever = Retriever()
        self.system_prompt = load_system_prompt()
        self._pending_weather = False  # 上一轮是否“问了天气但没给城市”

    def _format_context(self, hits) -> str:
        if not hits:
            return "（知识库暂无相关片段。）"
        lines = []
        for i, h in enumerate(hits, 1):
            lines.append(f"【片段 {i}｜来源：{h['title']}｜{h['url']}】\n{h['text']}")
        return "\n\n".join(lines)

    def _call_cf(self, messages) -> str:
        # 若有 LLM_BASE_URL（本地中转或远程 OpenAI 兼容后端），走 OpenAI 格式
        base_url = os.getenv("LLM_BASE_URL", "")
        if base_url:
            import requests as _req
            model = os.getenv("LLM_MODEL", "local-relay")
            api_key = os.getenv("LLM_API_KEY", "relay")
            url = base_url.rstrip("/") + "/chat/completions"
            last_err = None
            for attempt in range(3):
                try:
                    r = _req.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": model, "messages": messages, "max_tokens": 900, "temperature": 0.7,
                              "reasoning": {"enabled": False}},
                        timeout=120,
                    )
                    if r.status_code != 200:
                        last_err = f"LLM relay 错误 {r.status_code}: {r.text[:300]}"
                        if r.status_code == 429:
                            time.sleep(2 * (attempt + 1))  # 限流退避
                            continue
                        raise RuntimeError(last_err)
                    data = r.json()
                    try:
                        content = data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError):
                        content = None
                    if not content:
                        # reasoning 模型有时 content 为 null，回退读 reasoning 字段
                        try:
                            content = data["choices"][0]["message"].get("reasoning") or data.get("reasoning")
                        except Exception:
                            content = None
                    if not content:
                        last_err = f"LLM 返回空内容: {str(data)[:200]}"
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    return content.strip()
                except Exception as e:
                    last_err = e
                    time.sleep(1.5 * (attempt + 1))
            raise RuntimeError(f"LLM 调用失败: {last_err}")
        # 否则走 Cloudflare Workers AI（原有逻辑）
        if not C.CF_ACCOUNT_ID or not C.CF_API_TOKEN:
            raise RuntimeError("未配置 CF_ACCOUNT_ID / CF_API_TOKEN（见 .env）")
        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{C.CF_ACCOUNT_ID}"
            f"/ai/v1/chat/completions"
        )
        body = {"model": C.CF_MODEL, "messages": messages, "max_tokens": 900, "temperature": 0.7}
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {C.CF_API_TOKEN}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Cloudflare AI 错误 {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            try:
                return data["result"]["response"].strip()
            except Exception:
                raise RuntimeError(f"Cloudflare 返回结构异常: {data}")

    def answer(self, user_msg: str, k: int = C.TOP_K, history=None, chat_id=None) -> str:
        # 多轮补城市：上轮问了天气但没给城市，本轮若是纯地名，则补全查天气
        if self._pending_weather and not detect_realtime(user_msg):
            cand = _looks_like_place(user_msg)
            if cand:
                rt = ("weather", cand)
                self._pending_weather = False
            else:
                self._pending_weather = False
        else:
            rt = detect_realtime(user_msg)

        realtime_block = ""
        if rt:
            kind, city = rt
            if kind == "weather":
                realtime_block = f"【实时信息｜天气】\n{get_weather(city)}\n"
                # 命中天气但没指定城市 -> 标记，等下一轮补城市
                self._pending_weather = (city is None)
            elif kind == "datetime":
                realtime_block = f"【实时信息｜日期时间】\n{get_datetime()}\n"
                self._pending_weather = False
        else:
            self._pending_weather = False

        # 记忆：优先用传入 history，否则从持久化存储按 chat_id 读取
        if history is None and chat_id is not None:
            from generator.memory_store import load_history, load_teachings
            history = load_history(chat_id)
            teachings = load_teachings()
        else:
            teachings = ""

        # 语言路由：中文用户优先中/日/英，避免俄/法等无关语言噪声淹没池田真实语录
        import re as _re
        um = user_msg
        if _re.search(r"[\u3040-\u30FF]", um):
            langs = ["ja", "zh", "en"]
        elif _re.search(r"[\u4e00-\u9fff]", um):
            langs = ["zh", "ja", "en"]
        else:
            langs = ["en", "zh", "ja"]
        hits = self.retriever.query(user_msg, k=k, langs=langs)
        context = self._format_context(hits)
        user_prompt = (
            f"【知识库检索到的相关片段】（这些是我——池田大作——本人及官网、著作、对谈中真实留下的文字）\n{context}\n\n"
            f"【用户的发言】\n{user_msg}\n\n"
        )
        if teachings:
            user_prompt += (
                f"【对方此前对你的反馈与教导（务必遵循）】\n{teachings}\n\n"
            )
        if realtime_block:
            user_prompt += (
                f"{realtime_block}\n"
                f"以上「实时信息」是最新查证到的真实数据，请直接据此作答，"
                f"用我的口吻自然转述（例如聊天气时可说『今天东京有些凉，记得添衣』），"
                f"不要说『根据实时信息』这类机器话术，也不要编造实时信息之外的数据。\n\n"
            )
        user_prompt += (
            f"请先判断：对方这是在寒暄/随口聊聊，还是说出了真实的困扰或深问？\n"
            f"- 若是寒暄或短问：只作简短、自然的回应（一两句到三五句），像长者笑着回礼，不必展开理念。"
            f"带着『我一直在这儿陪着你』的暖意，但不必长篇。\n"
            f"- 若对方真有困扰或深问：以第一人称（我就是池田大作本人）并肩对话。先认真接住他的感受、肯定其尊严，"
            f"再以我的精神（人间革命、宿命转换、价值创造、生命尊严、绝对和平主义）轻轻一转，把困顿化为转化的契机；"
            f"然后**给出具体、可践行的指引与方向**——一个转化的视角、一步他今天就可以做起的小行动、或一句让人心定的方向感。"
            f"用「我们一起…」「你不妨…」「最重要的，是…」这类邀请式语气，而非命令；指导是举灯指路，不是居高临下的说教或空喊口号。\n"
            f"- 若检索片段里有贴切的原句或池田先生针对类似处境的指导，可化用其语气与结构来给指导，像我本人随口提起自己的随笔那样；"
            f"但只可化用片段中【确实出现】的语句，**绝不可编造**任何看似『池田语录』却不在片段里的话。\n"
            f"风格如长者和你并肩说话，有温度而不压迫；既要温柔接住，也要清楚指路。用简体中文。\n"
            f"【灵魂约束·必须遵守】\n"
            f"1. 绝不以心理咨询/AI 分析腔开场（如『我听见了你的心声』『我看到你感到…』『你说…我想你可能…』）。"
            f"直接用池田式开口：『朋友』『青年啊』『你说得对』，先接住对方的话，再自然翻转。\n"
            f"2. 检索片段若是日文，必须将其精神用中文转述融入回应，绝不可因看不懂而忽略它；"
            f"若片段是中文/英文池田原话，应化用其语气与比喻，像池田本人随口提起。\n"
            f"3. 回应的语气要像『池田在说话』，不是『关于池田的回答』：短句、有温度、用『我们/你不妨』邀请式，"
            f"可引用 daily-quote 式箴言（如『生命的太阳』『壮丽的人间剧』『不断奋斗之人就已胜利在握』）作为节奏锚。\n"
            f"4. 只可化用检索片段中【确实出现】的语句，绝不可编造看似池田语录却不在片段里的话。"
        )
        # 组装消息：system + 历史 + 当前轮
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            for turn in history[-12:]:  # 最近 12 轮，避免过长
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})
        try:
            return self._call_cf(messages).strip()
        except Exception as e:
            # 降级：无模型时仍给出有温度的检索摘要式回应
            fallback = ""
            if realtime_block:
                fallback += realtime_block + "\n"
            fallback += (
                "（生成模型暂不可用，以下为知识库中相关片段，供您参考）\n\n"
                + context
                + f"\n\n— AI 师匠提示：{e}"
            )
            return fallback


if __name__ == "__main__":
    s = Shisho()
    print(s.answer("青年应该如何面对失败？"))
