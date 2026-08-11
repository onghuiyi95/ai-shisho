"""本地 LLM 中转服务（OpenAI 兼容 /v1/chat/completions）。

让 bot 走一个稳定的、不依赖 Cloudflare 免费额度的生成后端。
- 默认后端：本地 transformers 小模型（免费、不限额、离线）
- 可切换：设置环境变量 LLM_BACKEND=openai + LLM_BASE_URL + LLM_API_KEY 走远程 OpenAI 兼容服务
  （如 Groq / Together / 你自己的中转，做到"跟 Hermes 调用一样的模型"）

用法：
  python tools/llm_relay.py            # 默认本地模型，监听 :8787
  LLM_BACKEND=openai python tools/llm_relay.py   # 远程后端
"""
import os
import sys
import json
import time

import config as C

BACKEND = os.getenv("LLM_BACKEND", "local")          # local | openai
PORT = int(os.getenv("LLM_RELAY_PORT", "8787"))
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "Qwen/Qwen2.5-3B-Instruct")

# ---------- 本地 transformers 后端 ----------
_local_pipe = None


def _load_local():
    global _local_pipe
    if _local_pipe is not None:
        return _local_pipe
    from transformers import pipeline
    print(f"[relay] 加载本地模型 {LOCAL_MODEL} ...", flush=True)
    t = time.time()
    _local_pipe = pipeline(
        "text-generation",
        model=LOCAL_MODEL,
        device=-1,                     # CPU
        dtype="auto",
        do_sample=False,
    )
    print(f"[relay] 本地模型就绪，耗时 {time.time()-t:.1f}s", flush=True)
    return _local_pipe


def _gen_local(messages, max_tokens=900, temperature=0.7):
    pipe = _load_local()
    # 拼成对话文本
    prompt = ""
    for m in messages:
        role = m["role"]
        if role == "system":
            prompt += f"<|system|>\n{m['content']}\n"
        elif role == "user":
            prompt += f"<|user|>\n{m['content']}\n"
        else:
            prompt += f"<|assistant|>\n{m['content']}\n"
    prompt += "<|assistant|>\n"
    out = pipe(prompt, max_new_tokens=max_tokens, do_sample=(temperature > 0),
               temperature=temperature, return_full_text=False)
    return out[0]["generated_text"].strip()


# ---------- 远程 OpenAI 兼容后端 ----------
def _gen_openai(messages, max_tokens=900, temperature=0.7):
    import requests
    url = os.getenv("LLM_BASE_URL", "").rstrip("/") + "/chat/completions"
    key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    r = requests.post(url, headers={"Authorization": f"Bearer {key}",
                       "Content-Type": "application/json"},
                      json={"model": model, "messages": messages,
                            "max_tokens": max_tokens, "temperature": temperature},
                      timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def generate(messages, max_tokens=900, temperature=0.7):
    if BACKEND == "openai":
        return _gen_openai(messages, max_tokens, temperature)
    return _gen_local(messages, max_tokens, temperature)


# ---------- HTTP 服务（OpenAI 兼容） ----------
def make_app():
    from flask import Flask, request, jsonify
    app = Flask(__name__)

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat():
        data = request.get_json(force=True)
        messages = data.get("messages", [])
        max_tokens = int(data.get("max_tokens", 900))
        temperature = float(data.get("temperature", 0.7))
        try:
            text = generate(messages, max_tokens, temperature)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        return jsonify({
            "id": "relay-" + str(int(time.time())),
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "backend": BACKEND})

    return app


if __name__ == "__main__":
    # 本地后端预加载（避免首个请求卡太久）
    if BACKEND == "local":
        try:
            _load_local()
        except Exception as e:
            print(f"[relay] 本地模型加载失败: {e}", flush=True)
    app = make_app()
    app.run(host="127.0.0.1", port=PORT, threaded=True)
    print(f"[relay] 监听 http://127.0.0.1:{PORT}  后端={BACKEND}", flush=True)
