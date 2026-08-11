"""检索器：从 Chroma 取与 query 最相关的 top-k 片段。"""
import chromadb
from sentence_transformers import SentenceTransformer

import config as C


class Retriever:
    def __init__(self):
        self.model = SentenceTransformer(C.EMBED_MODEL)
        self.client = chromadb.PersistentClient(path=str(C.CHROMA_DIR))
        try:
            self.col = self.client.get_collection("ikeda")
        except Exception as e:
            # 明确告警：索引集合不存在，bot 将无检索运行
            import logging
            logging.warning("[Retriever] Chroma 集合 'ikeda' 不存在，检索将返回空。请先运行 rag/build_index.py。错误: %s", e)
            self.col = None

    def ready(self) -> bool:
        return self.col is not None

    def query(self, q: str, k: int = C.TOP_K, langs: list = None, min_score: float = 0.45):
        if not self.ready():
            return []
        emb = self.model.encode([q], normalize_embeddings=True).tolist()
        kwargs = {}
        if langs:
            kwargs["where"] = {"lang": {"$in": langs}}
        res = self.col.query(query_embeddings=emb, n_results=k, include=["documents", "metadatas", "distances"], **kwargs)
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            score = 1 - dist
            if score < min_score:
                continue
            out.append({"text": doc, "url": meta["url"], "title": meta["title"], "lang": meta.get("lang", "other"), "score": score})
        return out


if __name__ == "__main__":
    r = Retriever()
    if not r.ready():
        print("索引尚未构建，先运行 rag/build_index.py")
    else:
        for hit in r.query("青年应该如何面对失败？"):
            print(f"[{hit['score']:.3f}] {hit['title']} ({hit['url']})")
            print(hit["text"][:200], "\n---")
