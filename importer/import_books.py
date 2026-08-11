"""把本地 EPUB（池田大作著作 / SGI 指导 / 新人间革命学习本等）导入知识库。

流程：
  1. 扫描文档目录下的 .epub
  2. 提取纯文本（epub_to_text）
  3. 以「每本一页」的形式追加进 data/clean/pages.jsonl
     （url = book:<书名>，source = local-epub，title = 干净书名）
  4. 之后照常跑 rag/chunk.py + rag/build_index.py 重建向量库

幂等：已导入的书名记录在 data/clean/imported_books.txt，重跑不重复。
用法：
  python importer/import_books.py [--docs DIR]
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 允许作为模块被项目调用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

from importer.epub_to_text import extract_epub_text  # noqa: E402


def clean_name(fname: str) -> str:
    """从文件名推导出干净书名。去掉 doc_<hash>_ 前缀与扩展名。"""
    stem = Path(fname).stem
    # 去掉开头的 doc_xxxxxxxx_ 哈希前缀
    stem = re.sub(r"^doc_[0-9a-f]+_", "", stem)
    # 统一全角空格/下划线为空格
    stem = stem.replace("－", "-").strip()
    return stem


def main():
    ap = argparse.ArgumentParser()
    default_docs = Path.home() / "AppData" / "Local" / "hermes" / "cache" / "documents"
    ap.add_argument("--docs", default=str(default_docs),
                    help="存放 epub 的目录")
    args = ap.parse_args()

    docs_dir = Path(args.docs)
    if not docs_dir.exists():
        print(f"文档目录不存在: {docs_dir}")
        sys.exit(1)

    pages_jsonl = C.PAGES_JSONL
    pages_jsonl.parent.mkdir(parents=True, exist_ok=True)

    imported_log = pages_jsonl.parent / "imported_books.txt"
    done = set()
    if imported_log.exists():
        done = {l.strip() for l in imported_log.read_text(encoding="utf-8").splitlines() if l.strip()}

    epubs = sorted(docs_dir.glob("*.epub"))
    print(f"发现 {len(epubs)} 个 epub，已导入 {len(done)} 本")

    added = 0
    skipped = 0
    too_short = 0
    with open(pages_jsonl, "a", encoding="utf-8") as fout, \
         open(imported_log, "a", encoding="utf-8") as flog:
        for ep in epubs:
            name = clean_name(ep.name)
            if name in done:
                skipped += 1
                continue
            try:
                text = extract_epub_text(str(ep))
            except Exception as e:
                print(f"  ✗ 解析失败 {ep.name}: {e}")
                skipped += 1
                continue
            cn = len(re.findall(r"[一-鿿]", text))
            if cn < 500:
                print(f"  ⚠ 中文过少，跳过 {ep.name} (cn={cn})")
                too_short += 1
                # 仍标记为已处理，避免反复尝试
                flog.write(name + "\n")
                done.add(name)
                continue
            rec = {
                "url": f"book:{name}",
                "title": name,
                "source": "local-epub",
                "text": text.strip(),
            }
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
            flog.write(name + "\n")
            done.add(name)
            added += 1
            print(f"  + 导入《{name}》 ({cn:,} 中文字)")

    print(f"\n完成：新增 {added} 本，跳过 {skipped} 本（已导入或失败），过短 {too_short} 本")
    print(f"pages.jsonl 当前总行数：")
    n = sum(1 for _ in open(pages_jsonl, encoding="utf-8"))
    print(f"  {n}")


if __name__ == "__main__":
    main()
