"""全量展开爬取 v3（最终修正）：
 - Blogger (wynpwy, canny-md): Atom feed 枚举全部帖子
 - sokasingapore: experiences 全 139 篇（winning-life 归入该分类，0 独立）
 - sgm: 18 个已知佛法概念页
 - infosoka: part_1..8 系列
 - twsgi: 教学橱窗各分类 buddha-detail
 - edward: 论坛 tid 扫描（短超时，最后跑）
断点续传追加到 data/web_crawl/web_crawl.jsonl。
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
sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})

DROP = ["以電子郵件傳送這篇文章", "BlogThis", "分享至", "張貼者：", "沒有留言",
        "標籤：", "較新的文章", "首頁", "訂閱：", "網誌存檔", "簡單主題", "技術提供",
        "關於我自己", "檢視我的完整簡介", "Create Blog", "Sign In", "Go to Blogger.com",
        "Report Abuse", "MoreShare", "Share by email", "Powered by Discuz"]

existing = set()
if JSONL.exists():
    for l in JSONL.read_text(encoding="utf-8").splitlines():
        if l.strip():
            try: existing.add(json.loads(l)["url"])
            except: pass
print(f"resume: already have {len(existing)} urls")

def fetch(url, timeout=10, retries=1):
    for _ in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code == 200 and len(r.text) > 300:
                return r.text
        except Exception:
            time.sleep(0.2)
    return "__ERR__"

def clean(text):
    out = []
    for l in text.splitlines():
        l = re.sub(r"\s+", " ", l).strip()
        if not l or any(d in l for d in DROP):
            continue
        out.append(l)
    return "\n".join(out)

def extract_generic(html):
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

def crawl_blogger(blog, source, cap=800):
    urls = []
    for start in range(1, cap, 500):
        fb = f"https://{blog}/feeds/posts/default?max-results=500&start-index={start}"
        h = fetch(fb, retries=3)
        if h.startswith("__ERR__"):
            break
        links = re.findall(r"rel='alternate' type='text/html' href='([^']+)'", h)
        if not links:
            links = re.findall(r'rel="alternate" type="text/html" href="([^"]+)"', h)
        if not links:
            break
        urls += links
        if len(links) < 500:
            break
        time.sleep(0.3)
    seen = set(); urls = [u for u in urls if not (u in seen or seen.add(u))]
    print(f"  [{source}] feed 枚举到 {len(urls)} 篇帖子")
    cnt = 0
    for i, u in enumerate(urls, 1):
        if u in existing:
            continue
        html = fetch(u)
        if html.startswith("__ERR__"):
            continue
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        art = soup.select_one(".post-body") or soup.select_one("article") or soup.body
        te = soup.select_one("h3") or soup.select_one("h1")
        title = te.get_text(" ", strip=True) if te else ""
        body = clean(art.get_text("\n"))
        if len(body) < 20:
            continue
        append(u, f"{source}_{i:03d}", title, body)
        cnt += 1
        time.sleep(0.05)
    print(f"  [{source}] 新增 {cnt}")

def crawl_sokasingapore():
    base = "https://sokasingapore.org"
    urls = set()
    for p in range(1, 45):
        u = f"{base}/category/experiences/" if p == 1 else f"{base}/category/experiences/page/{p}/"
        h = fetch(u)
        if h.startswith("__ERR__"):
            break
        ls = re.findall(r'href="(' + re.escape(base) + r'/experiences/[A-Za-z0-9\-]+)/?"', h)
        for l in ls:
            urls.add(l.rstrip("/"))
        time.sleep(0.12)
    print(f"  [sokasingapore] 发现 {len(urls)} 篇 experiences 文章")
    cnt = 0
    for i, u in enumerate(sorted(urls), 1):
        if u in existing:
            continue
        html = fetch(u)
        if html.startswith("__ERR__"):
            continue
        body = extract_generic(html)
        if len(body) < 50:
            continue
        append(u, f"sokasingapore_{i:03d}", title_of(html), body)
        cnt += 1
        time.sleep(0.05)
    print(f"  [sokasingapore] 新增 {cnt}")

def crawl_sgm():
    concepts = ["buddhism_dignity","cause-and-effect","changing-poison-into-medicine",
        "chinese-mentor-and-disciple","compassion","creating-value","human-revolution",
        "life-and-death","lotus-sutra-seven-parables-animation","namyohorenge",
        "practise-for-oneself-and-others","securing-peace-for-the-people","the-middle-way",
        "the-oneness-of-life-and-its-environment","the-ten-worlds-chinese","three-thousand-realms",
        "who-is-a-buddha-chinese","wisdom"]
    urls = [f"https://www.sgm.org.my/zh-hans/buddhist_concepts/{c}" for c in concepts]
    print(f"  [sgm] {len(urls)} 概念页")
    cnt = 0
    for i, u in enumerate(urls, 1):
        if u in existing:
            continue
        html = fetch(u)
        if html.startswith("__ERR__"):
            continue
        body = extract_generic(html)
        if len(body) < 50:
            continue
        append(u, f"sgm_concept_{i:02d}", title_of(html), body)
        cnt += 1
        time.sleep(0.05)
    print(f"  [sgm] 新增 {cnt}")

def crawl_infosoka():
    base = "https://www.infosoka.net/study/"
    urls = set()
    h = fetch(base + "index.html")
    urls |= set(re.findall(r'href="(part_\d+_\d+\.html)"', h))
    for x in range(1, 9):
        for y in range(1, 60):
            urls.add(f"part_{x}_{y}.html")
    urls = sorted({base + l for l in urls})
    print(f"  [infosoka] {len(urls)} 页")
    cnt = 0
    for i, u in enumerate(urls, 1):
        if u in existing:
            continue
        html = fetch(u)
        if html.startswith("__ERR__"):
            continue
        body = extract_generic(html)
        if len(body) < 30:
            continue
        append(u, f"infosoka_{i:03d}", title_of(html), body)
        cnt += 1
        time.sleep(0.04)
    print(f"  [infosoka] 新增 {cnt}")

def crawl_twsgi():
    base = "https://www.twsgi.org.tw/"
    links = set()
    for lid in [150, 21, 58, 22, 23]:
        h = fetch(base + f"buddha-list.php?level2_id={lid}")
        for l in re.findall(r'href="(buddha-detail\.php\?b_id=\d+)"', h):
            links.add(base + l)
    print(f"  [twsgi] buddha-detail {len(links)}")
    cnt = 0
    for i, u in enumerate(sorted(links), 1):
        if u in existing:
            continue
        html = fetch(u)
        if html.startswith("__ERR__"):
            continue
        body = extract_generic(html)
        if len(body) < 30:
            continue
        append(u, f"twsgi_buddha_{i:03d}", title_of(html), body)
        cnt += 1
        time.sleep(0.05)
    print(f"  [twsgi] 新增 {cnt}")

def crawl_edward(cap=200):
    base = "http://edward.sclub.com.tw/viewthread.php?action=printable&tid="
    cnt = 0
    for tid in range(1, cap + 1):
        u = f"{base}{tid}"
        if u in existing:
            continue
        html = fetch(u, timeout=4, retries=1)
        if html.startswith("__ERR__"):
            continue
        body = extract_generic(html)
        if len(body) < 200:
            continue
        append(u, f"edward_thread_{tid:03d}", title_of(html), body)
        cnt += 1
        time.sleep(0.02)
    print(f"  [edward] 新增 {cnt}")

if __name__ == "__main__":
    print("=== 全量展开爬取 v3 ===")
    crawl_blogger("wynpwy.blogspot.com", "wynpwy_full")
    crawl_blogger("canny-md.blogspot.com", "canny_md_full")
    crawl_sokasingapore()
    crawl_sgm()
    crawl_infosoka()
    crawl_twsgi()
    crawl_edward(cap=120)
    total = sum(1 for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip())
    print(f"\nDONE. web_crawl.jsonl 总行数: {total}")
