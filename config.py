"""AI 师匠 — 全局配置。从 .env 读取，缺省给安全默认值。"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent

DATA_DIR = Path(os.getenv("DATA_DIR", BASE / "data"))
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
PAGES_JSONL = CLEAN_DIR / "pages.jsonl"
CHUNKS_JSONL = CLEAN_DIR / "chunks.jsonl"

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", BASE / "chroma"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
TOP_K = int(os.getenv("TOP_K", "5"))

# Cloudflare Workers AI
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_MODEL = os.getenv("CF_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# 爬虫
SCRAPE_MAX_PAGES = int(os.getenv("SCRAPE_MAX_PAGES", "200"))
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "0.5"))

ALLOWED_DOMAINS = [
    "daisakuikeda.org",
    "zh.wikiquote.org",
    "zh.wikipedia.org",
    "ja.wikipedia.org",
    "en.wikipedia.org",
]

SEED_URLS = [
    "https://www.daisakuikeda.org/cht/sub/quotations/index.html",
    "https://www.daisakuikeda.org/cht/sub/quotations/theme/",
    "https://www.daisakuikeda.org/cht/sub/resources/works/essays/youth/",
    "https://www.daisakuikeda.org/cht/sub/resources/works/essays/peace-essays/",
    "https://www.daisakuikeda.org/cht/sub/resources/works/essays/educ-essays/",
    "https://www.daisakuikeda.org/cht/main/profile/bio/bio-01.html",
    "https://zh.wikiquote.org/wiki/%E6%B1%A0%E7%94%B0%E5%A4%A7%E4%BD%9C",
    "https://zh.wikipedia.org/wiki/%E6%B1%A0%E7%94%B0%E5%A4%A7%E4%BD%9C",
    "https://ja.wikipedia.org/wiki/%E6%B1%A0%E7%94%B0%E5%A4%A7%E4%BD%9C",
]

SYSTEM_PROMPT_FILE = BASE / "persona" / "system_prompt.txt"

# 知识库覆盖说明（诚实标注范围）
KB_SCOPE_NOTE = (
    "知识库以池田大作官方网站(daisakuikeda.org)的中文箴言/随笔/对谈/生平，"
    "以及 Wikipedia / Wikiquote 词条为主源。可在此基础上追加更多来源。"
)
