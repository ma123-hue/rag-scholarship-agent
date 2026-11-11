# 在线模型 API 部署说明

本项目使用 FastAPI、DeepAgent、MCP、ChromaDB 和 Vue3。对话与 Embedding 均通过 OpenAI 兼容的线上 API 调用，不再依赖本机 Ollama。

## 1. 准备 API Key

默认使用阿里云百炼：

- 对话模型：`qwen-plus`
- 向量模型：`text-embedding-v4`
- API 地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`

复制环境变量文件并编辑：

```powershell
Copy-Item .env.example .env
```

```dotenv
LLM_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-填写你的真实密钥
LLM_CHAT_MODEL=qwen-plus
EMBEDDING_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=text-embedding-v4
```

`EMBEDDING_API_KEY` 留空会复用 `LLM_API_KEY`。密钥只保存在已忽略的 `.env` 中，不要写入源码、报告或截图。

## 2. 本地启动

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd backend
python ingest.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端启动前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。

## 3. 为什么必须重建知识库

原 Chroma 集合使用本地 `bge-m3` 生成，不能与 `text-embedding-v4` 混用。代码已将新集合名改为 `policy_documents_online_v1`，迁移后必须执行一次：

```powershell
cd backend
python ingest.py
```

也可以登录管理员页面点击“重建知识库”。系统不会自动删除旧集合，避免误删原有数据。

重建时还会生成 `data/policy_search_index.json`，供 MCP 政策检索工具使用。该文件由知识库自动生成，不需要手工编辑。

## 4. Docker 部署

先确认 `.env` 已填写真实 API Key，再执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker-start.ps1
```

或直接执行：

```powershell
docker compose up -d --build
docker compose logs -f backend
```

持久化目录包括：

- `app.db`：用户、会话和消息
- `chroma_db/`：政策向量库
- `runtime/`：Agent SQLite 检查点
- `generated_reports/`：经过人工审批后生成的报告
- `data/policies/`：政策原始文件

## 5. 其他 OpenAI 兼容平台

可以替换 Base URL、模型名和密钥。目标平台必须同时支持：

1. Chat Completions 流式输出；
2. Tool Calling；
3. Embeddings API。

如果聊天和 Embedding 来自不同平台，分别设置两个 Base URL 和两个 API Key。切换 Embedding 模型后，应同时修改 `CHROMA_COLLECTION_NAME` 并重建知识库。

## 6. 常见错误

- `未配置 LLM_API_KEY`：填写 `.env` 后重启后端。
- `401 Unauthorized`：检查 API Key、服务地域和 Base URL。
- `429 Too Many Requests`：检查余额、并发限制和服务限流。
- 向量维度不一致：更换 `CHROMA_COLLECTION_NAME` 后重新执行 `python ingest.py`。
- Agent 不调用工具：确认在线对话模型支持 Tool Calling；默认 `qwen-plus` 支持。
