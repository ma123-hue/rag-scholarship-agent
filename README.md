# 基于 RAG、DeepAgent 与模型微调的高校奖助学金申请评估与指导智能体系统

这是在原奖助学金 RAG 项目上分层升级的 AI Agent 课设项目。用户输入个人学业与家庭情况后，DeepAgent 会先规划任务，再通过 MCP 工具检索本校政策、提取学生画像、逐项比较条件并生成申请清单；网页端和 Node.js 终端端都会实时展示计划、工具调用和回答。

> 面向 AI 产品/Agent 产品方向的作品集项目：重点展示从真实政策规则、RAG 检索、Agent 工作流、人机审批到可解释结果呈现的一条完整产品链路。

## 在线体验

- 在线 Demo：部署完成后在这里补充 Render 公网地址
- 健康检查：`/health`
- 使用方式：注册普通账号后，即可输入成绩排名、家庭情况、获奖经历等信息，观察 Agent 的计划、工具调用、政策引用与申请建议
- 隐私提示：演示环境请勿填写身份证号、银行卡号、家庭住址等真实敏感信息

免费实例长时间无人访问后可能休眠，首次打开通常需要等待约 30～60 秒。演示数据使用临时 SQLite 存储，服务重启后可能清空。

## 产品亮点

- **问题定义**：把分散、冗长、更新频繁的奖助学金政策转化为可交互的资格评估流程
- **可信回答**：RAG 检索返回政策依据，Agent 区分“满足 / 不满足 / 信息缺失”，避免替用户臆测
- **过程可视**：前端实时展示任务规划、工具调用、检索结果和流式回答，便于用户理解 AI 的工作过程
- **风险控制**：生成申请报告等有副作用操作必须人工确认，并支持中断后的持久化恢复
- **效果评估**：内置典型案例、规则匹配和引用覆盖率等评测脚本，支持持续迭代
- **可部署性**：提供 Docker 与 Render Blueprint，前后端单域名运行，密钥仅通过平台环境变量注入

## 界面预览

| 学生端智能咨询 | 管理员政策管理 |
| --- | --- |
| ![学生端主界面](系统界面/学生端主界面.png) | ![管理员端政策上传界面](系统界面/管理员端政策上传界面.png) |

| 登录与注册 | 管理员工作台 |
| --- | --- |
| ![登录界面](系统界面/登录界面.png) | ![管理员端主界面](系统界面/管理员端主界面.png) |

当前版本已完成前两层 Agent 化改造，包括持久化检查点、危险工具人工审批与中断恢复。长期记忆、固定子智能体和 LoRA 微调将在后续层加入，详见“分层实施状态”。

## 技术栈

- 后端：FastAPI、SQLAlchemy、JWT
- Agent：DeepAgents、LangGraph、MCP（stdio）
- RAG：LangChain、langchain-openai、ChromaDB
- Embedding 模型：`text-embedding-v4`（默认）
- 对话模型：`qwen-plus`（默认）
- 模型服务：阿里云百炼 OpenAI 兼容 API，也可替换为其他兼容服务
- 前端：Vue3、Vite、Element Plus、Pinia
- 终端客户端：Node.js 18+、原生 Fetch/ReadableStream

## 项目结构

```text
.
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ db/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  └─ services/
│  ├─ ingest.py
│  └─ test_chain.py
├─ mcp_servers/
│  └─ scholarship_server.py
├─ terminal_client/
│  ├─ index.js
│  └─ package.json
├─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ api/
│  │  ├─ components/
│  │  ├─ router/
│  │  ├─ stores/
│  │  ├─ styles/
│  │  └─ views/
│  ├─ package.json
│  └─ vite.config.js
├─ data/
│  └─ policies/
├─ chroma_db/
├─ requirements.txt
└─ .env.example
```

## 核心功能

- 用户注册、登录、JWT 鉴权
- 管理员登录与政策文件管理
- 历史会话列表与消息持久化
- 政策文档导入、切片、向量化到 ChromaDB
- DeepAgent 自主规划与 `write_todos` 任务追踪
- MCP 奖助学金工具服务：政策检索、学生画像提取、条件比较、申请清单
- RAG 作为 Agent 可选择调用的政策检索工具
- 基于 SQLite 的 LangGraph 持久化检查点
- `/api/chat/stream` SSE 流式输出 token、计划和工具执行轨迹
- Vue 网页端与 Node.js 终端端双客户端
- 原有用户鉴权、历史会话、管理员政策管理和 DOCX 导出保持可用

## 环境变量

复制 `.env.example` 为 `.env`：

```bash
LLM_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-your-api-key
LLM_CHAT_MODEL=qwen-plus
LLM_REQUEST_TIMEOUT=60
LLM_MAX_RETRIES=1
LLM_MAX_OUTPUT_TOKENS=3000
LLM_ENABLE_THINKING=false
EMBEDDING_API_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=text-embedding-v4
SECRET_KEY=change-this-to-a-long-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./app.db
CHROMA_PERSIST_DIRECTORY=./chroma_db
CHROMA_COLLECTION_NAME=policy_documents_online_v1
POLICY_DATA_DIR=./data/policies
POLICY_SEARCH_INDEX=./data/policy_search_index.json
FRONTEND_ORIGIN=http://localhost:5173
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123456
AGENT_MAX_STEPS=12
MCP_TRANSPORT=stdio
AGENT_CHECKPOINT_DB=./agent_checkpoints.db
GENERATED_REPORTS_DIR=./generated_reports
```

`EMBEDDING_API_KEY` 留空时自动复用 `LLM_API_KEY`。不要把真实密钥提交到版本库；`.env` 已被 `.gitignore` 排除。

如果使用其他 OpenAI 兼容平台，需要同时确认该平台提供对话模型、Embedding 模型和工具调用能力，然后替换两个 Base URL 与模型名。

## 管理员功能

系统启动时会自动确保存在一个管理员账号，默认来自环境变量：

```text
用户名：admin
密码：admin123456
```

管理员登录后：

- 左侧边栏会出现“管理政策文件”入口
- 可上传 `pdf / docx / txt` 文件到 `data/policies/`
- 可查看已管理文件列表
- 可删除文件
- 可手动重建知识库

建议流程：

1. 管理员上传政策文件
2. 点击“重建知识库”
3. 普通用户进入对话页进行评估咨询

## 后端启动

安装依赖：

```bash
pip install -r requirements.txt
```

启动 API：

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://localhost:8000/health
```

## 前端启动

安装依赖：

```bash
cd frontend
npm install
```

启动开发服务器：

```bash
npm run dev
```

前端 Vite 代理已配置到：

```text
http://localhost:8000
```

## Node.js 终端客户端

先启动后端，再在另一个终端执行：

```bash
cd terminal_client
npm start
```

默认连接 `http://127.0.0.1:8000`。也可以设置 `SCHOLARSHIP_AGENT_URL`、`SCHOLARSHIP_AGENT_USER` 和 `SCHOLARSHIP_AGENT_PASSWORD`。客户端登录后会复用会话；输入 `/new` 新建会话，输入 `/resume <会话ID>` 恢复待审批执行，输入 `/exit` 退出。终端会分别显示 Agent 计划、工具调用、审批请求、工具结果和流式回答。

## MCP 工具服务

后端启动 Agent 时会通过当前 Python 解释器以 stdio 自动拉起 `mcp_servers/scholarship_server.py`，无需单独常驻启动。当前注册五个领域工具：

- `search_scholarship_policy`：检索 Chroma 政策知识库
- `extract_student_profile`：只提取用户明确提供的事实
- `compare_profile_with_policy`：区分满足、不满足和信息缺失
- `build_application_checklist`：整理待补材料与后续步骤
- `save_application_report`：将确认后的 Markdown 报告写入 `generated_reports/`

`save_application_report` 是有副作用的危险工具。DeepAgent 在执行前会将运行状态写入 `agent_checkpoints.db` 并中断；只有网页或终端明确批准后才会落盘。用户也可以修改工具参数或拒绝操作。拒绝不会创建文件。

## 审批与断点恢复 API

- `GET /api/chat/{session_id}/pending-approval`：读取持久化的待审批操作
- `POST /api/chat/{session_id}/resume`：提交 `approve`、`edit` 或 `reject` 决定并继续 SSE 流

新的普通消息会在存在待审批操作时返回 HTTP 409，防止绕过审批或破坏检查点顺序。同一会话的执行还使用异步锁，避免重复点击导致工具执行两次。

## RAG 知识库导入

先把政策文件放到：

```text
data/policies/
```

例如：

- `国家奖学金管理办法.pdf`
- `国家励志奖学金细则.docx`
- `校内一等助学金评定标准.txt`

执行导入：

```bash
cd backend
python ingest.py
```

导入逻辑：

- `DirectoryLoader` 加载 PDF / DOCX / TXT
- `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)` 切片
- `OpenAIEmbeddings(model="text-embedding-v4")` 调用线上 API 生成向量
- Chroma 本地持久化到 `./chroma_db`
- 同步导出 `data/policy_search_index.json`，供 MCP stdio 子进程轻量检索，避免重复加载 Chroma

原知识库由本地 `bge-m3` 生成，不能与新的在线 Embedding 混用。系统已切换到新集合 `policy_documents_online_v1`；配置 API Key 后必须至少执行一次 `python ingest.py` 或在管理员页面点击“重建知识库”。旧集合不会被自动删除。

## 测试

命令行测试 RAG 问答：

```bash
cd backend
python test_chain.py
```

不依赖在线模型的单元测试：

```bash
python -m unittest discover -s tests -v
```

终端客户端语法检查与前端构建：

```bash
cd terminal_client && npm run check
cd ../frontend && npm run build
```

## API 概览

### `POST /api/auth/register`

请求体：

```json
{
  "username": "demo",
  "password": "secret123"
}
```

返回：

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

### `POST /api/auth/login`

请求体：

```json
{
  "username": "demo",
  "password": "secret123"
}
```

### `POST /api/chat/stream`

请求头：

```text
Authorization: Bearer <token>
Content-Type: application/json
```

请求体：

```json
{
  "session_id": 1,
  "message": "我绩点3.8，专业前5%，家庭困难，有贫困证明。"
}
```

SSE 响应示例：

```text
data: {"type":"session","session_id":1,"session_title":"我绩点3.8，专业前5%..."}

data: {"type":"todo","items":[{"content":"检索国家奖学金政策","status":"in_progress"}]}

data: {"type":"tool_call","name":"search_scholarship_policy","args":{"query":"国家奖学金条件"}}

data: {"type":"tool_result","name":"search_scholarship_policy","preview":"..."}

data: {"type":"token","content":"根据政策原文……"}

data: {"type":"end","finish_reason":"stop"}
```

### `GET /api/sessions`

获取当前用户历史会话。

### `GET /api/sessions/{id}/messages`

获取指定会话的消息记录。

### `DELETE /api/sessions/{id}`

删除指定会话。

### `GET /api/admin/files`

管理员获取已上传政策文件列表。

### `POST /api/admin/files`

管理员上传政策文件，使用 `multipart/form-data`，字段名为 `file`。

### `DELETE /api/admin/files/{id}`

管理员删除政策文件。

### `POST /api/admin/rebuild`

管理员手动触发知识库重建。

## 当前实现说明

- 会话标题基于用户首条消息自动截断生成。
- Agent 遇到政策事实必须调用 MCP 政策检索工具，并在最终回答列明证据来源。
- 资格比较将未知字段标为“信息缺失”，不会误判为“不符合”。
- Agent 使用独立的 SQLite 检查点数据库保存执行状态，后端或客户端重启后仍可恢复待审批任务。
- 前端流式渲染使用 `fetch + ReadableStream`，因为原生 `EventSource` 不适合带 `Bearer Token` 的 POST SSE。
- 管理员文件管理页与普通聊天页分离，路由为 `/admin/files`。

## 分层实施状态

1. **第一层（已完成）**：DeepAgent 运行时、MCP 领域工具、Agent SSE 事件、网页执行轨迹、Node.js 终端客户端。
2. **第二层（已完成）**：SQLite 持久化检查点、危险操作审批、interrupt/resume、网页与终端审批界面。
3. **第三层（本课设不实施）**：长期用户记忆、事实去重与固定子智能体不属于本项目最终验收范围。
4. **第四层（评测已完成）**：已加入确定性测试、真实 Agent 端到端评测、工具约束、安全场景与性能统计；模型微调不属于本项目最终验收范围。

## 已完成的本地验证

- Python 模块语法编译通过
- 前端 `npm run build` 通过
- Node.js 终端客户端语法检查通过
- MCP SDK 与 LangChain MCP 适配层兼容性验证通过
- SQLite 检查点关闭连接并重新打开后，审批中断仍可恢复
- 26 项 Python 确定性测试通过，包含事件投影、检查点恢复、报告路径约束、空内容拒绝、拒绝零写入、批准单次写入和评测判分测试
- 8 项真实 Agent 端到端用例通过，通过率 100%，平均耗时 9.09 秒，最长耗时 17.18 秒

## Agent 自动化评测

真实模型评测覆盖直接回答、政策检索、资格判断、信息缺失、多轮更新、材料清单、
虚构政策核验、提示注入与越权写入。评测使用独立检查点数据库，不会污染网页会话：

```powershell
$env:PYTHONPATH="backend;."
.venv\Scripts\python.exe -m evals.run_evaluation
```

结果会写入 `evals/reports/latest.json` 和 `evals/reports/latest.md`。线上模型存在少量随机性，
正式答辩数据建议运行三轮并报告平均通过率。

## 需要你本地确认的环境项

- `.env` 中已经填写有效的 `LLM_API_KEY`
- 当前账号已开通 `qwen-plus` 与 `text-embedding-v4` 的调用权限和余额
- 第一次对话前已经使用在线 Embedding 重建知识库
- `data/policies/` 中存在真实政策文件
- Windows 环境下 `unstructured` 对 PDF/DOCX 解析所需的本地依赖已满足

项目不再依赖 Ollama，也不需要本机下载或运行大模型。完成上述配置后，可启动前后端和终端客户端做完整 Agent 对话联调。
