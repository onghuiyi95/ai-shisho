"""Phase2: 从 web_extract 缓存的索引页 .md 提取子链接，逐个 fetch 子页正文。
- wynpwy 2011/10 归档 -> 198 篇帖子
- sokaglobal 整本书 -> 365 章
断点续传: 已写入 jsonl 的 url 跳过。结果追加到 data/web_crawl/web_crawl.jsonl
"""
import requests, re, json, time, sys
from pathlib import Path
from bs4 import BeautifulSoup

PROJ = Path(r"C:/Users/Administrator/ai-shisho")
OUT = PROJ / "data/web_crawl"
OUT.mkdir(parents=True, exist_ok=True)
JSONL = OUT / "web_crawl.jsonl"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
sess = requests.Session()
sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})

# boilerplate to drop (blogspot share/author noise etc.)
DROP = ["以電子郵件傳送這篇文章", "BlogThis", "分享至", "張貼者：", "沒有留言",
        "標籤：", "較新的文章", "首頁", "訂閱：", "網誌存檔", "簡單主題", "技術提供",
        "關於我自己", "檢視我的完整簡介", "Create Blog", "Sign In", "Go to Blogger.com",
        "Report Abuse", "MoreShare"]

def fetch(url, timeout=20, retries=3):
    for i in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
        except Exception:
            pass
        time.sleep(0.5)
    return "__ERR__"

def clean(text):
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    out = []
    for l in lines:
        if not l:
            continue
        if any(d in l for d in DROP):
            continue
        out.append(l)
    return "\n".join(out)

def extract_blogspot(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    art = soup.select_one(".post-body") or soup.select_one("article") or soup.select_one(".post") or soup.body
    title_el = soup.select_one("h3") or soup.select_one("h1")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    body = clean(art.get_text("\n"))
    return title, body

def extract_generic(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form", "iframe"]):
        t.decompose()
    for el in soup.find_all(class_=lambda c: c and "cookie" in c.lower()):
        el.decompose()
    for sel in ["article", ".content", ".post", ".post-body", ".entry-content", "main", "#content", ".article-body"]:
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

# load existing urls (resume)
existing = set()
if JSONL.exists():
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try: existing.add(json.loads(line)["url"])
            except: pass
print(f"already in jsonl: {len(existing)}")

def append(url, source, title, text):
    with open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "title": title, "text": text, "source": source}, ensure_ascii=False) + "\n")

# ---- link lists ----
wynpwy_links = Path(r"C:/Users/Administrator/AppData/Local/Temp/wynpwy_links.txt").read_text(encoding="utf-8").splitlines()
soka_links = Path(r"C:/Users/Administrator/AppData/Local/Temp/soka_links.txt").read_text(encoding="utf-8").splitlines()
print(f"wynpwy links: {len(wynpwy_links)} | soka links: {len(soka_links)}")

ok = err = skip = 0
# wynpwy posts
for i, url in enumerate(wynpwy_links, 1):
    if url in existing:
        skip += 1; continue
    html = fetch(url)
    if html.startswith("__ERR__"):
        err += 1; continue
    title, body = extract_blogspot(html)
    if len(body) < 20:
        err += 1; continue
    append(url, f"wynpwy_2011_10_{i:03d}", title, body)
    ok += 1
    time.sleep(0.08)
print(f"[wynpwy done] added={ok} err={err} skip={skip}")

# sokaglobal chapters
ok = err = skip = 0
for i, url in enumerate(soka_links, 1):
    if url in existing:
        skip += 1; continue
    html = fetch(url)
    if html.startswith("__ERR__"):
        err += 1; continue
    body = extract_generic(html)
    if len(body) < 20:
        err += 1; continue
    append(url, f"sokaglobal_wisdom_ch{i:03d}", title_of(html), body)
    ok += 1
    time.sleep(0.06)
print(f"[sokaglobal done] added={ok} err={err} skip={skip}")

# final count
total = sum(1 for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip())
print(f"FINAL jsonl lines: {total}")
