# AI 师匠（AI Shishō）

以池田大作（1928–2023）的思想内核与语言风格行事的对话式 AI，
把他的箴言、随笔、对谈、生平汇成 RAG 知识库，通过 Telegram 与你对话。
底层：本地 Chroma 向量检索 + 生成层（Cloudflare Workers AI 或 OpenAI 兼容后端如 Nous hy3）。

## 架构

```
网络抓取 ──> pages.jsonl ──> 切分 chunks.jsonl ──> Chroma 向量索引
                                                      │
用户消息 ──> Retriever(top-k) ──> 拼装 prompt ──> 生成层(CF / Nous hy3) ──> Telegram
```

## 1. 安装

> 注意：本项目自带 `.venv`（已装好全部依赖）。由于运行环境里 `$ uv run` 会误用宿主 Python（与本项目依赖冲突），请**始终用项目内的 python 解释器**运行：
> `./.venv/Scripts/python.exe main.py <命令>`（Linux/macOS 用 `./.venv/bin/python`）。

```bash
cd ai-shisho
cp .env.example .env   # 然后填入你的凭据
```

依赖：`requirements.txt`（requests / beautifulsoup4 / html2text / chromadb / sentence-transformers / python-telegram-bot / python-dotenv / tqdm）。

## 2. 配置 `.env`

`.env` 需要填三类凭据，下面逐项说明怎么申请。

### 2.1 Telegram Bot（必填）

1. 在 Telegram 搜索 `@BotFather`，发 `/newbot`，按提示取名字，得到一串 `123456789:AAE...` 的 token。
2. 把这段 token 填进 `.env`：
   ```
   TELEGRAM_BOT_TOKEN=你的_BotFather_Token
   ```
3. 启动：`python bot/run.py`（或 `python main.py bot`）。
4. 命令：`/start` 欢迎、`/about` 师匠是谁、`/source` 切换引用来源、`/teach <反馈>` 教它、`/forget` 收起记忆、`/wipe` 删存档、`/daily` 今日一句。

### 2.2 生成层（二选一，必填其一）

生成回复的模型有两套，代码优先级：**先走 OpenAI 兼容后端（Nous hy3），没配才走 Cloudflare**。

#### 方案 A：Nous Research（推荐，本项目当前在用）

免费、OpenAI 兼容、无需信用卡。本项目默认走这个。

1. 打开 https://inference-api.nousresearch.com/ 或 Nous 控制台申请 API key（注册即有）。
2. 在 `.env` 填：
   ```
   LLM_BACKEND=nous
   LLM_BASE_URL=https://inference-api.nousresearch.com/v1
   LLM_MODEL=tencent/hy3:free      # 免费模型；也可换其他 Nous 模型
   LLM_API_KEY=你的_nous_api_key
   ```
3. 代码里 `shisho.py` 检测到 `LLM_BASE_URL` 非空，就向 `{LLM_BASE_URL}/chat/completions` 发 OpenAI 格式请求。

#### 方案 B：Cloudflare Workers AI（备用）

1. 登录 https://dash.cloudflare.com/，左侧 **Workers & Pages → AI** 开通 Workers AI。
2. 记下来你的 **Account ID**（右侧边栏 “Account ID”）。
3. 右上角 **Manage API Tokens → Create Token**，权限勾 **Workers AI: Edit**（或 Account AI: Read/Write），生成 token。
4. 在 `.env` 填：
   ```
   CF_ACCOUNT_ID=你的_cloudflare_account_id
   CF_API_TOKEN=你的_cloudflare_api_token
   CF_MODEL=@cf/meta/llama-3.3-70b-instruct-fp8-fast
   ```
5. **注意**：若同时设了 `LLM_BASE_URL`，代码会优先走 Nous，CF 不会生效。只想用 CF 就把 `LLM_BASE_URL` 留空。

### 2.3 RAG / 路径（一般无需改）

```
DATA_DIR=./data
CHROMA_DIR=./chroma
EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2
CHUNK_CHARS=600
CHUNK_OVERLAP=100
TOP_K=5
```

## 3. 构建知识库（首次）

```bash
python main.py scrape    # 抓 daisakuikeda.org / Wikipedia 等源
python main.py chunk     # 切分 chunks.jsonl
python main.py index     # 建 Chroma 向量索引
python main.py ask "青年如何面对失败？"   # 本地单条测试
```

## 4. 运行

```bash
python main.py bot       # 启动 Telegram bot
# 或
python bot/run.py
```

打开 Telegram 给你的 bot 发消息即可对话。

## 5. 目录

```
ai-shisho/
├── main.py              # 命令行入口 (scrape/chunk/index/ask/bot)
├── config.py            # 全局配置 (读 .env)
├── bot/run.py           # Telegram bot
├── generator/shisho.py  # 生成层 (RAG 检索 + 调 CF / Nous)
├── rag/                 # 抓取/切分/建索引/检索
├── scraper/             # 网页抓取
├── importer/            # epub/书籍导入
├── persona/system_prompt.txt  # 陪伴基调
├── skills/ikeda-perspective/  # 池田认知框架
├── tools/               # 爬虫/启动/中继等工具
├── data/                # 语料 (gitignore, 不入库)
└── chroma/              # 向量库 (gitignore, 不入库)
```

## 6. 已知注意

- `.env` / `data/` / `chroma/` 已在 `.gitignore` 排除，不会进仓库。
- 生成层若都未配置，bot 会降级为「只回检索片段 + 提示」，不会崩溃。
- 本项目仅供学习研究，内容来自 AI，不构成任何专业建议。
