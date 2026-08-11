# AI 师匠（AI Shishō）

以池田大作（1928–2023）的思想内核与语言风格行事的对话式 AI，
把他的箴言、随笔、对谈、生平汇成 RAG 知识库，通过 Telegram 与你对话。
底层：本地 Chroma 向量检索 + Cloudflare Workers AI 生成。

## 架构
```
网络抓取 ──> pages.jsonl ──> 切分 chunks.jsonl ──> Chroma 向量索引
                                                      │
用户消息 ──> Retriever(top-k) ──> 拼装 prompt ──> Cloudflare Workers AI ──> Telegram
```

## 1. 安装
> 注意：本项目自带 `.venv`（已装好全部依赖）。由于运行环境里 `$ uv run` 会误用宿主 Python（与本项目依赖冲突），请**始终用项目内的 python 解释器**运行：
> `./.venv/Scripts/python.exe main.py <命令>`（Linux/macOS 用 `./.venv/bin/python`）。

```bash
cd ai-shisho
cp .env.example .env   # 然后填入你的凭据
```

## 2. 配置 .env
| 变量 | 说明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather 创建的 bot token |
| `CF_ACCOUNT_ID` | Cloudflare 账户 ID |
| `CF_API_TOKEN` | Cloudflare API Token（需 Workers AI 权限） |
| `CF_MODEL` | 默认 `@cf/meta/llama-3.3-70b-instruct-fp8-fast` |
| `EMBED_MODEL` | 默认多语嵌入 `paraphrase-multilingual-MiniLM-L12-v2` |
| `TOP_K` | 检索片段数，默认 5 |

## 3. 构建知识库
```bash
./.venv/Scripts/python.exe main.py scrape   # 抓取（默认 ~200 页，限放行域名）
./.venv/Scripts/python.exe main.py chunk     # 文本切分
./.venv/Scripts/python.exe main.py index     # 建 Chroma 索引
```
抓取源默认：daisakuikeda.org（中文箴言/随笔/对谈/生平）+ 中/日/英 Wikipedia + 中文 Wikiquote。
要扩展：编辑 `config.py` 的 `SEED_URLS` 与 `ALLOWED_DOMAINS`。

## 4. 本地单条测试
```bash
./.venv/Scripts/python.exe main.py ask "青年应该如何面对失败？"
```
> 未配置 Cloudflare 凭据时，会降级返回检索到的知识片段（验证检索链路用）。

## 5. 连接 Telegram
```bash
# 在 .env 填入 TELEGRAM_BOT_TOKEN 后：
./.venv/Scripts/python.exe main.py bot
```
Bot 命令：`/start` `/about` `/source`（切换是否显示引用来源）。私聊直接说话即可。

## 6. 诚实边界
- 知识库范围有限，覆盖官方站与百科词条；生成层不编造具体引文/日期。
- 心理危机/疾病/法律问题会引导寻求专业援助，不越界。
- 不传教、不排他，谈和平立足普遍人性价值。
