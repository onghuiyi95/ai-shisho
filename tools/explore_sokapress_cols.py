"""探索 sokapress 11 个 0-返回栏目的真实结构：是 AJAX / 图片画廊 / 还是列表接口不同。
登录 -> 抓各栏目 list 页 -> 打印关键结构信号 + 保存原始 HTML 供细看。
"""
import requests, re, json, time, base64, sys
from pathlib import Path

BASE = "https://sokapress.twsgi.org.tw"
USER, PW = "huiyi0731@gmail.com", "Twsgi@2020"
DUMP = Path(r"C:/Users/Administrator/ai-shisho/data/sokapress_backup/explore")
DUMP.mkdir(parents=True, exist_ok=True)

sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
sess.get(BASE + "/index.php", timeout=25)
r = sess.post(BASE + "/member_judge.php",
              data={"user_name": USER, "user_pw": PW, "reUrlAddr": "JCUvaW5kZXgucGhwPyMh"}, timeout=25)
print("login:", r.status_code, "cookies:", list(sess.cookies.keys()))

def lid(n):
    return base64.b64encode(f"$%{n}#!".encode()).decode()

# 11 个 0-返回栏目 + 1 个已知有文字的(信仰體驗 n=16) 做对照
PROBE = [6, 7, 8, 9, 10, 15, 21, 23, 25, 26, 27, 16]

for n in PROBE:
    l = lid(n)
    # try column.php (other 型用的列表页)
    html = sess.get(f"{BASE}/column.php?level1_id={l}&page=1", timeout=20).text
    detail_links = re.findall(r'column_detail\.php\?([^"\'>\s]+)', html)
    aj_thumbs = re.findall(r'(?:data-|onclick=|href=)["\']([^"\']*(?:ajax|load|page|photo|img|gallery)[^"\']*)["\']', html, re.I)
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
    has_pager = bool(re.search(r'(?:page=|pagination|下一頁|more|載入更多|load-more)', html, re.I))
    # also try proverbs.php just in case some are actually proverbs type
    phtml = sess.get(f"{BASE}/proverbs.php?level1_id={l}&page=1", timeout=20).text
    p_titles = re.findall(r'class="pTitle">([^<]*)</a>', phtml)
    print(f"\n=== n={n} ===")
    print(f"  column.php len={len(html)} | detail_links={len(detail_links)} | imgs={len(imgs)} | pager={has_pager}")
    print(f"  proverbs.php pTitle matches={len(p_titles)}")
    if detail_links:
        print(f"  sample detail link: {detail_links[0][:80]}")
    if imgs:
        uniq = sorted(set(imgs))[:3]
        print(f"  sample imgs: {uniq}")
    # dump raw for close inspection (first 4k chars)
    (DUMP / f"col_{n}.html").write_text(html, encoding="utf-8")
    time.sleep(0.3)
print("\nDUMP dir:", DUMP)
