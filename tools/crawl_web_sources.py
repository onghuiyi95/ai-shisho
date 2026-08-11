"""爬取用户给的 9 个 URL（含两个索引页展开子页），提取正文存盘，供 RAG 用。
- 单篇: 直接抓
- blog-archive (#2): 抓当月各 post 链接并逐篇抓
- book-toc (#9): 抓目录里所有 chapter-/conclusion- 链接并逐篇抓
输出: data/web_crawl/web_crawl.jsonl  (url,title,text,source)
"""
import requests, re, json, time, sys
from pathlib import Path
from bs4 import BeautifulSoup

PROJ = Path(r"C:/Users/Administrator/ai-shisho")
OUT = PROJ / "data/web_crawl"
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

sess = requests.Session()
sess.headers.update({"User-Agent": UA})

def fetch(url, timeout=25):
    try:
        r = sess.get(url, timeout=timeout)
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        return f"__ERR__{e}"

def extract_main(html):
    if html.startswith("__ERR__"):
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form", "iframe"]):
        tag.decompose()
    for el in soup.find_all(class_=lambda c: c and "cookie" in c.lower()):
        el.decompose()
    for sel in ["article", ".content", ".post", ".post-body", ".entry-content", "main", "#content", ".article"]:
        el = soup.select_one(sel)
        if el:
            t = el.get_text("\n")
            if len(t) > 200:
                return t
    body = soup.body or soup
    return body.get_text("\n")

def clean(text):
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return "\n".join(lines)

def title_of(html, fallback=""):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return fallback

docs = []

def add(url, source, title=""):
    html = fetch(url)
    if html.startswith("__ERR__"):
        print(f"  [ERR] {url}: {html}")
        return
    text = clean(extract_main(html))
    if len(text) < 30:
        print(f"  [WARN] too short {url} ({len(text)})")
        return
    docs.append({"url": url, "title": title_of(html, title), "text": text, "source": source})
    print(f"  + {source}: {len(text)} chars <- {url.split('/')[-1][:40]}")

# ---- targets ----
TARGETS = [
    ("sokasingapore_experience", "https://sokasingapore.org/experiences/facing-illness-with-the-heart-of-a-lion-king-chinese/", "page"),
    ("wynpwy_blog_2011_10", "https://wynpwy.blogspot.com/2011/10/", "blog-archive"),
    ("sokaglobal_chapter_5_3", "https://www.sokaglobal.org/chs/resources/study-materials/buddhist-study/the-wisdom-for-creating-happiness-and-peace/chapter-5-3.html", "page"),
    ("canny_md_blogpost", "https://canny-md.blogspot.com/2015/12/blog-post.html", "page"),
    ("twsgi_buddha_1128", "https://www.twsgi.org.tw/buddha-detail.php?b_id=1128", "page"),
    ("sgm_changing_poison", "https://www.sgm.org.my/zh-hans/buddhist_concepts/changing-poison-into-medicine/", "page"),
    ("infosoka_part_5_21", "https://www.infosoka.net/study/part_5_21.html", "page"),
    ("edward_sclub_32", "http://edward.sclub.com.tw/viewthread.php?action=printable&tid=32", "page"),
    ("sokaglobal_wisdom_toc", "https://www.sokaglobal.org/chs/resources/study-materials/buddhist-study/the-wisdom-for-creating-happiness-and-peace.html", "book-toc"),
]

for source, url, kind in TARGETS:
    print(f"\n=== {source} ({kind}) ===")
    if kind == "page":
        add(url, source)
    elif kind == "blog-archive":
        html = fetch(url)
        # posts on this month: links like /2011/10/blog-post_XXXX.html
        links = re.findall(r'href="(https://wynpwy\.blogspot\.com/2011/10/[^"]+)"', html)
        seen = set(); links = [l for l in links if l not in seen and (seen.add(l) or True)]
        print(f"  found {len(links)} post links")
        for i, l in enumerate(links[:60], 1):
            add(l, f"{source}_{i:02d}")
            time.sleep(0.15)
    elif kind == "book-toc":
        html = fetch(url)
        # chapter-X-Y.html and conclusion-X.html on same path
        base = "https://www.sokaglobal.org/chs/resources/study-materials/buddhist-study/the-wisdom-for-creating-happiness-and-peace/"
        links = re.findall(r'href="(\./)?((?:chapter|conclusion)-\d[\w-]*\.html)"', html)
        chap = []
        seen = set()
        for _, name in links:
            if name not in seen:
                seen.add(name); chap.append(base + name)
        print(f"  found {len(chap)} chapter links")
        for i, l in enumerate(chap[:200], 1):
            add(l, f"{source}_ch{i:03d}")
            time.sleep(0.1)

# save
outf = OUT / "web_crawl.jsonl"
with open(outf, "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
print(f"\nTOTAL docs: {len(docs)} -> {outf}")
print("by source:")
from collections import Counter
for k, v in Counter(d["source"].split("_")[0] for d in docs).most_common():
    print(f"  {k}: {v}")
