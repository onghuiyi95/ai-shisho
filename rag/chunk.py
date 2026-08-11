"""把抓取到的页面切分成用于向量化的文本块 -> chunks.jsonl。
用法： uv run python rag/chunk.py
"""
import json
import re

import config as C


def detect_lang(rec):
    """推断文档语言，用于检索时的语言路由（中文用户优先中/日/英，避免俄/法文噪声）。"""
    src = rec.get("source", "")
    url = rec.get("url", "")
    t = rec.get("text", "")[:400]
    # 日文一手源
    if any(k in src for k in ["ningenkakumei", "sokanet", "miraibu", "fc2-aoshiro", "note-jousei"]):
        return "ja"
    # 英文 quotations
    if "daisakuikeda" in src:
        return "en"
    # 中文源
    if any(k in src for k in ["daily", "sokapress"]):
        return "zh"
    # sokaglobal 多语言：按文本字符判定
    if "sokaglobal" in src:
        if re.search(r"[\u0400-\u04FF]", t):
            return "ru"          # 西里尔(俄等)
        if re.search(r"[\u0370-\u03FF]", t):
            return "el"          # 希腊
        if re.search(r"[\uAC00-\uD7A3]", t):
            return "ko"
        if re.search(r"[\u3040-\u30FF]", t):
            return "ja"
        if re.search(r"[\u4e00-\u9fff]", t):
            return "zh"
        return "other"
    # 通用：有日文假名 -> ja，有汉字 -> zh，否则 other
    if re.search(r"[\u3040-\u30FF]", t):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", t):
        return "zh"
    return "other"


def chunk_text(text: str, size: int = C.CHUNK_CHARS, overlap: int = C.CHUNK_OVERLAP):
    # 优先按段落切，长段落再按字符切
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= size:
            buf = (buf + "\n" + p).strip() if buf else p
        else:
            if buf:
                chunks.append(buf)
            # 超长段落按字符切
            if len(p) > size:
                for i in range(0, len(p), size - overlap):
                    chunks.append(p[i : i + size])
                buf = ""
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


def main():
    out = []
    n = 0
    with open(C.PAGES_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            lang = detect_lang(rec)
            for ci, c in enumerate(chunk_text(rec["text"])):
                out.append({
                    "chunk_id": f"{n:06d}",
                    "url": rec["url"],
                    "title": rec["title"],
                    "source": rec["source"],
                    "lang": lang,
                    "text": c,
                })
                n += 1
    with open(C.CHUNKS_JSONL, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"切分 {n} 个块 -> {C.CHUNKS_JSONL}")


if __name__ == "__main__":
    main()
