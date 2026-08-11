"""补爬 sokaglobal 佛法教材：3 本教材 × 6 语言 + 2 个数位资源页。
之前 web_crawl.jsonl 只拿了 book1 (the-wisdom-for-creating-happiness-and-peace) 的 chs 365 章，
漏了 book2/book3 全部语言 + 数位资源页。本脚本枚举补齐，断点续传追加到 web_crawl.jsonl。

教材 landing 页（父页 buddhist-study.html 列出）：
  - the-wisdom-for-creating-happiness-and-peace      (book1, 章节 chapter-N-M.html)
  - the-basics-of-nichiren-buddhism-...-kosen-rufu   (book2, 章节 chapter-N.html)
  - the-new-human-revolution                          (book3)
数位资源：
  - commemorative-dates
  - buddhist-concepts
语言前缀：cht chs en es fr ru
"""
import requests, re, json, time
from pathlib import Path
from bs4 import BeautifulSoup

PROJ = Path(r"C:/Users/Administrator/ai-shisho")
OUT = PROJ / "data/web_crawl"
OUT.mkdir(parents=True, exist_ok=True)
JSONL = OUT / "web_crawl.jsonl"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
sess = requests.Session()
sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"})

LANGS = ["cht", "chs", "en", "es", "fr", "ru"]
BOOKS = [
    "the-wisdom-for-creating-happiness-and-peace",
    "the-basics-of-nichiren-buddhism-for-the-new-era-of-worldwide-kosen-rufu",
    "the-new-human-revolution",
]
DIGITAL = ["commemorative-dates", "buddhist-concepts"]

existing = set()
if JSONL.exists():
    for l in JSONL.read_text(encoding="utf-8").splitlines():
        if l.strip():
            try: existing.add(json.loads(l)["url"])
            except: pass
print(f"resume: already have {len(existing)} urls")

def fetch(url, timeout=15, retries=2):
    for _ in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code == 200 and len(r.text) > 300:
                return r.text
        except Exception:
            time.sleep(0.3)
    return "__ERR__"

DROP = ["以電子郵件傳送", "BlogThis", "分享至", "張貼者", "沒有留言", "標籤",
        "較新的文章", "首頁", "訂閱", "網誌存檔", "技術提供", "關於我自己"]
def clean(text):
    out = []
    for l in text.splitlines():
        l = re.sub(r"\s+", " ", l).strip()
        if not l or any(d in l for d in DROP):
            continue
        out.append(l)
    return "\n".join(out)

def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form", "iframe"]):
        t.decompose()
    for el in soup.find_all(class_=lambda c: c and "cookie" in c.lower()):
        el.decompose()
    for sel in ["article", ".content", ".post", ".post-body", ".entry-content", "main", "#content", ".article-body", ".txt"]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text("\n")
            if len(t) > 200:
                return clean(t)
    body = soup.body or soup
    return clean(body.get_text("\n"))

def title_of(html, fb=""):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else fb

def append(url, source, title, text):
    with open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "title": title, "text": text, "source": source}, ensure_ascii=False) + "\n")

cnt = 0
# 3 本教材 × 6 语言
for book in BOOKS:
    for lang in LANGS:
        land = f"https://www.sokaglobal.org/{lang}/resources/study-materials/buddhist-study/{book}.html"
        if land in existing:
            continue
        html = fetch(land)
        if html.startswith("__ERR__"):
            print(f"  [ERR] {land}")
            continue
        # 抓 landing 页本身（含导言）
        body = extract(html)
        if len(body) > 100:
            append(land, f"sokaglobal_{book}_{lang}", title_of(html, book), body)
            cnt += 1
            print(f"  [OK] {lang}/{book} landing ({len(body)} chars)")
        time.sleep(0.1)
        # 提取所有同书章节链接 chapter-*.html（含子目录任意层级）
        base_path = f"/{lang}/resources/study-materials/buddhist-study/{book}/"
        chaps = set(re.findall(r'href="([^"]*chapter-[^"]*\.html)"', html))
        # 也匹配绝对路径
        for c in re.findall(r'href="(https://www\.sokaglobal\.org/' + re.escape(base_path.lstrip("/")) + r'[^"]*chapter-[^"]*\.html)"', html):
            chaps.add(c)
        full = []
        for c in chaps:
            if c.startswith("http"):
                full.append(c)
            elif c.startswith("/"):
                full.append("https://www.sokaglobal.org" + c)
            else:
                full.append("https://www.sokaglobal.org" + base_path + c)
        for u in sorted(set(full)):
            if u in existing:
                continue
            ch = fetch(u)
            if ch.startswith("__ERR__"):
                continue
            cb = extract(ch)
            if len(cb) > 80:
                append(u, f"sokaglobal_{book}_{lang}", title_of(ch, book), cb)
                cnt += 1
            time.sleep(0.05)
        print(f"  [done] {lang}/{book} 章节 {len(full)} 个")

# 2 个数位资源页 × 6 语言（单页，可能有子链接也一并抓）
for dig in DIGITAL:
    for lang in LANGS:
        land = f"https://www.sokaglobal.org/{lang}/resources/study-materials/{dig}.html"
        if land in existing:
            continue
        html = fetch(land)
        if html.startswith("__ERR__"):
            continue
        body = extract(html)
        if len(body) > 100:
            append(land, f"sokaglobal_{dig}_{lang}", title_of(html, dig), body)
            cnt += 1
            print(f"  [OK] {lang}/{dig} ({len(body)} chars)")
        time.sleep(0.1)

total = sum(1 for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip())
print(f"\nDONE. 本次新增 {cnt} 条, web_crawl.jsonl 总行数: {total}")
