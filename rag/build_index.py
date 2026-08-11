"""构建 / 重建 Chroma 向量索引。
用法： uv run python rag/build_index.py
"""
import json

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

import config as C


class LocalSTEmbedding:
    """包装 sentence-transformers 作为 Chroma 的 embedding 函数。"""
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()

    def __call__(self, input):
        if isinstance(input, str):
            input = [input]
        return self.model.encode(input, normalize_embeddings=True).tolist()

    def name(self):
        return "local-st-multilingual"


def main():
    chunks = []
    with open(C.CHUNKS_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    if not chunks:
        print("没有块可建索引，先运行 rag/chunk.py")
        return

    # 重建前彻底清空旧 chroma 目录，杜绝孤儿集合堆积（历史多次 reindex 会残留 uuid 集合）
    import shutil
    if C.CHROMA_DIR.exists():
        shutil.rmtree(C.CHROMA_DIR, ignore_errors=True)
    C.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(C.CHROMA_DIR))
    embed = LocalSTEmbedding(C.EMBED_MODEL)

    col = client.create_collection(
        name="ikeda",
        embedding_function=embed,
        metadata={"hnsw:space": "cosine"},
    )

    docs = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metas = [{"url": c["url"], "title": c["title"], "source": c["source"], "lang": c.get("lang", "other")} for c in chunks]
    # 分批写入，避免一次过大
    B = 500
    for i in range(0, len(docs), B):
        col.add(documents=docs[i:i+B], ids=ids[i:i+B], metadatas=metas[i:i+B])
    print(f"索引完成：共 {len(docs)} 个块，模型 {C.EMBED_MODEL}")


if __name__ == "__main__":
    main()
