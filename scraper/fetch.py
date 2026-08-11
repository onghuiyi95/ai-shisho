"""爬虫：从种子 URL 广度优先抓取已放行域名下的页面，转成 markdown 存为 pages.jsonl。
用法： uv run python scraper/fetch.py
"""
import json
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import html2text
from tqdm import tqdm

import config as C

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIShishoBot/1.0; +https://example.com/bot)",
}


def is_allowed(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in C.ALLOWED_DOMAINS)


def extract_text(html_or_soup):
    if isinstance(html_or_soup, str):
        soup = BeautifulSoup(html_or_soup, "html.parser")
    else:
        soup = html_or_soup
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_tables = False
    h.body_width = 0
    return h.handle(str(soup))


def _main_content(soup):
    """剥离导航噪音，优先取正文容器。"""
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find(id="CONT") or soup.find("article") or soup
    return main


def fetch(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except Exception as e:
        return None, None, []
    if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
        return None, None, []
    host = urlparse(url).netloc.lower()
    # daisakuikeda.org 内容页为 UTF-8；apparent_encoding 在此站点误判，故强制
    r.encoding = "utf-8" if "daisakuikeda.org" in host else (r.apparent_encoding or "utf-8")
    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or url
    # 收集同站链接（用全站 soup，利于发现内容页）
    links = []
    for a in soup.find_all("a", href=True):
        absu = urljoin(url, a["href"])
        if is_allowed(absu):
            links.append(absu.split("#")[0])
    main = _main_content(soup)
    text = extract_text(main)
    return title, text, links


def _looks_like_content(text: str) -> bool:
    """粗筛：去掉换行后长度足够、且含一定数量中文字符，避免把纯导航页入库。"""
    import re
    t = text.replace("\n", "").strip()
    if len(t) < 400:
        return False
    cn = len(re.findall(r"[一-鿿]", t))
    return cn >= 120  # 至少 ~120 个汉字才视为可读内容


def main():
    seen = set()
    queue = []
    for u in C.SEED_URLS:
        if u not in seen:
            seen.add(u)
            queue.append(u)

    out = C.PAGES_JSONL
    count = 0
    with open(out, "w", encoding="utf-8") as f:
        pbar = tqdm(total=C.SCRAPE_MAX_PAGES, desc="抓取")
        while queue and count < C.SCRAPE_MAX_PAGES:
            url = queue.pop(0)
            title, text, links = fetch(url)
            time.sleep(C.SCRAPE_DELAY)
            if title is None:
                continue
            if "404" in title or "查無此頁" in title or "找不到" in title:
                continue
            if text and _looks_like_content(text):
                rec = {
                    "url": url,
                    "title": title,
                    "source": urlparse(url).netloc,
                    "text": text.strip(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                count += 1
                pbar.update(1)
            for l in links:
                if l not in seen:
                    seen.add(l)
                    queue.append(l)
        pbar.close()
    print(f"已保存 {count} 页 -> {out}")


if __name__ == "__main__":
    main()
