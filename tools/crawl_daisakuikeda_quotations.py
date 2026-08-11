"""补爬 daisakuikeda.org 的 Quotations（42 个主题）英文原话，作为池田表达DNA/心智模型的权威一手英文素材。
并入 web_crawl.jsonl（增量去重），供后续 chunk + 索引。
每条 quote 单独成 doc（source=daisakuikeda-quotations-<theme>），便于检索单句原话。
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
sess.headers.update({"User-Agent": UA})

THEMES = ["attitude","cause-effect","compassion","courage","creativity","desires",
"dialogue","difficulties","diversity","education","empowerment","enlightenment",
"environment","family-parenting","global-citizenship","good-evil","gratitude",
"happiness","health-illness","hope","human-relationships","human-revolution",
"human-rights","interconnectedness","leadership","life","life-death",
"life-potential","love-marriage","mental-well-being","mentor-disciple",
"nonviolence","nuclear-disarmament","peace","power-of-heart","power-of-women",
"prayer","religion-faith","self-mastery","strength"]

existing = set()
if JSONL.exists():
    for l in JSONL.read_text(encoding="utf-8").splitlines():
        if l.strip():
            try: existing.add(json.loads(l)["url"])
            except: pass
print(f"resume: already {len(existing)} urls")

def fetch(url, timeout=20, retries=3):
    for _ in range(retries):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 300:
                return r.text
        except Exception:
            time.sleep(0.5)
    return ""

def extract_quotes(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript","header","footer","nav"]): t.decompose()
    quotes = []
    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if 30 < len(txt) < 500 and ('“' in txt or '"' in txt or '—' in txt or '[' in txt):
            quotes.append(txt)
    # 去重 + 过滤导航残留
    seen=set(); out=[]
    for q in quotes:
        if q in seen: continue
        seen.add(q); out.append(q)
    return out

cnt=0
for th in THEMES:
    url = f"https://www.daisakuikeda.org/sub/quotations/theme/{th}.html"
    if url in existing:
        print(f"  skip {th}"); continue
    html = fetch(url)
    if not html:
        print(f"  [ERR] {th}"); continue
    qs = extract_quotes(html)
    for i,q in enumerate(qs):
        uid = f"{url}#q{i}"
        if uid in existing: continue
        rec = {"url": uid, "title": f"Quotations: {th}", "text": q,
               "source": f"daisakuikeda-quotations-{th}"}
        with open(JSONL,"a",encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False)+"\n")
        existing.add(uid); cnt+=1
    print(f"  [OK] {th}: {len(qs)} quotes")
    time.sleep(0.2)

total = sum(1 for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip())
print(f"\nDONE. 本次新增 {cnt} 条, web_crawl.jsonl 总行数: {total}")
