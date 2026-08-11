"""EPUB -> 纯文本 提取器（绕过 OPF manifest 的损坏/非标准问题，直接解 zip）。

用法：
  python importer/epub_to_text.py <file.epub>           # 打印诊断+前 500 字
  python importer/epub_to_text.py <file.epub> --out out.txt
"""
import sys
import re
import zipfile
import warnings
from pathlib import Path

from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning

warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)


def extract_epub_text(path: str) -> str:
    """返回整本书的纯文本（章节顺序）。直接读 zip 内所有 xhtml/html。"""
    out = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if n.lower().endswith((".xhtml", ".html", ".htm", ".xml"))]
        # 按路径排序，尽量贴近阅读顺序
        for n in sorted(names):
            try:
                data = z.read(n)
            except Exception:
                continue
            # 尝试解码（多为 utf-8）
            try:
                txt = data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    txt = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    txt = data.decode("latin-1", errors="ignore")
            try:
                soup = BeautifulSoup(txt, "xml")
            except Exception:
                soup = BeautifulSoup(txt, "html.parser")
            # 去掉脚本/样式
            for t in soup(["script", "style"]):
                t.decompose()
            body = soup.get_text("\n")
            body = re.sub(r"[ \t]+", " ", body)
            body = re.sub(r"\n{2,}", "\n", body).strip()
            if body:
                out.append(body)
    return "\n\n".join(out)


def diagnose(path: str):
    text = extract_epub_text(path)
    cn = len(re.findall(r"[一-鿿]", text))
    print(f"文件: {Path(path).name}")
    print(f"  总字符: {len(text):,}  中文字符: {cn:,}")
    if cn < 200:
        print("  ⚠ 中文极少，可能是图片扫描版（OCR 无意义）")
    else:
        print("  样例(前400字):")
        print("  " + text[:400].replace("\n", "\n  "))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: epub_to_text.py <file.epub> [--out out.txt]")
        sys.exit(1)
    p = sys.argv[1]
    if "--out" in sys.argv:
        outp = sys.argv[sys.argv.index("--out") + 1]
        text = extract_epub_text(p)
        Path(outp).write_text(text, encoding="utf-8")
        print(f"written {len(text):,} chars -> {outp}")
    else:
        diagnose(p)
