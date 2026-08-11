"""sokapress 全量文字备份爬虫。
登录 -> 枚举 27 个栏目 -> 两类提取：
  proverbs 型: 列表页 pTxts 短句，翻页(检测首条日期变化停止)
  other 型:    列表页 column_detail 链接 -> 进每篇提 class=txt 正文
输出: data/sokapress_backup/text/<栏目名>.json + manifest.json
"""
import requests, re, json, time, base64, sys
from pathlib import Path

BASE="https://sokapress.twsgi.org.tw"
USER, PW = "huiyi0731@gmail.com", "Twsgi@2020"
OUT=Path(r"C:/Users/Administrator/ai-shisho/data/sokapress_backup/text")
OUT.mkdir(parents=True, exist_ok=True)

sess=requests.Session()
sess.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
sess.get(BASE+"/index.php", timeout=25)
sess.post(BASE+"/member_judge.php",
          data={"user_name":USER,"user_pw":PW,"reUrlAddr":"JCUvaW5kZXgucGhwPyMh"}, timeout=25)

def lid(n):
    return base64.b64encode(f"$%{n}#!".encode()).decode()

# ---- proverbs 型: 列表翻页抓 pTxts ----
MAXP = 60  # 栏目实际可能到 39 页，原写死 15 会截断，放宽到 60
def crawl_proverbs(n):
    l=lid(n)
    items=[]; seen=set(); page=1
    while page<=MAXP:
        html=sess.get(f"{BASE}/proverbs.php?level1_id={l}&page={page}", timeout=20).text
        titles=re.findall(r'class="pTitle">([^<]*)</a>', html)
        dates=re.findall(r'class="pdate">([^<]*)</div>', html)
        texts=re.findall(r'class="pTxts"[^>]*>([\s\S]*?)</div>', html)
        if not titles: break
        first=dates[0] if dates else None
        if first in seen: break
        seen.add(first)
        m=min(len(titles),len(dates),len(texts))
        for i in range(m):
            items.append({"title":titles[i].strip(),"date":dates[i].strip(),
                          "text":re.sub(r'<[^>]+>','',texts[i]).strip()})
        page+=1; time.sleep(0.2)
    # dedupe
    s2=set(); uniq=[]
    for it in items:
        k=(it["date"],it["text"])
        if k in s2: continue
        s2.add(k); uniq.append(it)
    return uniq

# ---- other 型: 列表抓 detail 链接 -> 进每篇提正文 ----
def crawl_column(n):
    l=lid(n)
    # get list pages
    detail_ids=[]
    seen=set(); page=1
    while page<=MAXP:
        html=sess.get(f"{BASE}/column.php?level1_id={l}&page={page}", timeout=20).text
        links=re.findall(r'column_detail\.php\?([^"\'>\s]+)', html)
        if not links: break
        first=links[0]
        if first in seen: break
        seen.add(first)
        for lnk in links:
            did=re.search(r'id=([^"&\s]+)', lnk)
            if did: detail_ids.append(did.group(1))
        page+=1; time.sleep(0.2)
    # fetch each detail, extract txt
    items=[]
    for did in dict.fromkeys(detail_ids):
        try:
            dh=sess.get(f"{BASE}/column_detail.php?level1_id={l}&id={did}", timeout=20).text
        except: continue
        # title
        mt=re.search(r'class="title">([^<]+)', dh)
        md=re.search(r'class="dates">([^<]*)', dh)
        # body: class=txt region (strip tags)
        c=re.search(r'class="txt"[^>]*>(.*?)</div>', dh, re.S)
        body=""
        if c:
            body=re.sub(r'<[^>]+>',' ',c.group(1))
            body=re.sub(r'\s+',' ',body).strip()
        if not body:
            # fallback: og:description
            og=re.search(r'og:description"\s+content="([^"]+)"', dh)
            if og: body=og.group(1)
        items.append({"title":mt.group(1).strip() if mt else "","date":md.group(1).strip() if md else "","text":body})
        time.sleep(0.15)
    return items

# ---- run ----
CATS=[
 (1,"proverbs","焦點News"),(2,"proverbs","特輯"),(3,"proverbs","每日箴言"),
 (4,"proverbs","信心園地"),(5,"proverbs","池田大作先生指導"),(6,"other","賀詞"),
 (7,"other","隨筆"),(8,"other","與御書前進"),(9,"other","詩篇"),
 (10,"other","新‧人間革命"),(11,"proverbs","其他"),(12,"proverbs","學習御書"),
 (13,"proverbs","座談會御書"),(14,"proverbs","追善回向勤行會御書"),(15,"other","區御書學習班專題"),
 (16,"proverbs","信仰體驗"),(17,"proverbs","教育‧心理"),(19,"proverbs","藝文"),
 (20,"proverbs","生活"),(21,"other","健康"),(22,"proverbs","醫學"),
 (23,"other","法律"),(24,"proverbs","SGI News"),(25,"other","對談集"),
 (26,"other","學習小說《新．人間革命》"),(27,"other","世界寫真紀行"),(28,"proverbs","人間革命"),
]
manifest={"categories":[],"total_items":0}
for n,typ,name in CATS:
    if typ=="proverbs":
        items=crawl_proverbs(n)
    else:
        items=crawl_column(n)
    fn=OUT/f"{name}.json"
    fn.write_text(json.dumps(items,ensure_ascii=False,indent=1),encoding="utf-8")
    manifest["categories"].append({"n":n,"type":typ,"name":name,"items":len(items),"file":name+".json"})
    manifest["total_items"]+=len(items)
    print(f"#{n:2d} [{typ:8}] {name:24} -> {len(items)} items")
    sys.stdout.flush()

(OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=1),encoding="utf-8")
print("\nTOTAL ITEMS:", manifest["total_items"])
print("manifest ->", OUT/"manifest.json")
