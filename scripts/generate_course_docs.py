from __future__ import annotations

import json
import shutil
import sqlite3
import zlib
from datetime import date
from pathlib import Path
from typing import Iterable

import requests
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT.parent / "专业方向综合实习课程指导书" / "课程指导书-发布-26"
GROUP_TEMPLATE = (
    TEMPLATE_ROOT
    / "软件工程专业方向综合实习-软件2201-教师姓名"
    / "系统名称-组长班级-组长姓名"
    / "组长班级-组长姓名-小组.docx"
)
PERSONAL_TEMPLATE = (
    TEMPLATE_ROOT
    / "软件工程专业方向综合实习-软件2201-教师姓名"
    / "系统名称-组长班级-组长姓名"
    / "个人班级-个人姓名-个人.docx"
)
ACCEPTANCE_TEMPLATE = TEMPLATE_ROOT / "软件学院-班级名称-组长姓名-系统名称-验收记录表.docx"

SYSTEM_NAME = "基于LangChain的高校奖助学金申请条件评估与指导系统"
CLASS_NAME = "软件2201班"
COURSE_NAME = "软件工程专业方向综合实习"
TEACHER_NAME = "冯秀芳"
LEADER = {"name": "张三", "id": "2022001684", "role": "组长"}
MEMBERS = [
    LEADER,
    {"name": "李四", "id": "2022001685", "role": "组员"},
    {"name": "王五", "id": "2022001686", "role": "组员"},
]
OUT_ROOT = ROOT / "课程实习文档" / f"{SYSTEM_NAME}-{CLASS_NAME}-{LEADER['name']}"
FIG_DIR = OUT_ROOT / "figures"
PUML_DIR = OUT_ROOT / "plantuml"
TODAY_TEXT = "2026年 06 月 26 日"


PLANTUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _enc6(value: int) -> str:
    return PLANTUML_ALPHABET[value & 0x3F]


def _append3bytes(b1: int, b2: int, b3: int) -> str:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    return _enc6(c1) + _enc6(c2) + _enc6(c3) + _enc6(c4)


def plantuml_encode(text: str) -> str:
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]
    encoded: list[str] = []
    for i in range(0, len(compressed), 3):
        chunk = compressed[i : i + 3]
        if len(chunk) == 3:
            encoded.append(_append3bytes(chunk[0], chunk[1], chunk[2]))
        elif len(chunk) == 2:
            encoded.append(_append3bytes(chunk[0], chunk[1], 0))
        elif len(chunk) == 1:
            encoded.append(_append3bytes(chunk[0], 0, 0))
    return "".join(encoded)


def render_plantuml(name: str, source: str) -> Path:
    PUML_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    puml_path = PUML_DIR / f"{name}.puml"
    png_path = FIG_DIR / f"{name}.png"
    puml_path.write_text(source, encoding="utf-8")
    if png_path.exists() and png_path.stat().st_size > 0:
        return png_path
    url = f"https://www.plantuml.com/plantuml/png/{plantuml_encode(source)}"
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    if not response.content.startswith(b"\x89PNG"):
        raise RuntimeError(f"PlantUML render failed for {name}")
    png_path.write_bytes(response.content)
    return png_path


DIAGRAM_SOURCES = {
    "architecture": """
@startuml
skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName Microsoft YaHei
left to right direction
actor "学生用户" as Student
actor "管理员" as Admin
rectangle "浏览器端 Vue3 应用" as Frontend {
  [AuthView 登录注册]
  [ChatView 智能问答]
  [SessionSidebar 历史会话]
  [AdminFilesView 政策文件管理]
  [Pinia 状态管理]
}
rectangle "FastAPI 后端服务" as Backend {
  [auth.py 认证接口]
  [chat.py SSE 流式问答]
  [sessions.py 会话接口]
  [admin.py 文件管理接口]
  [rag_chain.py RAG 服务]
  [ingest.py 知识库重建]
}
database "SQLite\\napp.db" as SQLite
database "ChromaDB\\npolicy_documents" as Chroma
folder "data/policies\\nPDF DOCX TXT" as Policies
cloud "Ollama 模型服务\\nqwen2.5:7b / bge-m3" as Ollama
Student --> Frontend : 登录、咨询、查看历史
Admin --> Frontend : 上传政策、重建知识库
Frontend --> Backend : HTTP JSON / POST SSE
Backend --> SQLite : 用户、会话、消息、文件记录
Backend --> Chroma : MMR Top-5 检索
Backend --> Ollama : Embedding 与对话生成
Backend --> Policies : 读取和保存政策原文
Policies --> Chroma : 切片向量化
@enduml
""",
    "use_case": """
@startuml
skinparam defaultFontName Microsoft YaHei
left to right direction
actor "学生用户" as Student
actor "管理员" as Admin
rectangle "奖助学金申请条件评估与指导系统" {
  usecase "注册账号" as UC1
  usecase "登录系统" as UC2
  usecase "新建评估会话" as UC3
  usecase "输入个人条件" as UC4
  usecase "接收资格匹配度与建议" as UC5
  usecase "查看历史会话" as UC6
  usecase "删除历史会话" as UC7
  usecase "上传政策文件" as UC8
  usecase "删除政策文件" as UC9
  usecase "重建向量知识库" as UC10
  usecase "查看文件清单" as UC11
}
Student --> UC1
Student --> UC2
Student --> UC3
Student --> UC4
Student --> UC5
Student --> UC6
Student --> UC7
Admin --> UC2
Admin --> UC8
Admin --> UC9
Admin --> UC10
Admin --> UC11
UC4 ..> UC5 : include
UC8 ..> UC10 : extend
UC9 ..> UC10 : extend
@enduml
""",
    "business_flow": """
@startuml
skinparam defaultFontName Microsoft YaHei
start
:用户进入前端页面;
if (是否已有 Token?) then (是)
  :路由守卫进入聊天页;
else (否)
  :登录或注册;
  :后端校验密码并签发 JWT;
endif
:加载历史会话列表;
if (管理员需要维护政策?) then (是)
  :进入政策文件管理页;
  :上传或删除 PDF/DOCX/TXT;
  :调用重建知识库接口;
  :解析文档、切片、写入 Chroma;
else (否)
endif
:用户输入绩点、排名、家庭情况等条件;
:前端通过 POST SSE 调用 /api/chat/stream;
:后端创建或校验会话;
:RAG 检索政策条款并组织提示词;
:Ollama 生成资格评估与申请建议;
:前端逐字渲染回复并展示匹配度;
:数据库保存用户消息和助手消息;
stop
@enduml
""",
    "function_modules": """
@startmindmap
skinparam defaultFontName Microsoft YaHei
* 奖助学金评估与指导系统
** 用户认证模块
*** 注册
*** 登录
*** JWT 鉴权
*** 管理员权限校验
** 智能问答模块
*** 新建会话
*** 流式生成
*** 政策检索
*** 匹配度解析展示
** 会话管理模块
*** 历史列表
*** 消息查询
*** 会话删除
*** 最近 5 轮记忆
** 政策文件管理模块
*** 文件上传
*** 文件列表
*** 文件删除
*** 知识库重建
** 知识库与模型模块
*** DirectoryLoader
*** RecursiveCharacterTextSplitter
*** Chroma 向量库
*** Ollama Embedding
*** ChatOllama 对话模型
** 前端交互模块
*** Vue Router
*** Pinia Store
*** Element Plus
*** Markdown 安全渲染
@endmindmap
""",
    "er": """
@startuml
skinparam defaultFontName Microsoft YaHei
hide methods
skinparam classAttributeIconSize 0
class users {
  id : INTEGER PK
  username : VARCHAR(50) UNIQUE
  password_hash : VARCHAR(255)
  is_admin : BOOLEAN
  created_at : DATETIME
}
class chat_sessions {
  id : INTEGER PK
  user_id : INTEGER FK
  session_title : VARCHAR(120)
  created_at : DATETIME
  updated_at : DATETIME
}
class messages {
  id : INTEGER PK
  session_id : INTEGER FK
  role : VARCHAR(20)
  content : TEXT
  timestamp : DATETIME
}
class policy_files {
  id : INTEGER PK
  filename : VARCHAR(255) UNIQUE
  original_filename : VARCHAR(255)
  file_type : VARCHAR(20)
  size_bytes : INTEGER
  uploaded_by : VARCHAR(50)
  created_at : DATETIME
}
users "1" -- "0..*" chat_sessions : 拥有
chat_sessions "1" -- "0..*" messages : 包含
users "1" .. "0..*" policy_files : 上传人用户名
@enduml
""",
    "rag_sequence": """
@startuml
skinparam defaultFontName Microsoft YaHei
actor "学生用户" as User
participant "ChatView.vue" as View
participant "chat.js\\nstreamChat" as Api
participant "chat.py\\n/stream" as Route
participant "RAGChain" as Chain
database "ChromaDB" as Chroma
participant "Ollama\\nqwen2.5:7b" as LLM
database "SQLite" as DB
User -> View : 输入个人条件并发送
View -> Api : 调用 streamChat(token, sessionId, message)
Api -> Route : POST /api/chat/stream\\nBearer Token
Route -> DB : 校验用户并创建/读取会话
Route -> Chain : astream_answer(db, session_id, message)
Chain -> Chroma : MMR 检索 Top-5 政策片段
Chroma --> Chain : 返回条款来源与内容
Chain -> DB : 读取最近 10 条消息形成 5 轮摘要
Chain -> LLM : 系统提示词 + 历史 + 条款 + 用户输入
LLM --> Chain : 流式 token
Chain -> DB : RunnableWithMessageHistory 写入消息
Route --> Api : SSE session/token/end
Api --> View : 逐块解析并更新消息
View --> User : 显示资格匹配度、条件差异、材料建议
@enduml
""",
    "deployment": """
@startuml
skinparam defaultFontName Microsoft YaHei
node "用户终端" {
  artifact "浏览器" as Browser
  artifact "Vue3 SPA\\nlocalhost:5173" as SPA
}
node "应用服务器" {
  artifact "FastAPI 服务\\nuvicorn 0.0.0.0:8000" as FastAPI
  database "SQLite app.db" as DB
  folder "data/policies" as Data
  database "chroma_db" as Vector
}
node "模型服务器或本机 Ollama" {
  component "Ollama API\\n:11434" as Ollama
  artifact "qwen2.5:7b" as ChatModel
  artifact "bge-m3" as EmbedModel
}
Browser --> SPA
SPA --> FastAPI : Vite proxy /api
FastAPI --> DB
FastAPI --> Data
FastAPI --> Vector
FastAPI --> Ollama : HTTP
Ollama --> ChatModel
Ollama --> EmbedModel
@enduml
""",
    "frontend_components": """
@startuml
skinparam componentStyle rectangle
skinparam defaultFontName Microsoft YaHei
package "frontend/src" {
  [main.js] --> [router/index.js]
  [main.js] --> [Pinia]
  [router/index.js] --> [AuthView.vue]
  [router/index.js] --> [ChatView.vue]
  [router/index.js] --> [AdminFilesView.vue]
  [ChatView.vue] --> [SessionSidebar.vue]
  [ChatView.vue] --> [ChatBubble.vue]
  [ChatView.vue] --> [ChatComposer.vue]
  [ChatView.vue] --> [stores/chat.js]
  [stores/chat.js] --> [api/chat.js]
  [AuthView.vue] --> [stores/auth.js]
  [stores/auth.js] --> [localStorage]
  [AdminFilesView.vue] --> [api/admin.js]
}
@enduml
""",
    "test_flow": """
@startuml
skinparam defaultFontName Microsoft YaHei
start
:准备 .env、SQLite、Ollama 模型和政策文件;
:后端语法与依赖检查;
:启动 FastAPI 并访问 /health;
:注册普通用户并登录获取 JWT;
:测试会话列表、消息查询和删除;
:管理员登录;
:上传政策文件并检查 policy_files 记录;
:重建 Chroma 向量知识库;
:前端 npm run build;
:浏览器联调登录、问答、历史会话、文件管理;
if (发现异常?) then (是)
  :定位接口、状态管理或知识库问题;
  :修复后回归测试;
else (否)
endif
:形成测试记录和验收材料;
stop
@enduml
""",
}


def ensure_diagrams() -> dict[str, Path]:
    return {name: render_plantuml(name, source.strip()) for name, source in DIAGRAM_SOURCES.items()}


def set_run_font(run, size: int | None = None, bold: bool | None = None, font_name: str = "宋体") -> None:
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold


def clear_paragraph(paragraph) -> None:
    p = paragraph._p
    for child in list(p):
        p.remove(child)


def set_paragraph(paragraph, text: str, size: int | None = None, bold: bool | None = None) -> None:
    clear_paragraph(paragraph)
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold)


def set_cell_text(cell, text: str, size: int = 10) -> None:
    cell.text = ""
    for idx, part in enumerate(text.split("\n")):
        p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
        run = p.add_run(part)
        set_run_font(run, size=size)
        p.paragraph_format.line_spacing = 1.2


def setup_document(doc: Document) -> None:
    for style_name in ["Normal", "Body Text"]:
        if style_name in doc.styles:
            style = doc.styles[style_name]
            style.font.name = "宋体"
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            style.font.size = Pt(11)
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.2)
        section.left_margin = Cm(2.7)
        section.right_margin = Cm(2.7)


def trim_after_marker(doc: Document, marker: str) -> None:
    marker_el = None
    for paragraph in doc.paragraphs:
        if marker in paragraph.text:
            marker_el = paragraph._element
            set_paragraph(paragraph, marker, size=16, bold=True)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            break
    if marker_el is None:
        return
    body = doc.element.body
    found = False
    for child in list(body):
        if child is marker_el:
            found = True
            continue
        if found and child.tag != qn("w:sectPr"):
            body.remove(child)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    style_name = f"Heading {level}"
    if style_name in doc.styles:
        paragraph = doc.add_paragraph(text, style=style_name)
    elif level == 1 and "Heading" in doc.styles:
        paragraph = doc.add_paragraph(text, style="Heading")
    else:
        paragraph = doc.add_paragraph(text)
    for run in paragraph.runs:
        set_run_font(run, size=16 if level == 1 else 13, bold=True, font_name="黑体")
    if level == 1:
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(8)
    else:
        paragraph.paragraph_format.space_before = Pt(8)
        paragraph.paragraph_format.space_after = Pt(4)


def add_para(doc: Document, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Pt(22)
    paragraph.paragraph_format.line_spacing = 1.35
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(text)
    set_run_font(run, size=11)


def add_plain_para(doc: Document, text: str, bold: bool = False) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.25
    run = paragraph.add_run(text)
    set_run_font(run, size=11, bold=bold)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None):
    table = doc.add_table(rows=1, cols=len(headers))
    for style_name in ("Table Grid", "表格网格", "Table"):
        try:
            table.style = style_name
            break
        except KeyError:
            continue
    for idx, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[idx], header, size=10)
        for p in table.rows[0].cells[idx].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.bold = True
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            set_cell_text(cells[idx], value, size=9)
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Cm(width)
    doc.add_paragraph()
    return table


def add_picture(doc: Document, image_path: Path, caption: str, width: float = 5.9) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(image_path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(caption)
    set_run_font(run, size=10, bold=True)


def add_toc(doc: Document, entries: Iterable[tuple[str, int]]) -> None:
    for title, level in entries:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.7 * (level - 1))
        run = paragraph.add_run(title)
        set_run_font(run, size=11, bold=(level == 1))


def fill_task_table(table, student_name: str, report_type: str) -> None:
    rows = table.rows
    set_cell_text(rows[0].cells[1], student_name)
    set_cell_text(rows[0].cells[3], CLASS_NAME)
    set_cell_text(rows[1].cells[1], COURSE_NAME)
    set_cell_text(rows[2].cells[1], SYSTEM_NAME)
    set_cell_text(rows[2].cells[3], "2")
    if report_type == "group":
        main_task = (
            "围绕高校奖助学金申请条件评估场景，完成用户认证、历史会话、RAG 智能问答、"
            "政策文件管理、知识库构建、前端交互和测试验收等工作，形成能够运行的前后端分离系统。"
        )
        requirement = (
            "系统应支持普通用户登录后输入绩点、专业排名、家庭经济情况、获奖经历等条件，"
            "依据本地政策知识库输出资格匹配度、已满足条件、缺失条件和申请建议；管理员应能维护政策文件并重建向量知识库。"
        )
        archive = (
            "提交小组报告、三份个人报告、验收记录表、项目介绍文档以及完整项目代码。"
        )
    else:
        main_task = (
            "结合个人分工完成指定模块的需求分析、功能设计、编码实现、联调测试、问题修复和文档整理，"
            "记录开发过程并总结课程实习收获。"
        )
        requirement = (
            "个人报告应说明本人承担的模块、代码实现过程、测试过程、问题解决方法和个人开发日志，"
            "内容需与系统实际功能和代码文件一致。"
        )
        archive = "提交个人报告一份，包含个人开发日志、负责模块说明、测试记录和个人总结。"
    set_cell_text(rows[3].cells[1], main_task)
    set_cell_text(rows[4].cells[1], requirement)
    refs = (
        "参考资料：\n"
        "1. 太原理工大学软件工程专业方向综合实习课程指导书。\n"
        "2. FastAPI、SQLAlchemy、Vue3、Vite、Element Plus 官方文档。\n"
        "3. LangChain、ChromaDB、Ollama 相关技术文档。\n"
        "4. 项目 README.md、requirements.txt、frontend/package.json 及源代码。"
    )
    set_cell_text(rows[5].cells[1], refs)
    set_cell_text(rows[6].cells[1], archive)


def fill_group_cover(doc: Document) -> None:
    set_paragraph(doc.paragraphs[12], f"设计名称：   {SYSTEM_NAME}")
    set_paragraph(doc.paragraphs[13], f"专业班级：{CLASS_NAME}   学号： {LEADER['id']}")
    set_paragraph(doc.paragraphs[14], f"组长姓名：          {LEADER['name']}")
    set_paragraph(doc.paragraphs[15], "组员姓名：   " + "、".join(member["name"] for member in MEMBERS))
    set_paragraph(doc.paragraphs[16], "")
    set_paragraph(doc.paragraphs[17], f"指导教师：          {TEACHER_NAME}")
    set_paragraph(doc.paragraphs[20], TODAY_TEXT)
    if doc.tables:
        fill_task_table(doc.tables[0], LEADER["name"], "group")


def fill_personal_cover(doc: Document, member: dict[str, str]) -> None:
    set_paragraph(doc.paragraphs[12], f"设计名称：   {SYSTEM_NAME}")
    set_paragraph(doc.paragraphs[13], f"专业班级：{CLASS_NAME}   学号： {member['id']}")
    set_paragraph(doc.paragraphs[14], f"学生姓名：          {member['name']}")
    set_paragraph(doc.paragraphs[15], f"组长姓名：          {LEADER['name']}")
    set_paragraph(doc.paragraphs[16], f"指导教师：          {TEACHER_NAME}")
    set_paragraph(doc.paragraphs[20], TODAY_TEXT)
    if doc.tables:
        fill_task_table(doc.tables[0], member["name"], "personal")


def add_group_body(doc: Document, diagrams: dict[str, Path]) -> None:
    add_toc(
        doc,
        [
            ("第一章  概述", 1),
            ("1.1 所选题目", 2),
            ("1.2 项目背景与意义", 2),
            ("1.3 项目概况", 2),
            ("1.4 可行性分析", 2),
            ("1.5 小组分工", 2),
            ("第二章 需求说明书", 1),
            ("第三章 概要设计说明书", 1),
            ("第四章 详细设计说明书", 1),
            ("第五章 系统测试报告", 1),
            ("第六章 项目总结与其他说明", 1),
        ],
    )
    doc.add_page_break()

    add_heading(doc, "第一章  概述", 1)
    add_heading(doc, "1.1 所选题目", 2)
    add_para(doc, f"本课程实习小组所选题目为“{SYSTEM_NAME}”。系统面向高校奖助学金申请咨询场景，将学校奖助学金政策、申请条件、材料要求和评定流程组织为可检索的知识库，学生在登录后输入自己的专业、年级、绩点、专业排名、综合测评、家庭经济情况、贫困认定、获奖经历和违纪记录等信息，系统通过检索增强生成方式给出资格匹配度、可申报项目、已满足条件、缺失条件以及后续申请建议。")
    add_para(doc, "系统不是简单的政策全文搜索工具，而是围绕“申请条件评估”这一具体业务目标设计的智能问答系统。后端使用 FastAPI 提供认证、会话、问答和管理员接口，使用 SQLAlchemy 管理 SQLite 数据库，使用 LangChain、ChromaDB 与 Ollama 组合实现本地政策知识库检索和大语言模型生成；前端使用 Vue3、Vite、Element Plus、Pinia 和 Vue Router 实现登录注册、类聊天交互、历史会话、管理员文件管理和流式回答展示。")

    add_heading(doc, "1.2 项目背景与意义", 2)
    for text in [
        "高校奖助学金政策通常涉及国家奖学金、国家励志奖学金、国家助学金、校内奖学金、临时困难补助等多类项目。不同项目在成绩排名、综合测评、家庭经济困难认定、获奖经历、违纪情况、申请材料和评审流程方面存在明显差异。学生在准备申请时，经常需要在多份 PDF、Word 或网页通知之间查找条款，理解成本较高；辅导员和资助工作人员也需要重复解答相似问题，人工咨询效率受到影响。",
        "本系统以 RAG 技术为核心，把政策原文以文档形式导入本地知识库，通过切片、向量化和相似度检索找到与学生问题最相关的政策条款，再由对话模型结合提示词规则生成结构化建议。系统提示词明确要求回答必须以“资格匹配度：XX%”开头，并在信息不足时指出缺失项和不确定性，因此能把政策检索、条件核对和申请指导整合为连续对话过程。",
        "从教学实践角度看，本项目覆盖了前后端分离开发、REST API 设计、SSE 流式响应、JWT 鉴权、数据库建模、文件上传、向量数据库、LangChain 链路组织、前端状态管理和系统测试等软件工程关键内容。项目规模适合作为综合实习题目，既有传统信息系统的业务管理功能，又体现了人工智能应用系统在真实场景中的工程落地方式。",
    ]:
        add_para(doc, text)

    add_heading(doc, "1.3 项目概况", 2)
    add_para(doc, "项目目录由 backend、frontend、data、chroma_db、logs、requirements.txt、README.md、app.db 等部分组成。backend/app 目录按照 FastAPI 项目结构划分为 api、core、db、models、schemas、services 等包；frontend/src 目录按照 Vue 应用结构划分为 api、components、router、stores、styles、views 等目录。data/policies 用于保存管理员上传的政策文件，chroma_db 用于保存 Chroma 向量数据库持久化数据，app.db 是 SQLite 业务数据库。")
    add_para(doc, "系统运行时，普通用户首先通过 AuthView 完成注册或登录，前端将后端返回的 JWT、用户名和管理员标记保存到 localStorage。进入 ChatView 后，Pinia 的 chat store 会加载当前用户的历史会话列表，用户输入申请条件后，前端通过 fetch 发起 POST /api/chat/stream 请求，并在请求头中携带 Bearer Token。后端校验用户身份，创建或读取会话，调用 RAGChain 检索知识库并流式生成回答，前端逐块解析 SSE 数据并实时更新消息气泡。")
    add_picture(doc, diagrams["architecture"], "图1-1 系统总体架构图")

    add_heading(doc, "1.4 可行性分析", 2)
    for text in [
        "技术可行性方面，项目采用的 FastAPI、SQLAlchemy、Vue3、Vite、Element Plus、Pinia、LangChain、ChromaDB 和 Ollama 都是成熟工具。FastAPI 能够以较少代码实现类型校验、依赖注入和异步接口；SQLAlchemy 提供统一的数据模型和会话管理；Vue3 与 Pinia 能够清晰管理页面状态；LangChain 的 RunnableWithMessageHistory、ChatPromptTemplate 和向量检索器能够降低 RAG 链路开发成本。项目代码已形成完整目录结构，说明技术路线可以支撑课程实习要求。",
        "操作可行性方面，系统入口分为普通用户和管理员两类。普通用户只需要完成登录、输入个人情况、阅读系统建议；管理员只需要上传政策文件、删除无效文件和点击重建知识库。前端页面采用左侧历史会话、右侧对话区和底部输入框布局，交互接近常见智能助手产品，学习成本较低。",
        "经济可行性方面，项目使用本地 SQLite、ChromaDB 和 Ollama 模型服务，不依赖收费云数据库或在线大模型接口，适合课程设计和校内部署验证。硬件成本主要来自运行本地模型所需的 CPU、内存和可选 GPU；在实验环境中，也可以把 Ollama 部署到局域网模型服务器，由多名开发者共享使用。",
        "法律与安全可行性方面，系统只处理学生主动输入的咨询信息，业务数据库保存用户名、密码哈希、会话标题、消息内容和政策文件记录。密码采用 bcrypt 哈希，接口通过 JWT 鉴权保护，管理员接口通过 require_admin 做权限限制。系统后续部署时需要补充隐私提示、日志脱敏和生产级密钥管理，本课程实习版本已具备基本安全控制。",
    ]:
        add_para(doc, text)

    add_heading(doc, "1.5 小组分工", 2)
    add_para(doc, "本小组由三名成员组成，按照前端、后端、数据库与测试文档等方向分工，同时在需求分析、接口联调和文档整理阶段共同参与。分工既考虑模块边界，也考虑接口之间的依赖关系，保证每名成员都能参与完整的软件开发流程。")
    add_table(
        doc,
        ["姓名", "角色", "主要任务", "对应代码与成果"],
        [
            [LEADER["name"], "组长、后端与 RAG 集成", "负责总体架构、FastAPI 主程序、RAG 链路、知识库重建、管理员接口协调和小组文档整合。", "backend/app/main.py、backend/app/api/routes/chat.py、backend/app/services/rag_chain.py、backend/ingest.py、小组报告"],
            ["李四", "前端开发", "负责登录注册页面、聊天页面、会话侧栏、消息气泡、输入组件、管理员文件页面、Pinia 状态管理和流式响应解析。", "frontend/src/views、frontend/src/components、frontend/src/stores、frontend/src/api"],
            ["王五", "数据库、认证、安全与测试", "负责数据模型、JWT 鉴权、SQLite 表结构、会话消息持久化、政策文件记录、测试用例设计和验收材料整理。", "backend/app/models、backend/app/core/security.py、backend/app/core/deps.py、app.db、测试报告、验收记录表"],
        ],
        widths=[2.2, 3, 6.5, 6.5],
    )

    add_heading(doc, "第二章 需求说明书", 1)
    add_heading(doc, "2.1 引言", 2)
    add_para(doc, "本章说明系统的功能需求、性能需求、数据管理需求、输入输出要求、运行环境和约束条件，面向开发人员、测试人员、指导教师和后续维护人员。需求描述以现有系统代码和运行目标为基础，重点说明学生用户、管理员和系统服务之间的交互边界。")
    add_heading(doc, "2.1.1 编写目的", 2)
    add_para(doc, "需求说明书用于明确本系统在课程实习阶段需要完成的功能范围和质量要求。通过该说明书，可以判断系统是否真正实现了高校奖助学金申请条件评估、政策知识库维护、会话管理和前端交互等核心目标，也为后续概要设计、详细设计和测试用例提供依据。")
    add_heading(doc, "2.1.2 背景", 2)
    add_para(doc, "系统名称为“基于 LangChain 的高校奖助学金申请条件评估与指导系统”。任务提出背景是高校奖助学金政策条款分散、人工咨询重复、学生准备材料时容易遗漏条件。系统开发者为软件工程专业方向综合实习小组，最终用户包括需要咨询奖助学金资格的学生，以及负责维护政策文件的管理员。系统作为独立 Web 应用运行，通过浏览器访问前端，通过 FastAPI 后端完成数据处理和模型调用。")
    add_heading(doc, "2.1.3 定义", 2)
    add_table(
        doc,
        ["术语", "含义"],
        [
            ["RAG", "Retrieval-Augmented Generation，检索增强生成。系统先检索政策条款，再由大语言模型生成回答。"],
            ["SSE", "Server-Sent Events，服务器发送事件。系统使用 POST 请求返回 text/event-stream，实现回答逐字流式展示。"],
            ["JWT", "JSON Web Token。登录成功后后端签发令牌，前端在接口请求中通过 Bearer Token 携带。"],
            ["ChromaDB", "本项目使用的本地向量数据库，用于保存政策文档切片和向量表示。"],
            ["Ollama", "本项目调用的本地模型服务，提供 qwen2.5:7b 对话模型和 bge-m3 向量模型。"],
            ["MMR", "Maximal Marginal Relevance，最大边际相关检索。系统检索时设置 k=5、fetch_k=12，兼顾相关性与多样性。"],
        ],
        widths=[3, 13],
    )
    add_heading(doc, "2.1.4 参考资料", 2)
    for text in [
        "课程实习指导书、软件工程文档编制规范、项目 README.md、requirements.txt、frontend/package.json、FastAPI 官方文档、SQLAlchemy 官方文档、Vue3 官方文档、Vite 官方文档、Element Plus 官方文档、LangChain 官方文档、ChromaDB 文档和 Ollama 模型服务文档。",
        "在业务资料方面，系统支持将学校奖助学金政策 PDF、DOCX 或 TXT 文件导入 data/policies 目录。管理员上传后，政策文件记录进入 policy_files 表，重建知识库时由 ingest.py 统一加载、切片和向量化。课程实习阶段的政策样例存放于 data/policies 目录，真实部署时应替换为学校正式发布的资助政策文件。",
    ]:
        add_para(doc, text)

    add_heading(doc, "2.2 任务概述", 2)
    add_heading(doc, "2.2.1 目标", 2)
    add_para(doc, "系统目标是为学生提供奖助学金申请资格评估和材料准备指导。用户输入个人条件后，系统应结合政策知识库判断可能符合的奖助学金项目，列出已满足条件和尚未满足或缺失的信息，并给出申请步骤和材料建议。系统回答必须尽量依据检索到的政策条款，不能凭空编造政策；当用户提供信息不足时，应优先反问补充关键项。")
    add_heading(doc, "2.2.2 用户特点", 2)
    add_para(doc, "普通用户主要是高校学生，熟悉浏览器和聊天式交互，但不一定熟悉政策条文结构。管理员主要是资助相关工作人员或系统维护人员，需要具备上传、删除政策文件和重建知识库的基本操作能力。开发维护人员需要了解 Python、JavaScript、FastAPI、Vue 和 LangChain 基础。系统预期使用频率在奖助学金评定季较高，在平时可作为政策咨询工具使用。")
    add_heading(doc, "2.2.3 假定和约束", 2)
    add_para(doc, "系统假定管理员上传的政策文件内容真实有效，且文件格式为 PDF、DOCX 或 UTF-8 编码 TXT。系统依赖 Ollama 模型服务，要求 qwen2.5:7b 和 bge-m3 可访问；若模型服务不可用，RAG 问答和知识库重建会失败。系统课程版本使用 SQLite，适合本地和小规模部署；若并发量较大，应迁移到 MySQL 或 PostgreSQL，并为向量库和模型服务配置更稳定的运行环境。")
    add_picture(doc, diagrams["use_case"], "图2-1 系统用例图")

    add_heading(doc, "2.3 需求规定", 2)
    add_heading(doc, "2.3.1 对功能的规定", 2)
    add_para(doc, "系统功能按照认证、智能问答、会话管理、政策文件管理、知识库构建和前端展示六个模块划分。各模块既相互独立又通过接口协同：认证模块提供用户身份，问答模块依赖会话和知识库，会话管理模块保存对话历史，管理员模块维护知识库来源，前端展示模块负责把后端数据转化为可操作界面。")
    add_table(
        doc,
        ["模块", "输入", "处理", "输出"],
        [
            ["用户认证", "用户名、密码", "注册时检查用户名唯一性并写入密码哈希；登录时验证密码并签发 JWT。", "access_token、token_type、username、is_admin"],
            ["智能问答", "session_id、用户消息、Bearer Token", "校验用户、创建或读取会话、MMR 检索政策条款、组织提示词、调用 Ollama 流式生成。", "SSE session/token/error/end 事件、数据库消息记录"],
            ["会话管理", "当前用户、会话编号", "查询当前用户会话列表、读取消息、删除会话及级联消息。", "会话列表、消息列表、删除结果"],
            ["政策文件管理", "管理员身份、上传文件或文件编号", "校验扩展名、保存文件、记录元数据、删除文件、触发知识库重建。", "文件清单、上传记录、重建文档数和切片数"],
            ["知识库构建", "data/policies 中的 PDF、DOCX、TXT", "DirectoryLoader 加载，RecursiveCharacterTextSplitter 以 500/50 切分，bge-m3 生成向量，Chroma 持久化。", "chroma_db/policy_documents 向量集合"],
            ["前端展示", "后端接口数据和 SSE 流", "Pinia 管理状态，Vue 组件渲染，MarkdownIt 和 DOMPurify 处理回答内容。", "登录页、聊天页、历史会话、匹配度进度条、文件管理页"],
        ],
        widths=[2.8, 3.7, 6.8, 4.2],
    )
    add_picture(doc, diagrams["business_flow"], "图2-2 业务流程图")

    add_heading(doc, "2.3.2 对性能的规定", 2)
    for text in [
        "响应时间方面，登录、注册、会话列表、消息查询、文件列表等普通数据库接口应在本地环境中保持秒级响应。RAG 问答涉及向量检索和大模型生成，首个 token 的等待时间受模型服务性能影响，因此系统采用 SSE 流式输出，让用户尽早看到生成过程，降低等待感。",
        "检索准确性方面，系统在 rag_chain.py 中使用 Chroma retriever 的 MMR 模式，search_kwargs 设置为 k=5、fetch_k=12，优先返回与用户条件相关、同时避免内容过度重复的政策片段。提示词要求模型严格依据条款，信息不足时明确说明缺失项，从流程上减少错误结论。",
        "安全性方面，密码不得明文保存，使用 passlib bcrypt 哈希；接口依赖 OAuth2PasswordBearer 提取 token；管理员功能通过 require_admin 过滤普通用户。前端在 http.js 中拦截 401 响应并清理本地令牌，避免过期登录状态继续使用。",
    ]:
        add_para(doc, text)
    add_heading(doc, "2.3.3 输入输出要求", 2)
    add_para(doc, "系统主要输入包括用户名、密码、学生个人条件描述、会话编号、政策文件和管理员操作指令。用户消息长度在 ChatStreamRequest 中通过 Pydantic Field 限定为 1 到 4000 字符；注册用户名长度为 3 到 50，密码长度为 6 到 128。政策文件扩展名限定为 .pdf、.docx、.txt，空文件会被拒绝。")
    add_para(doc, "系统主要输出包括 JSON 响应、SSE 流式事件、前端消息气泡、会话列表、政策文件列表和知识库重建结果。问答输出由提示词约束为“资格匹配度：XX%”开头，随后分点说明可能符合的奖助学金、已满足条件、缺失条件、建议补充材料和申请步骤。前端 ChatBubble.vue 会用正则解析匹配度百分比并显示进度条。")
    add_heading(doc, "2.3.4 数据管理能力要求", 2)
    add_para(doc, "业务数据库 app.db 保存 users、chat_sessions、messages、policy_files 四张表。users 保存账号、密码哈希、管理员标记和创建时间；chat_sessions 保存用户会话标题与时间；messages 保存会话内用户和助手消息；policy_files 保存政策文件元数据。向量库 chroma_db 保存政策文档切片及向量，用于问答检索。文件原文保存在 data/policies，数据库只记录文件名、原始文件名、类型、大小、上传人和创建时间。")
    add_heading(doc, "2.3.5 故障处理要求", 2)
    add_para(doc, "认证失败时返回 401 或 400，并在前端显示错误提示；访问不存在或不属于当前用户的会话时返回 404；普通用户访问管理员接口时返回 403；上传非支持格式或空文件时返回 400；重建知识库时若目录不存在、无文件、解析依赖缺失或模型服务不可用，应返回明确错误信息。chat.py 的 event_generator 捕获异常后会回滚数据库事务，并通过 SSE error 事件把错误内容传给前端。")
    add_heading(doc, "2.3.6 其他专门要求", 2)
    add_para(doc, "系统应具有较好的可维护性。后端按 api、core、db、models、schemas、services 分层，接口、配置、安全、模型和服务逻辑分离；前端按 api、components、views、stores、router 分层，便于单独维护。系统应支持后续替换模型、调整检索参数、扩展政策文件格式和迁移数据库。")
    add_heading(doc, "2.4 运行环境规定", 2)
    add_para(doc, "硬件环境建议为 Windows 或 Linux 开发机，具备 16GB 以上内存；若本机运行 qwen2.5:7b，建议配置较好的 CPU 或 GPU。软件环境包括 Python 3.11 及以上、Node.js 18 及以上、Ollama、浏览器、FastAPI、LangChain、ChromaDB、SQLAlchemy、Vue3、Vite 和 Element Plus。后端默认监听 8000 端口，前端 Vite 默认监听 5173 端口。")
    add_para(doc, "后端启动步骤为：复制 .env.example 为 .env，确认 OLLAMA_BASE_URL、模型名、数据库路径、Chroma 路径、政策目录和管理员账号；执行 pip install -r requirements.txt；进入 backend 后执行 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000。前端启动步骤为：进入 frontend，执行 npm install，然后执行 npm run dev，浏览器访问 http://localhost:5173。知识库可通过管理员页面重建，也可在 backend 目录执行 python ingest.py。")

    add_heading(doc, "第三章 概要设计说明书", 1)
    add_heading(doc, "3.1 引言", 2)
    add_para(doc, "概要设计在需求说明的基础上，描述系统整体架构、模块划分、接口关系、运行流程、数据结构和出错处理策略。本系统采用浏览器前端、FastAPI 后端、SQLite 业务数据库、Chroma 向量数据库和 Ollama 模型服务组成的分层架构。")
    add_picture(doc, diagrams["function_modules"], "图3-1 系统功能模块图")
    add_heading(doc, "3.2 总体设计", 2)
    add_para(doc, "总体设计采用前后端分离模式。前端负责页面路由、表单输入、状态保存、SSE 解析和渲染；后端负责业务接口、身份鉴权、数据库访问、政策文件管理、知识库构建和 RAG 生成。业务数据库和向量数据库分别承担结构化数据和语义检索数据的持久化任务，Ollama 提供 embedding 和对话生成能力。")
    add_para(doc, "后端 main.py 通过 lifespan 在应用启动时执行 init_db，自动创建缺失数据表并确保管理员账号存在。api/router.py 统一挂载 auth、chat、sessions 和 admin 路由，所有业务接口统一以 /api 为前缀。core/config.py 使用 pydantic-settings 从 .env 读取配置，并提供路径解析属性，保证无论从项目根目录还是 backend 目录启动都能找到 app.db、chroma_db 和 data/policies。")
    add_heading(doc, "3.2.1 需求规定", 2)
    add_para(doc, "系统必须完成用户注册登录、JWT 鉴权、管理员权限控制、历史会话、流式智能问答、政策文件上传删除、知识库重建和前端可视化展示。需求与程序关系通过路由层、服务层和前端组件共同实现，接口返回数据统一由 Pydantic schema 约束。")
    add_heading(doc, "3.2.2 运行环境", 2)
    add_para(doc, "后端运行于 Python 环境，依赖 FastAPI、uvicorn、python-jose、passlib、SQLAlchemy、LangChain、ChromaDB、Ollama 相关包；前端运行于 Node.js/Vite 环境，依赖 Vue3、Element Plus、Pinia、Vue Router、Axios、MarkdownIt 和 DOMPurify。模型服务通过 HTTP 地址 OLLAMA_BASE_URL 访问，默认配置为 http://localhost:11434。")
    add_heading(doc, "3.2.3 基本设计概念和处理流程", 2)
    add_para(doc, "智能问答处理流程是系统核心：用户输入问题后，前端立即插入用户消息和空助手消息，设置 streaming 状态；后端创建或读取会话后，RAGChain 先从 ChromaDB 检索政策条款，再读取数据库最近消息形成历史摘要，随后把系统提示词、历史、检索上下文和用户输入传给 ChatOllama；生成过程以 token 流返回，前端逐块拼接内容并在结束事件后刷新会话列表和持久化消息。")
    add_picture(doc, diagrams["rag_sequence"], "图3-2 RAG 问答核心流程时序图")
    add_heading(doc, "3.2.4 结构", 2)
    add_table(
        doc,
        ["层次", "模块", "主要文件", "职责"],
        [
            ["前端页面层", "认证、聊天、管理员文件", "AuthView.vue、ChatView.vue、AdminFilesView.vue", "负责页面布局、表单交互、按钮事件和用户提示。"],
            ["前端组件层", "会话侧栏、输入框、消息气泡", "SessionSidebar.vue、ChatComposer.vue、ChatBubble.vue", "复用 UI 组件，渲染会话、输入消息、显示 Markdown 和匹配度进度条。"],
            ["前端状态与接口层", "Pinia、Axios、Fetch SSE", "stores/auth.js、stores/chat.js、api/*.js", "保存 token、用户信息、会话状态，封装 HTTP 与 SSE 调用。"],
            ["后端接口层", "认证、问答、会话、管理", "routes/auth.py、chat.py、sessions.py、admin.py", "处理 HTTP 请求、鉴权、参数校验和响应。"],
            ["后端服务层", "RAG、向量库、聊天历史", "services/rag_chain.py、vector_store.py、chat_history.py", "组织模型调用、向量检索、历史消息读写。"],
            ["数据层", "模型和数据库", "models/*.py、db/session.py、app.db、chroma_db", "保存业务结构化数据和政策向量数据。"],
        ],
        widths=[2.6, 3, 4.2, 6.8],
    )
    add_heading(doc, "3.2.5 功能需求与程序的关系", 2)
    add_para(doc, "登录注册需求由 auth.py、security.py、User 模型和 auth store 实现；聊天需求由 chat.py、rag_chain.py、chat_history.py、chat store 和 ChatView 实现；历史会话需求由 sessions.py、ChatSession/Message 模型和 SessionSidebar 实现；管理员文件管理需求由 admin.py、PolicyFile 模型、ingest.py 和 AdminFilesView 实现。")
    add_heading(doc, "3.2.6 人工处理过程", 2)
    add_para(doc, "人工处理主要发生在政策文件准备和知识库维护环节。管理员需要确认上传文件内容属于有效政策文件，避免把无关资料加入知识库；政策调整后需要重新上传或删除文件，并点击重建知识库。学生侧也需要人工确认系统建议，最终申请仍应以学校正式通知和人工审核为准。")
    add_heading(doc, "3.2.7 尚未解决的问题", 2)
    add_para(doc, "课程版本尚未接入真实学校资助系统和学生成绩系统，学生条件依赖手动输入，无法自动校验成绩排名或家庭经济困难认定。系统当前未实现政策条款引用定位到页码和高亮展示，后续可在检索上下文中保留 page、source 等元数据并在前端展示。")
    add_heading(doc, "3.3 接口设计", 2)
    add_table(
        doc,
        ["接口", "方法", "请求数据", "主要处理", "响应"],
        [
            ["/api/auth/register", "POST", "username、password", "检查用户名唯一，bcrypt 加密，创建普通用户，签发 JWT。", "TokenResponse"],
            ["/api/auth/login", "POST", "username、password", "查询用户，校验密码，签发 JWT。", "TokenResponse"],
            ["/api/chat/stream", "POST", "session_id、message、Bearer Token", "校验用户、创建或读取会话、调用 RAGChain，返回 SSE。", "session/token/error/end"],
            ["/api/sessions", "GET", "Bearer Token", "按更新时间倒序查询当前用户会话。", "SessionRead 列表"],
            ["/api/sessions/{id}/messages", "GET", "session_id、Bearer Token", "校验会话归属并查询消息。", "MessageRead 列表"],
            ["/api/sessions/{id}", "DELETE", "session_id、Bearer Token", "校验归属后删除会话并级联消息。", "204"],
            ["/api/admin/files", "GET", "管理员 Token", "查询政策文件元数据。", "PolicyFileRead 列表"],
            ["/api/admin/files", "POST", "multipart file", "校验后缀和内容，保存到 data/policies，写入 policy_files。", "PolicyFileRead"],
            ["/api/admin/files/{id}", "DELETE", "file_id", "删除磁盘文件和数据库记录。", "204"],
            ["/api/admin/rebuild", "POST", "管理员 Token", "调用 rebuild_knowledge_base 解析、切片、向量化。", "文档数、切片数"],
        ],
        widths=[3.5, 1.4, 3.8, 5.8, 2.7],
    )
    add_heading(doc, "3.4 运行设计", 2)
    add_para(doc, "系统运行模块组合包括普通用户问答组合、管理员维护组合和命令行知识库导入组合。普通用户问答组合需要前端 ChatView、chat store、chat.py、RAGChain、SQLite、Chroma 和 Ollama 同时工作；管理员维护组合需要 AdminFilesView、admin.py、PolicyFile、data/policies 和 ingest.py；命令行导入组合只需要 backend/ingest.py、配置、文档加载器、向量模型和 Chroma。")
    add_picture(doc, diagrams["deployment"], "图3-3 系统部署图")
    add_heading(doc, "3.5 系统数据结构设计", 2)
    add_para(doc, "系统结构化数据模型由 SQLAlchemy ORM 定义。User 与 ChatSession 是一对多关系，ChatSession 与 Message 是一对多关系，并通过 cascade='all, delete-orphan' 实现删除用户或会话时清理关联数据。PolicyFile 独立保存政策文件元数据，uploaded_by 使用用户名记录上传人，便于管理员审计。")
    add_picture(doc, diagrams["er"], "图3-4 数据库 ER 图")
    add_table(
        doc,
        ["表名", "字段", "说明"],
        [
            ["users", "id、username、password_hash、is_admin、created_at", "账号表。username 唯一，password_hash 保存 bcrypt 哈希，is_admin 用于区分管理员。"],
            ["chat_sessions", "id、user_id、session_title、created_at、updated_at", "会话表。user_id 关联 users，session_title 由首条消息自动截断生成。"],
            ["messages", "id、session_id、role、content、timestamp", "消息表。role 保存 user 或 assistant，content 保存完整文本。"],
            ["policy_files", "id、filename、original_filename、file_type、size_bytes、uploaded_by、created_at", "政策文件表。filename 为安全存储名，original_filename 为用户上传的原文件名。"],
        ],
        widths=[3.2, 6, 7.5],
    )
    add_heading(doc, "3.6 系统出错处理设计", 2)
    add_para(doc, "系统出错处理分为接口异常、业务异常和模型链路异常。接口异常通过 FastAPI HTTPException 返回状态码和 detail；业务异常包括用户名重复、密码错误、会话不存在、无管理员权限、文件为空和文件格式不支持；模型链路异常包括政策目录不存在、无政策文件、文档解析依赖缺失、向量模型不可用和对话模型不可用。前端通过 Element Plus 的 ElMessage 显示错误，并在 401 时清理 token 跳转登录页。")

    add_heading(doc, "第四章 详细设计说明书", 1)
    add_heading(doc, "4.1 引言", 2)
    add_para(doc, "详细设计围绕项目主要程序文件展开，说明每个核心模块的职责、输入输出、关键逻辑和接口关系。系统没有把所有逻辑集中在单个文件中，而是按后端分层与前端组件化原则拆分，便于定位问题和扩展功能。")
    add_heading(doc, "4.2 程序系统结构", 2)
    add_para(doc, "backend/app/main.py 是后端入口，创建 FastAPI 应用、配置 CORS、中间件、生命周期函数和健康检查接口。api/router.py 将 auth、chat、sessions、admin 四组路由统一挂载到 /api。core/config.py 负责读取 .env 并解析相对路径，core/security.py 负责密码哈希、JWT 创建与解码，core/deps.py 负责当前用户和管理员依赖注入。models 与 schemas 分别定义数据库模型和接口模型。")
    add_para(doc, "frontend/src/main.js 创建 Vue 应用并安装 Pinia、Router 和 Element Plus。router/index.js 定义 /login、/、/admin/files 三个页面，并通过 beforeEach 根据 localStorage 中的 token 和 is_admin 控制访问。api/http.js 封装 Axios 实例，为普通接口自动携带 Authorization 请求头，并在 401 时跳转登录页；api/chat.js 因为需要 POST SSE，使用 fetch 和 ReadableStream 手动解析 data 事件。")
    add_heading(doc, "4.3 认证模块设计", 2)
    add_para(doc, "认证模块由 backend/app/api/routes/auth.py、core/security.py、core/deps.py、models/user.py、schemas/auth.py、frontend/src/views/AuthView.vue 和 stores/auth.js 共同实现。注册接口接收 UserRegister，使用 SQLAlchemy 查询同名用户，若不存在则调用 get_password_hash 生成 bcrypt 哈希并写入 users 表。登录接口查询用户后调用 verify_password 校验密码，成功后 create_access_token 把用户 id 写入 JWT 的 sub 字段。")
    add_para(doc, "前端 AuthView.vue 使用 Element Plus Tabs 区分登录和注册表单。登录或注册成功后调用 authStore.setAuth，将 token、username 和 is_admin 同步写入 Pinia 状态与 localStorage。路由守卫依据 localStorage 决定是否允许进入聊天页或管理员页。该设计保证刷新浏览器后仍能保持登录状态，同时在后端返回 401 时可以统一清理状态。")
    add_heading(doc, "4.4 智能问答与 RAG 模块设计", 2)
    add_para(doc, "智能问答入口是 backend/app/api/routes/chat.py 的 /stream 接口。接口先通过 get_current_user 校验 JWT，然后根据 session_id 判断是继续已有会话还是创建新会话。新会话标题由 _build_session_title 根据首条用户消息截断生成，长度限制为 24 字符并追加省略号。接口内部定义 event_generator，先发送 session 事件，再调用 rag_chain.astream_answer 逐块获取模型输出，并把每个字符封装为 token 事件。")
    add_para(doc, "rag_chain.py 中的 SYSTEM_PROMPT 是系统回答质量的关键。提示词把模型角色限定为“高校资助中心专家顾问”，要求严格依据政策条款，信息缺失时反问补充，回答必须以资格匹配度开头，并分点列出可能符合的奖助学金、已满足条件、缺失条件、建议材料和申请步骤。该提示词使回答更适合奖助学金评估场景，而不是普通开放式问答。")
    add_para(doc, "RAGChain 初始化时通过 get_vector_store 获取 Chroma 向量库，并调用 as_retriever(search_type='mmr', search_kwargs={'k':5,'fetch_k':12}) 构建检索器；通过 ChatOllama 创建 qwen2.5:7b 对话模型，temperature 设置为 0.2 以降低随机性。ChatPromptTemplate 包含系统角色、最近 5 轮摘要、检索到的政策条款、历史消息占位和当前用户输入。RunnableWithMessageHistory 通过 DatabaseChatMessageHistory 把消息读写与链路执行绑定起来。")
    add_para(doc, "astream_answer 的核心逻辑是先 await retriever.ainvoke(user_input) 获取相关文档，再把每个文档格式化为“[条款idx] 来源：source + page_content”。如果检索不到内容，则上下文设为“当前知识库证据不足”。随后读取当前会话的最近消息生成 history_summary，并调用 self.chain.astream 持续输出 chunk。由于前端需要更平滑的逐字效果，chat.py 又把 chunk 拆成字符并设置短暂 sleep。")
    add_heading(doc, "4.5 知识库构建与文件管理模块设计", 2)
    add_para(doc, "管理员接口由 admin.py 实现。上传文件时，系统先根据文件名后缀判断是否属于 ALLOWED_EXTENSIONS 中的 .pdf、.docx、.txt，再读取文件内容并拒绝空文件。安全存储名由原始文件 stem、uuid4 的前 10 位和后缀组成，避免中文空格、重名和路径穿越问题。文件保存到 settings.resolved_policy_dir 后，PolicyFile 记录写入数据库。")
    add_para(doc, "重建知识库接口会检查政策目录和 policy_files 记录，随后调用 ingest.py 中的 rebuild_knowledge_base。ingest.py 使用 DirectoryLoader 分别加载 PDF、DOCX 和 TXT，其中 PDF 使用 PyPDFLoader，DOCX 使用 UnstructuredFileLoader，TXT 使用 TextLoader 并指定 UTF-8。加载后的文档用 RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50) 切分，之后通过 get_vector_store 获取 Chroma 集合，先删除或重置旧集合，再 add_documents 写入新切片。")
    add_heading(doc, "4.6 会话历史模块设计", 2)
    add_para(doc, "sessions.py 提供会话列表、消息列表和删除接口。所有接口都依赖 get_current_user，确保用户只能访问自己的会话。list_sessions 按 updated_at desc 和 id desc 排序，便于前端显示最近会话。list_session_messages 校验会话归属后按 timestamp 和 id 升序返回消息。delete_session 删除 ChatSession，SQLAlchemy 关系配置会级联删除 Message。")
    add_para(doc, "chat_history.py 实现 DatabaseChatMessageHistory，继承 BaseChatMessageHistory。messages 属性每次打开新的 SessionLocal 查询当前会话最近 window_size 条消息，并根据 role 转为 HumanMessage 或 AIMessage；add_messages 把 LangChain 消息类型 human/ai 映射为数据库中的 user/assistant。该设计让 LangChain 历史机制直接使用业务数据库，避免额外维护内存状态。")
    add_heading(doc, "4.7 前端交互模块设计", 2)
    add_para(doc, "ChatView.vue 是问答主页面，组合 SessionSidebar、ChatBubble 和 ChatComposer。页面加载时调用 chatStore.loadSessions，用户点击建议提示或输入框发送时调用 chatStore.sendMessage。watch 监听消息内容变化，在模型输出过程中自动滚动到底部。退出登录时调用 authStore.logout 并重置 chat store。管理员入口只在 isAdmin 为 true 时显示。")
    add_para(doc, "stores/chat.js 是前端问答状态核心。state 中保存 sessions、activeSessionId、draftMessages、messagesBySession、loadingSessions 和 streaming。sendMessage 会先在当前列表中插入用户消息和空助手消息，再调用 streamChat。收到 session 事件时，如果是新会话，会把 draftMessages 稳定到 messagesBySession[event.session_id]，并把新会话插入 sessions 顶部；收到 token 事件时拼接助手内容；收到 end 事件后刷新会话列表和持久化消息。")
    add_para(doc, "ChatBubble.vue 使用 MarkdownIt 渲染模型回答，用 DOMPurify 消毒 HTML，避免不可信内容直接注入页面。它通过正则 /资格匹配度：\\s*(\\d{1,3})%/ 提取百分比，并使用 el-progress 显示进度条。ChatComposer.vue 处理输入框、Enter 发送和 Shift+Enter 换行，避免用户误操作。AdminFilesView.vue 处理文件上传、删除、重建知识库和文件表格展示。")
    add_heading(doc, "4.8 数据库详细设计", 2)
    add_para(doc, "User 模型包含 username 唯一索引、password_hash、is_admin 和 created_at。ChatSession 模型包含 user_id 外键、session_title、created_at、updated_at，并通过 relationship 与 User 和 Message 建立关系。Message 模型保存 role 和 content，timestamp 使用数据库当前时间。PolicyFile 模型的 filename 唯一并建索引，original_filename 用于界面展示，file_type 用于类型标签，size_bytes 用于文件大小展示。")
    add_heading(doc, "4.9 关键代码说明", 2)
    add_para(doc, "main.py 的 init_db 在应用启动时执行轻量迁移：若 SQLite 老表 users 缺少 is_admin 字段，则通过 ALTER TABLE 补充；随后只创建缺失表，避免覆盖已有数据；最后根据环境变量确保管理员账号存在。这一设计使课程开发过程中数据库结构变化后仍能启动，并降低手工初始化成本。")
    add_para(doc, "admin.py 的 _safe_storage_name 对上传文件名进行规范化，保留 stem 前 80 个字符，空 stem 使用 policy，并追加 uuid4 短随机串。这种方式比直接使用用户上传文件名更安全，能够避免覆盖已有文件和特殊路径问题。delete_policy_file 在删除数据库记录前先删除磁盘文件，保证文件系统和数据库尽量一致。")
    add_para(doc, "frontend/src/api/chat.js 的 consumeSseBuffer 会把 ReadableStream 解码后的文本按空行分割成 SSE 事件，再处理以 data: 开头的行并 JSON.parse。原生 EventSource 不适合带 Bearer Token 的 POST 请求，因此项目使用 fetch 自行消费流。这一实现与后端 StreamingResponse 对应，是前端流式体验的关键代码。")

    add_heading(doc, "第五章 系统测试报告", 1)
    add_heading(doc, "5.1 测试范围", 2)
    add_para(doc, "测试范围覆盖后端接口、前端页面、数据库读写、RAG 链路、文件管理、权限控制、构建过程和异常处理。重点验证普通用户是否能够注册、登录、发起问答、查看历史会话和删除会话；管理员是否能够上传政策文件、查看文件列表、删除文件和重建知识库；系统是否能在模型服务可用时返回流式回答。")
    add_picture(doc, diagrams["test_flow"], "图5-1 系统测试流程图")
    add_heading(doc, "5.2 测试计划", 2)
    add_para(doc, "测试采用分阶段方式：第一阶段进行静态检查和语法检查，确认后端 Python 模块可导入、前端能完成生产构建；第二阶段测试数据库初始化、管理员账号创建和基础接口；第三阶段联调前后端登录、聊天、历史会话和文件管理；第四阶段使用政策文件重建知识库并测试 RAG 回答质量；第五阶段整理测试结果、问题和修复记录。")
    add_heading(doc, "5.3 测试项目说明", 2)
    add_table(
        doc,
        ["编号", "测试项目", "操作步骤", "预期结果", "实际结果"],
        [
            ["TC-01", "用户注册", "在注册页输入新用户名和 6 位以上密码，点击注册。", "返回 token，进入聊天页，localStorage 保存 token 和用户名。", "通过"],
            ["TC-02", "重复注册", "使用已存在用户名再次注册。", "后端返回 400，提示 Username already exists。", "通过"],
            ["TC-03", "用户登录", "输入正确用户名和密码。", "返回 TokenResponse，前端跳转聊天页。", "通过"],
            ["TC-04", "错误登录", "输入错误密码。", "后端返回 401，前端显示登录失败。", "通过"],
            ["TC-05", "新建问答", "在聊天页输入绩点、排名、家庭收入等条件。", "后端创建会话，前端收到 session 事件和 token 流。", "通过"],
            ["TC-06", "历史会话", "刷新页面或重新进入聊天页。", "会话列表按更新时间倒序显示，点击后加载消息。", "通过"],
            ["TC-07", "删除会话", "点击历史会话删除按钮并确认。", "接口返回 204，会话从列表移除。", "通过"],
            ["TC-08", "普通用户访问管理员页", "普通用户直接访问 /admin/files。", "路由守卫返回聊天页，后端接口也会拒绝。", "通过"],
            ["TC-09", "管理员上传文件", "管理员上传 PDF/DOCX/TXT 文件。", "文件保存到 data/policies，policy_files 写入记录。", "通过"],
            ["TC-10", "非支持格式上传", "上传 .exe 或空文件。", "后端返回 400，提示格式或空文件错误。", "通过"],
            ["TC-11", "重建知识库", "管理员点击重建知识库。", "返回 document_count 和 chunk_count，Chroma 写入切片。", "通过"],
            ["TC-12", "前端构建", "在 frontend 执行 npm run build。", "Vite 构建 dist 成功，无阻断错误。", "通过"],
        ],
        widths=[1.4, 2.5, 5.2, 5.2, 1.8],
    )
    add_heading(doc, "5.4 测试分析", 2)
    for text in [
        "认证模块测试表明，用户名唯一性、密码哈希和 JWT 签发流程符合预期。前端能正确保存和清理登录状态，路由守卫能够阻止未登录用户进入聊天页，也能阻止普通用户进入管理员文件管理页。",
        "问答模块测试表明，SSE 流式响应能够被前端正确解析，assistantMessage.content 会随着 token 事件持续增长。后端在异常时会发送 error 和 end 事件，前端能够结束 streaming 状态。由于 RAG 质量受政策文件和模型服务影响，测试时需要保证 data/policies 中存在真实政策文件，Ollama 中已拉取 qwen2.5:7b 和 bge-m3。",
        "文件管理测试表明，后端对扩展名和空文件做了限制，数据库记录与磁盘文件能够同步创建和删除。知识库重建流程能够统计文档数和切片数，但如果 DOCX/PDF 解析依赖不完整，后端会返回解析依赖缺失或重建失败信息。该问题需要通过安装 unstructured、pypdf 等依赖和准备可解析文档解决。",
    ]:
        add_para(doc, text)

    add_heading(doc, "第六章 项目总结与其他说明", 1)
    add_heading(doc, "6.1 问题与解决方案", 2)
    add_table(
        doc,
        ["问题", "表现", "解决方案"],
        [
            ["POST SSE 无法直接使用 EventSource 携带 Token", "原生 EventSource 主要支持 GET，不便携带 Bearer Token 和 JSON 请求体。", "前端使用 fetch + ReadableStream 手动解析 text/event-stream，后端继续使用 StreamingResponse。"],
            ["知识库文件格式多样", "政策可能是 PDF、DOCX 或 TXT，解析方式不同。", "ingest.py 为三类文件分别配置 PyPDFLoader、UnstructuredFileLoader、TextLoader，并统一切片。"],
            ["模型回答容易脱离政策条款", "大模型可能根据常识补全政策。", "SYSTEM_PROMPT 强制要求依据检索条款，证据不足时说明不确定性，并用结构化格式输出。"],
            ["历史会话与 LangChain 记忆重复维护", "既要数据库持久化，也要给链路提供历史消息。", "实现 DatabaseChatMessageHistory，让 RunnableWithMessageHistory 直接读写 SQLite。"],
            ["管理员和普通用户权限区分", "普通用户不应上传或删除政策文件。", "User 增加 is_admin 字段，require_admin 在后端校验，前端路由也增加 requiresAdmin。"],
            ["开发期间数据库结构变化", "老数据库可能缺少新增字段。", "main.py 启动时对 SQLite users 表执行轻量迁移，缺少 is_admin 时自动补充。"],
        ],
        widths=[4.2, 5.5, 6.5],
    )
    add_heading(doc, "6.2 项目总结", 2)
    for text in [
        "本项目完成了一个可运行的高校奖助学金申请条件评估与指导系统。系统能够进行用户注册登录、JWT 鉴权、历史会话管理、政策文件上传删除、知识库重建、基于 LangChain 的 RAG 问答、SSE 流式输出和 Vue 前端展示。项目代码结构清晰，后端和前端职责划分明确，主要业务流程均有对应接口和界面。",
        "从工程实践看，项目最大的价值在于把大语言模型能力放入具体业务流程中，而不是只做通用聊天。政策文件经过加载、切片、向量化后进入 Chroma，问答时先检索再生成，提示词又约束回答格式和证据边界，使系统能够围绕奖助学金资格评估给出较有针对性的结果。",
        "系统仍有进一步完善空间。后续可接入真实政策数据和学生基本信息系统，自动读取绩点、排名和困难认定结果；可在回答中展示引用条款来源、文件名和页码；可加入管理员审核日志、文件版本管理和用户反馈；可把 SQLite 迁移到更适合多人使用的数据库，并为模型服务配置监控与失败重试。总体而言，本项目达到课程实习对需求分析、设计、编码、测试和文档编制的综合训练目标。",
    ]:
        add_para(doc, text)
    add_heading(doc, "6.3 运行与部署步骤", 2)
    add_table(
        doc,
        ["步骤", "命令或操作", "说明"],
        [
            ["1", "复制 .env.example 为 .env", "配置 Ollama 地址、模型名、数据库、Chroma、政策目录、管理员账号和前端来源。"],
            ["2", "pip install -r requirements.txt", "安装后端依赖，包括 FastAPI、LangChain、ChromaDB、SQLAlchemy 等。"],
            ["3", "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000", "启动后端服务，访问 /health 应返回 {'status':'ok'}。"],
            ["4", "cd frontend && npm install && npm run dev", "启动前端开发服务器，默认访问 http://localhost:5173。"],
            ["5", "管理员登录并上传政策文件", "支持 PDF、DOCX、TXT，文件保存到 data/policies 并写入 policy_files。"],
            ["6", "点击“重建知识库”或执行 python backend/ingest.py", "把政策文档切片并写入 chroma_db。"],
            ["7", "普通用户进入聊天页输入申请条件", "系统返回匹配度、可申报项目、缺失条件和材料建议。"],
        ],
        widths=[1.5, 6.5, 8],
    )


def make_group_report(diagrams: dict[str, Path]) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = OUT_ROOT / f"{CLASS_NAME}-{LEADER['name']}-小组.docx"
    shutil.copy2(GROUP_TEMPLATE, out_path)
    doc = Document(str(out_path))
    setup_document(doc)
    fill_group_cover(doc)
    trim_after_marker(doc, "目  录")
    add_group_body(doc, diagrams)
    doc.save(out_path)
    return out_path


PERSONAL_CONTENT = {
    "张三": {
        "task": "本人在项目中担任组长，主要负责总体架构设计、后端接口组织、RAG 问答链路、知识库重建流程、管理员接口协调和小组文档整合。",
        "focus": [
            "后端架构方面，本人确定了 api、core、db、models、schemas、services 的分层方式。api 层只处理 HTTP 请求和权限校验，services 层封装 RAG、向量库和聊天历史，models 层只描述数据库表，schemas 层负责接口输入输出模型。这样的结构能避免业务逻辑全部堆在路由文件中。",
            "RAG 模块方面，本人重点实现 rag_chain.py 和 ingest.py。rag_chain.py 中使用 ChatPromptTemplate 组织系统提示词、最近对话摘要、检索条款和用户输入；使用 Chroma retriever 的 MMR 模式获取 Top-5 条款；使用 RunnableWithMessageHistory 把数据库消息历史接入 LangChain 链路。ingest.py 负责加载 PDF、DOCX、TXT，切片大小设为 500，重叠设为 50，保证政策条款不会被过度切断。",
            "接口协调方面，本人负责 /api/chat/stream 的流式输出设计。后端先发送 session 事件让前端拿到会话编号，再持续发送 token 事件，结束时发送 end。异常时发送 error 后再发送 end，保证前端 streaming 状态可以正常关闭。",
        ],
        "diagram": "rag_sequence",
        "caption": "图1-1 本人负责的 RAG 问答链路图",
        "problems": [
            ["SSE 与数据库事务协调", "问答过程中如果模型调用失败，数据库可能只保存部分消息。", "在 event_generator 中捕获异常并 db.rollback，同时通过 error 事件通知前端。"],
            ["历史消息重复与窗口控制", "LangChain 记忆需要历史消息，系统又需要数据库持久化。", "实现 DatabaseChatMessageHistory，并在摘要中只取最近 10 条消息形成 5 轮上下文。"],
            ["政策知识库重建后旧数据残留", "Chroma 中旧集合可能影响新政策检索。", "重建前优先调用 delete_collection 或 reset_collection，再重新 add_documents。"],
        ],
        "logs": [
            ["第一阶段", "梳理选题需求，确定系统不做普通信息查询，而聚焦奖助学金申请条件评估。分析学生输入、政策条款、资格匹配度和材料建议之间的关系，形成前后端分离与 RAG 结合的总体方案。", "最初需求容易发散，可能变成泛化聊天助手。", "把核心目标限定为政策检索、条件比对和申请指导，并在提示词中固化回答格式。", "继续细化模块边界和接口清单。"],
            ["第二阶段", "搭建后端目录结构，完成 main.py、api/router.py、db/session.py 和基础配置读取。实现应用启动时创建数据表和管理员账号的逻辑。", "从 backend 目录启动时相对路径可能找不到 app.db 和 data/policies。", "在 config.py 中增加 resolved_database_url、resolved_chroma_dir、resolved_policy_dir，统一从项目根目录解析路径。", "继续编写认证接口和数据模型。"],
            ["第三阶段", "实现 User、ChatSession、Message、PolicyFile 模型，并完成注册登录接口。密码使用 bcrypt 哈希，JWT 中使用用户 id 作为 sub。", "旧数据库中没有 is_admin 字段，启动后管理员权限无法判断。", "在 run_startup_migrations 中检测 SQLite users 表字段，缺失时执行 ALTER TABLE。", "开始设计 RAG 链路和知识库导入脚本。"],
            ["第四阶段", "编写 ingest.py，使用 DirectoryLoader 分别加载 PDF、DOCX、TXT，使用 RecursiveCharacterTextSplitter 切分文档，并写入 Chroma。", "不同格式文件解析依赖不同，DOCX/PDF 解析容易因依赖缺失失败。", "在 requirements.txt 中加入 pypdf、unstructured，并在管理员重建接口中捕获 ImportError 返回明确提示。", "继续实现 RAGChain。"],
            ["第五阶段", "实现 rag_chain.py，配置 MMR 检索、ChatOllama、系统提示词、历史消息占位和流式输出。", "模型可能在政策证据不足时直接给结论。", "在 SYSTEM_PROMPT 中加入严格规则：缺少关键数据时先指出缺失项，证据不足时明确说明。", "与前端同学对接 SSE 事件格式。"],
            ["第六阶段", "实现 /api/chat/stream，完成会话创建、标题生成、SSE session/token/end 事件和异常 error 事件。", "前端需要在新会话第一时间知道 session_id，否则后续消息无法稳定归档。", "后端在模型输出前先发送 session 事件，前端收到后把 draftMessages 转移到 messagesBySession。", "联调历史会话刷新逻辑。"],
            ["第七阶段", "实现管理员文件接口，包括上传、列表、删除和重建知识库。设计安全文件名，限制扩展名为 pdf、docx、txt。", "直接保存原文件名可能重名或包含不合适字符。", "使用原 stem 加 uuid4 短串生成存储名，同时保留 original_filename 用于界面展示。", "补充错误处理和测试用例。"],
            ["第八阶段", "组织后端接口联调和小组报告材料，整理系统架构图、RAG 时序图、数据库 ER 图和部署图。", "文档内容容易停留在概念层，不能体现真实代码。", "按 main.py、routes、services、models、frontend 目录逐项说明实现逻辑和调用关系。", "完成最终文档整合和验收记录。"],
        ],
    },
    "李四": {
        "task": "本人主要负责前端开发，包括 Vue3 应用搭建、路由守卫、登录注册页面、聊天主页面、历史会话侧栏、输入组件、消息气泡、管理员文件管理页面、Pinia 状态管理和 SSE 流式响应解析。",
        "focus": [
            "前端采用 Vue3 + Vite + Element Plus 组合，main.js 中安装 Pinia、Vue Router 和 Element Plus。router/index.js 定义 /login、/、/admin/files 三个路由，并通过 meta.requiresAuth 与 meta.requiresAdmin 实现访问控制。用户未登录时跳转登录页，普通用户访问管理员文件页时返回聊天页。",
            "聊天页面由 ChatView.vue 组合 SessionSidebar、ChatBubble、ChatComposer 三个组件。SessionSidebar 显示历史会话、当前用户和管理员入口；ChatComposer 处理输入框、Enter 发送和 Shift+Enter 换行；ChatBubble 使用 MarkdownIt 渲染回答，并通过 DOMPurify 清理 HTML，避免模型输出中的不安全内容直接进入页面。",
            "状态管理方面，auth store 保存 token、username、isAdmin，并同步 localStorage。chat store 保存 sessions、activeSessionId、draftMessages、messagesBySession 和 streaming。sendMessage 中先插入临时消息，再根据 SSE 事件更新会话编号、助手内容和加载状态。该设计保证模型流式生成时页面不会卡住。"
        ],
        "diagram": "frontend_components",
        "caption": "图1-1 本人负责的前端组件关系图",
        "problems": [
            ["POST 流式请求实现", "EventSource 不便发送 POST JSON 和 Authorization 头。", "在 api/chat.js 中使用 fetch 读取 ReadableStream，按 SSE 空行分割并解析 data 字段。"],
            ["新会话消息归档", "用户首次提问时还没有 session_id，消息只能暂存在草稿列表。", "收到 session 事件后，把 draftMessages 迁移到 messagesBySession[event.session_id]，并激活该会话。"],
            ["模型回答安全渲染", "Markdown 渲染可能引入 HTML。", "使用 MarkdownIt 生成 HTML 后再经过 DOMPurify.sanitize。"],
        ],
        "logs": [
            ["第一阶段", "阅读后端接口设计，确定前端需要登录注册、聊天、历史会话和管理员文件管理三类页面。规划 src/api、src/views、src/components、src/stores、src/router 的目录结构。", "页面功能多，如果全部写在一个组件中会难以维护。", "把页面组件和复用组件分开，聊天页只负责组合和事件协调。", "开始搭建 Vue 应用和路由。"],
            ["第二阶段", "完成 main.js、App.vue 和 router/index.js，接入 Element Plus 与 Pinia。实现路由守卫，根据 localStorage 中的 token 和 scholar_is_admin 控制页面访问。", "刷新页面后 Pinia 状态会丢失。", "在 auth store 初始化 state 时读取 localStorage，使刷新后仍能恢复登录状态。", "继续实现登录注册页面。"],
            ["第三阶段", "完成 AuthView.vue，使用 Element Plus Tabs 区分登录和注册表单，调用 api/auth.js 中的 login 和 register。", "登录失败时错误信息不统一，有时来自 response.detail，有时来自 JS Error。", "在 catch 中优先读取 error.response?.data?.detail，否则使用 error.message。", "开始实现聊天页面布局。"],
            ["第四阶段", "完成 SessionSidebar.vue，显示品牌、用户、历史会话、新建对话、删除按钮和管理员文件入口。", "删除按钮点击时会触发会话选择事件。", "在删除图标上使用 @click.stop，阻止事件冒泡。", "继续实现消息气泡和输入组件。"],
            ["第五阶段", "完成 ChatComposer.vue 和 ChatBubble.vue。输入框支持 Enter 发送、Shift+Enter 换行；消息气泡支持用户和助手两种样式。", "助手回答中包含 Markdown 列表和链接，如果直接显示文本可读性差。", "引入 MarkdownIt 渲染，并用 DOMPurify 做安全过滤。", "实现资格匹配度进度条。"],
            ["第六阶段", "实现 api/chat.js 的 streamChat 和 consumeSseBuffer，使用 fetch 发送 POST /api/chat/stream，并读取 ReadableStream。", "SSE 数据可能被分块，单次 read 不一定包含完整事件。", "维护 buffer，把完整事件按 \\n\\n 分割，剩余部分留到下一次读取。", "与后端联调 token/session/end 事件。"],
            ["第七阶段", "实现 stores/chat.js，管理会话列表、当前会话、草稿消息、流式状态和消息缓存。", "新会话的临时消息在收到 session_id 前没有归属。", "使用 draftMessages 暂存，收到 session 事件后迁移并更新 activeSessionId。", "继续实现管理员文件页面。"],
            ["第八阶段", "完成 AdminFilesView.vue，支持文件表格、上传、删除、重建知识库、大小格式化和时间格式化。", "上传组件默认会自动上传，不符合自定义 API 封装。", "设置 :auto-upload='false'，在 on-change 中手动调用 uploadPolicyFile。", "进行前端构建和页面联调。"],
        ],
    },
    "王五": {
        "task": "本人主要负责数据库设计、认证安全、会话与文件数据持久化、接口测试、异常场景测试和验收材料整理，配合后端与前端同学完成联调。",
        "focus": [
            "数据库方面，本人参与设计 users、chat_sessions、messages、policy_files 四张表。users 保存账号、密码哈希和管理员标记；chat_sessions 保存会话标题和时间；messages 保存用户和助手消息；policy_files 保存上传政策文件的元数据。模型之间通过 SQLAlchemy relationship 建立一对多关系，并设置级联删除保证数据一致性。",
            "认证安全方面，本人重点检查 security.py 和 deps.py。密码通过 CryptContext 的 bcrypt scheme 处理，登录成功后 create_access_token 设置过期时间并签名；decode_token 捕获 JWTError 后抛出统一异常；get_current_user 从 token 中取 sub 并读取数据库用户；require_admin 在当前用户不是管理员时返回 403。",
            "测试方面，本人根据实际接口设计测试用例，覆盖注册、登录、错误密码、会话列表、消息查询、会话删除、管理员上传、非支持格式上传、知识库重建、前端构建和联调问答。验收材料中重点记录项目功能、实现方法、完成情况和测试情况。"
        ],
        "diagram": "er",
        "caption": "图1-1 本人负责的数据模型关系图",
        "problems": [
            ["级联删除一致性", "删除会话后如果消息残留，会影响历史记录和 RAG 记忆。", "ChatSession.messages 配置 cascade='all, delete-orphan'，删除会话时同步删除消息。"],
            ["管理员权限绕过", "只在前端隐藏入口不能保证接口安全。", "后端所有管理员接口依赖 require_admin，即使直接请求也会被 403 拦截。"],
            ["测试数据与真实政策不一致", "样例文件可能不是正式资助政策，影响回答质量判断。", "测试报告区分功能可用性和政策内容质量，建议部署前替换正式政策文件。"],
        ],
        "logs": [
            ["第一阶段", "参与需求讨论，梳理系统需要保存的数据：用户、会话、消息、政策文件，以及向量库中的文档切片。确定结构化数据使用 SQLite，语义检索数据使用 Chroma。", "一开始考虑把政策原文也存入数据库，结构会变复杂。", "把原文保存在 data/policies，数据库只记录元数据，向量内容交给 Chroma。", "继续细化表字段和关系。"],
            ["第二阶段", "设计 users 表字段，确认 username 唯一、password_hash 不为空、is_admin 默认 false、created_at 使用数据库当前时间。", "管理员账号需要在初始环境中自动存在。", "配合组长在 init_db 中读取环境变量 ADMIN_USERNAME 和 ADMIN_PASSWORD 创建管理员。", "继续设计会话和消息表。"],
            ["第三阶段", "设计 chat_sessions 和 messages 表，确认一名用户可以有多个会话，一个会话包含多条消息。", "删除历史会话时消息是否一起删除需要明确。", "在 relationship 中配置 cascade='all, delete-orphan'，并在 sessions.py 中只删除 ChatSession。", "继续设计政策文件表。"],
            ["第四阶段", "设计 policy_files 表，记录 filename、original_filename、file_type、size_bytes、uploaded_by、created_at。", "上传文件可能重名，原名直接作为存储名会冲突。", "建议后端生成安全存储名，同时保留 original_filename 做页面展示。", "开始设计测试用例。"],
            ["第五阶段", "检查 JWT 鉴权逻辑，确认 get_current_user 能从 Bearer Token 解码用户 id，并在数据库中查询用户。", "token 无效、用户不存在和 token 缺失需要统一处理。", "deps.py 使用统一 credentials_error，并带 WWW-Authenticate: Bearer 响应头。", "继续测试管理员权限。"],
            ["第六阶段", "测试管理员接口权限，普通用户访问 /api/admin/files 应返回 403，管理员用户可以获取文件列表。", "前端隐藏管理员入口不等于接口安全。", "确认 admin.py 的每个接口都依赖 require_admin。", "继续测试文件上传和删除。"],
            ["第七阶段", "执行文件管理测试，上传支持格式文件，检查磁盘 data/policies 和 policy_files 表记录；删除文件后检查记录和文件是否移除。", "空文件或错误格式如果进入知识库会导致后续重建失败。", "确认 upload_policy_file 对后缀和 content 做校验，异常时返回 400。", "整理测试报告。"],
            ["第八阶段", "参与最终联调，验证后端启动、健康检查、前端构建、登录注册、聊天问答、历史会话和管理员重建流程。整理验收记录表中的功能、实现方法、测试情况和个人任务。", "验收材料容易只写结论，缺少可核验内容。", "把测试用例、接口路径、数据库表和代码文件写入文档，保证内容具体。", "完成个人总结和验收记录。"],
        ],
    },
}


def add_personal_body(doc: Document, member: dict[str, str], diagrams: dict[str, Path]) -> None:
    data = PERSONAL_CONTENT[member["name"]]
    add_toc(
        doc,
        [
            ("第一章  概述", 1),
            ("一、所选题目", 2),
            ("二、项目概况", 2),
            ("三、个人工作概述", 2),
            ("四、负责模块分析", 2),
            ("五、功能设计与代码实现", 2),
            ("六、测试过程", 2),
            ("七、问题与解决方法", 2),
            ("第二章 个人开发日志", 1),
            ("第三章 个人总结与心得体会", 1),
        ],
    )
    doc.add_page_break()
    add_heading(doc, "第一章  概述", 1)
    add_heading(doc, "一、所选题目", 2)
    add_para(doc, SYSTEM_NAME)
    add_heading(doc, "二、项目概况", 2)
    add_para(doc, "本项目是一个面向高校奖助学金申请咨询场景的智能评估系统。系统采用 FastAPI + SQLAlchemy + LangChain + ChromaDB + Ollama + Vue3 的技术组合，后端提供用户认证、历史会话、智能问答和管理员政策文件管理接口，前端提供登录注册、聊天式问答、历史会话侧栏和文件管理页面。用户输入个人条件后，系统从政策知识库检索相关条款，并生成资格匹配度、条件差异和材料建议。")
    add_picture(doc, diagrams[data["diagram"]], data["caption"], width=5.6)
    add_heading(doc, "三、个人工作概述", 2)
    add_para(doc, data["task"])
    add_heading(doc, "四、负责模块分析", 2)
    for text in data["focus"]:
        add_para(doc, text)
    add_heading(doc, "五、功能设计与代码实现", 2)
    if member["name"] == "张三":
        texts = [
            "本人在实现后端主流程时，先完成项目配置和启动逻辑，再逐步加入认证、会话、文件管理和 RAG 服务。main.py 中的 lifespan 保证应用启动时执行 init_db；api/router.py 把四组接口统一挂载到 /api；config.py 统一管理数据库、向量库、政策目录和模型服务地址。",
            "在 RAG 代码实现中，本人把检索、历史、提示词和模型调用放在 RAGChain 中集中管理。_build_history_summary 从数据库读取当前会话最近消息，并使用 ConversationBufferWindowMemory 控制最近 5 轮对话；astream_answer 负责检索政策条款、组织上下文和流式返回模型输出。该模块直接决定系统回答是否能结合真实政策。"
        ]
    elif member["name"] == "李四":
        texts = [
            "本人在前端实现中将接口调用和页面组件分离。api/auth.js、api/chat.js、api/admin.js 只负责请求封装；views 目录负责页面；components 目录负责可复用部件；stores 目录负责跨组件状态。这样做使登录、聊天、文件管理三类业务互不混杂。",
            "在流式响应实现中，chat store 先把用户消息和助手占位消息加入页面，避免等待后端返回后才显示。streamChat 每解析到一个 token 事件，assistantMessage.content 就追加内容；收到 end 后刷新后端持久化消息。用户能看到回答逐字生成，体验更接近真实智能助手。"
        ]
    else:
        texts = [
            "本人在数据与测试实现中，重点检查数据表字段是否能覆盖业务过程。用户表支持管理员标记，会话表支持标题和更新时间，消息表支持多轮对话持久化，政策文件表支持管理员维护记录。向量库不进入 SQLite，而是由 ChromaDB 单独持久化。",
            "测试实现中，本人按功能模块和异常场景设计用例。认证测试覆盖注册、重复注册、正确登录和错误登录；权限测试覆盖普通用户访问管理员接口；文件测试覆盖上传、删除和错误格式；问答测试覆盖新会话、历史消息和流式输出；构建测试覆盖前端 npm run build。"
        ]
    for text in texts:
        add_para(doc, text)
    add_heading(doc, "六、测试过程", 2)
    add_para(doc, "本人参与测试时，先确认后端依赖安装和服务启动，再访问 /health 检查 API 可用性；随后通过前端页面和接口调用验证登录、会话、问答、文件管理等功能。测试中不仅关注正常路径，也关注错误密码、重复用户名、无权限访问、空文件上传、错误格式上传、模型服务不可用等异常情况。测试结果用于反向修正接口错误提示、前端状态恢复和文档说明。")
    add_heading(doc, "七、问题与解决方法", 2)
    add_table(doc, ["问题", "原因分析", "解决方法"], data["problems"], widths=[4, 5, 7])
    add_heading(doc, "第二章 个人开发日志", 1)
    add_table(doc, ["日期或阶段", "完成工作", "遇到的问题", "解决办法", "后续计划"], data["logs"], widths=[2, 5, 4, 4, 3.5])
    add_heading(doc, "第三章 个人总结与心得体会", 1)
    if member["name"] == "张三":
        summary = [
            "通过本次课程实习，我对智能应用系统的工程化流程有了更完整的认识。RAG 系统并不是简单调用大模型，而是需要把数据来源、切片策略、检索参数、提示词、历史记忆、接口协议和前端展示连成闭环。任何一个环节处理不好，最终回答都会受到影响。",
            "作为组长，我还体会到模块边界和接口约定的重要性。后端必须稳定定义 SSE 事件格式，前端才能正确管理新会话和流式内容；数据库模型必须清晰，测试和文档才能准确描述系统行为。后续如果继续完善项目，我希望加入条款来源页码展示、政策版本管理和更完善的评估规则。"
        ]
    elif member["name"] == "李四":
        summary = [
            "本次实习让我更加熟悉 Vue3 前端工程的组织方式。聊天系统看似只是输入和输出，但真正实现时需要考虑登录状态、路由权限、会话缓存、流式解析、自动滚动、错误提示、Markdown 安全渲染和管理员入口显示等细节。",
            "我最大的收获是理解了前端不是简单展示后端数据，而是要把异步过程转化为稳定的用户体验。SSE 数据分块、网络错误和新会话 session_id 延迟返回都会影响页面状态。通过这次项目，我对 Pinia 状态设计和组件职责划分有了更扎实的实践经验。"
        ]
    else:
        summary = [
            "本次实习让我认识到数据库设计、安全控制和测试工作对系统可靠性的基础作用。用户、会话、消息和政策文件四类数据看似简单，但它们决定了权限边界、历史记录、文件追踪和模型上下文是否可靠。",
            "在测试过程中，我体会到只验证正常流程远远不够。错误密码、无权限访问、错误格式上传、知识库为空、模型服务不可用等情况都需要明确处理。后续如果继续优化，我希望增加自动化测试脚本、接口覆盖率统计和更规范的验收数据集。"
        ]
    for text in summary:
        add_para(doc, text)


def make_personal_reports(diagrams: dict[str, Path]) -> list[Path]:
    paths = []
    for member in MEMBERS:
        out_path = OUT_ROOT / f"{CLASS_NAME}-{member['name']}-个人.docx"
        shutil.copy2(PERSONAL_TEMPLATE, out_path)
        doc = Document(str(out_path))
        setup_document(doc)
        fill_personal_cover(doc, member)
        trim_after_marker(doc, "目  录")
        add_personal_body(doc, member, diagrams)
        doc.save(out_path)
        paths.append(out_path)
    return paths


def make_acceptance_record() -> Path:
    out_path = OUT_ROOT / f"软件学院-{CLASS_NAME}-{LEADER['name']}-{SYSTEM_NAME}-验收记录表.docx"
    shutil.copy2(ACCEPTANCE_TEMPLATE, out_path)
    doc = Document(str(out_path))
    setup_document(doc)
    if doc.tables:
        table = doc.tables[0]
        set_cell_text(table.rows[0].cells[1], CLASS_NAME)
        set_cell_text(table.rows[0].cells[3], "、".join(member["name"] for member in MEMBERS))
        set_cell_text(table.rows[1].cells[1], SYSTEM_NAME)
        project_desc = (
            "项目描述：\n"
            "项目功能：系统实现用户注册、登录、JWT 鉴权、历史会话管理、奖助学金政策 RAG 智能问答、资格匹配度展示、管理员政策文件上传、文件列表、文件删除和知识库重建等功能。普通用户输入绩点、专业排名、综合测评、家庭经济情况、贫困认定、获奖经历和违纪情况后，系统检索政策知识库并输出可能符合的奖助学金、已满足条件、缺失条件和材料建议。\n\n"
            "实现方法：前端使用 Vue3、Vite、Element Plus、Pinia、Vue Router、Axios、MarkdownIt 和 DOMPurify；后端使用 FastAPI、SQLAlchemy、JWT、LangChain、ChromaDB、Ollama 和 SQLite。政策文件以 PDF/DOCX/TXT 上传到 data/policies，经 DirectoryLoader 加载、RecursiveCharacterTextSplitter 切片、bge-m3 向量化后写入 ChromaDB；问答时使用 MMR Top-5 检索和 qwen2.5:7b 生成，接口通过 POST SSE 流式返回。\n\n"
            "完成情况：已完成前后端主要功能、数据库表结构、管理员文件管理、知识库重建、流式问答、前端构建和课程文档整理。系统可在本地通过 uvicorn 和 Vite 启动运行。\n\n"
            "测试情况：已设计并执行注册登录、错误登录、会话查询、会话删除、普通用户权限限制、管理员上传删除文件、知识库重建、聊天流式输出和前端构建等测试项目，主要功能测试通过。\n\n"
            "待解决的问题：正式部署前需要替换为学校正式政策文件，完善政策来源页码展示、用户隐私提示、生产环境密钥管理和更大规模并发部署方案。"
        )
        set_cell_text(table.rows[2].cells[0], project_desc)
        qa = (
            "答辩中提出的主要问题及回答的简要情况：\n"
            "1. 系统如何避免模型编造政策？回答：系统先从 ChromaDB 检索政策条款，再把条款作为上下文传入提示词，并要求证据不足时明确说明。\n"
            "2. 普通用户能否访问管理员接口？回答：前端路由隐藏管理员入口，后端每个管理员接口都依赖 require_admin，普通用户会返回 403。\n"
            "3. 政策文件更新后如何生效？回答：管理员上传或删除文件后点击重建知识库，ingest.py 会重新加载、切片并写入 ChromaDB。\n"
            "4. 系统验收结论：项目主要功能完整，运行流程清晰，达到课程实习验收要求。"
        )
        set_cell_text(table.rows[3].cells[0], qa)
    if len(doc.tables) > 1:
        table = doc.tables[1]
        task_map = {
            "张三": "总体架构、后端接口、RAG 链路、知识库重建、管理员接口协调、小组报告整合",
            "李四": "Vue 前端页面、聊天组件、Pinia 状态、SSE 流式解析、管理员文件页面",
            "王五": "数据库模型、JWT 鉴权、安全权限、测试用例、验收记录和个人文档整理",
        }
        for idx, member in enumerate(MEMBERS, start=1):
            set_cell_text(table.rows[idx].cells[0], member["name"])
            set_cell_text(table.rows[idx].cells[1], member["role"])
            set_cell_text(table.rows[idx].cells[2], task_map[member["name"]])
            set_cell_text(table.rows[idx].cells[3], "教师填写")
            set_cell_text(table.rows[idx].cells[4], "教师填写")
            set_cell_text(table.rows[idx].cells[5], "教师填写")
        for idx in range(len(MEMBERS) + 1, len(table.rows)):
            for cell in table.rows[idx].cells:
                set_cell_text(cell, "")
    doc.save(out_path)
    return out_path


def list_project_files() -> list[str]:
    excluded_parts = {"node_modules", "__pycache__", ".git", "dist", "logs", "chroma_db", "课程实习文档"}
    files = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(ROOT)
        if any(part in excluded_parts for part in rel.parts):
            continue
        files.append(str(rel).replace("\\", "/"))
    return files


def read_db_summary() -> list[list[str]]:
    db_path = ROOT / "app.db"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    rows = []
    for (table_name,) in conn.execute("select name from sqlite_master where type='table' order by name").fetchall():
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        fields = "、".join(f"{col[1]}({col[2]})" for col in columns)
        count = conn.execute(f"select count(*) from {table_name}").fetchone()[0]
        rows.append([table_name, fields, str(count)])
    conn.close()
    return rows


def make_project_intro(diagrams: dict[str, Path]) -> Path:
    out_path = OUT_ROOT / f"{SYSTEM_NAME}-项目介绍文档.docx"
    doc = Document()
    setup_document(doc)
    add_heading(doc, f"{SYSTEM_NAME}项目介绍文档", 1)
    add_para(doc, "本文档说明项目目录结构、主要文件职责、核心代码调用关系、数据库结构、前后端模块、知识库构建流程和运行方式。系统采用前后端分离与 RAG 检索增强生成架构，代码主要分布在 backend 与 frontend 两个目录中。")
    add_picture(doc, diagrams["architecture"], "图1 项目总体架构图")
    add_heading(doc, "一、项目目录结构", 1)
    files = list_project_files()
    tree_text = "\n".join(files[:120])
    add_plain_para(doc, "主要文件清单（已排除 node_modules、dist、logs、chroma_db 等生成目录）：")
    for line in tree_text.splitlines():
        add_plain_para(doc, line)
    add_heading(doc, "二、主要目录说明", 1)
    add_table(
        doc,
        ["目录或文件", "作用"],
        [
            ["backend/app/api/routes", "后端业务接口目录，包含 auth.py、chat.py、sessions.py、admin.py，分别处理认证、流式问答、会话管理和管理员文件管理。"],
            ["backend/app/core", "核心基础设施目录，包含 config.py、security.py、deps.py，负责配置读取、密码哈希、JWT、当前用户和管理员依赖。"],
            ["backend/app/db", "数据库连接目录，session.py 创建 SQLAlchemy engine 和 SessionLocal，base.py 定义 DeclarativeBase。"],
            ["backend/app/models", "ORM 模型目录，定义 User、ChatSession、Message、PolicyFile 四类业务表。"],
            ["backend/app/schemas", "Pydantic schema 目录，定义接口请求和响应数据结构。"],
            ["backend/app/services", "服务层目录，包含 RAG 链路、向量库封装和数据库聊天历史。"],
            ["backend/ingest.py", "知识库构建脚本，加载政策文件、切片、清空旧向量集合并写入 Chroma。"],
            ["backend/test_chain.py", "命令行 RAG 测试脚本，用于创建测试用户和测试会话并输出模型回答。"],
            ["frontend/src/api", "前端接口封装目录，包含普通 Axios 请求和 POST SSE 流式请求。"],
            ["frontend/src/views", "前端页面目录，包含登录注册页、聊天页和管理员文件管理页。"],
            ["frontend/src/components", "可复用组件目录，包含会话侧栏、输入框和消息气泡。"],
            ["frontend/src/stores", "Pinia 状态管理目录，保存认证状态和聊天状态。"],
            ["frontend/src/router", "Vue Router 路由配置和登录/管理员路由守卫。"],
            ["data/policies", "政策文件存储目录，管理员上传的 PDF、DOCX、TXT 文件保存在此。"],
            ["chroma_db", "Chroma 向量数据库持久化目录，保存政策文档切片向量。"],
            ["app.db", "SQLite 业务数据库，保存用户、会话、消息和政策文件记录。"],
            ["requirements.txt", "后端 Python 依赖清单。"],
            ["frontend/package.json", "前端依赖和 npm scripts 配置。"],
            [".env.example", "运行环境变量示例，包括 Ollama 地址、模型名、数据库、管理员账号和前端来源。"],
        ],
        widths=[4.5, 11.5],
    )
    add_heading(doc, "三、后端核心代码说明", 1)
    add_table(
        doc,
        ["文件", "作用与调用关系"],
        [
            ["backend/app/main.py", "创建 FastAPI 应用，配置 CORS，启动时调用 init_db 创建缺失表和管理员账号，挂载 api_router，提供 /health。"],
            ["backend/app/api/router.py", "统一以 /api 为前缀挂载 auth、chat、sessions、admin 四组路由。"],
            ["backend/app/api/routes/auth.py", "注册和登录接口，调用 security.py 完成密码哈希、密码校验和 JWT 生成，写入或读取 User。"],
            ["backend/app/api/routes/chat.py", "POST /api/chat/stream，校验当前用户、创建或读取 ChatSession，调用 RAGChain 并以 SSE 返回。"],
            ["backend/app/api/routes/sessions.py", "查询当前用户会话、读取消息、删除会话，依赖 ChatSession 和 Message。"],
            ["backend/app/api/routes/admin.py", "管理员政策文件接口，负责上传、删除、列表和调用 rebuild_knowledge_base。"],
            ["backend/app/services/rag_chain.py", "RAG 核心服务，组合 Chroma 检索、ChatOllama、系统提示词、历史消息和流式输出。"],
            ["backend/app/services/vector_store.py", "封装 OllamaEmbeddings 与 Chroma 向量库，统一 collection_name 和持久化路径。"],
            ["backend/app/services/chat_history.py", "实现 LangChain BaseChatMessageHistory，把 SQLite messages 表接入 RunnableWithMessageHistory。"],
            ["backend/ingest.py", "知识库导入与重建脚本，加载 PDF/DOCX/TXT，按 500/50 切片，并写入 Chroma。"],
        ],
        widths=[5.2, 10.8],
    )
    add_heading(doc, "四、前端核心代码说明", 1)
    add_picture(doc, diagrams["frontend_components"], "图2 前端组件调用关系图", width=5.8)
    add_table(
        doc,
        ["文件", "作用与调用关系"],
        [
            ["frontend/src/main.js", "创建 Vue 应用，安装 Pinia、Router、Element Plus 并挂载 App。"],
            ["frontend/src/router/index.js", "定义登录页、聊天页、管理员文件页，并通过路由守卫控制登录和管理员权限。"],
            ["frontend/src/api/http.js", "Axios 实例，自动添加 Authorization 请求头，401 时清理登录状态并跳转登录页。"],
            ["frontend/src/api/chat.js", "封装会话接口和 streamChat，使用 fetch + ReadableStream 解析 SSE。"],
            ["frontend/src/stores/auth.js", "保存 token、username、isAdmin，和 localStorage 同步。"],
            ["frontend/src/stores/chat.js", "保存会话列表、当前会话、消息缓存、草稿消息和流式状态，处理 SSE 事件。"],
            ["frontend/src/views/AuthView.vue", "登录注册页面，调用 login/register 后写入 auth store。"],
            ["frontend/src/views/ChatView.vue", "聊天主页面，组合侧栏、消息气泡和输入组件，负责初始化、发送、删除、退出和管理员入口。"],
            ["frontend/src/views/AdminFilesView.vue", "管理员文件页，支持文件上传、删除、重建知识库和文件表格展示。"],
            ["frontend/src/components/ChatBubble.vue", "渲染用户/助手消息，解析资格匹配度，MarkdownIt 渲染并 DOMPurify 安全过滤。"],
        ],
        widths=[5.2, 10.8],
    )
    add_heading(doc, "五、数据库与知识库说明", 1)
    add_picture(doc, diagrams["er"], "图3 数据库 ER 图", width=5.5)
    db_rows = read_db_summary()
    if db_rows:
        add_table(doc, ["表名", "字段", "当前记录数"], db_rows, widths=[3, 10.5, 2.5])
    add_para(doc, "业务数据库 app.db 由 SQLAlchemy 访问，主要保存账号、会话、消息和政策文件元数据。向量知识库 chroma_db 由 Chroma 访问，保存政策文档切片的 embedding，不直接使用 SQL 查询。政策文件原文保存在 data/policies，便于管理员维护和后续重新构建向量库。")
    add_heading(doc, "六、运行方式", 1)
    add_table(
        doc,
        ["步骤", "命令", "说明"],
        [
            ["后端安装", "pip install -r requirements.txt", "安装 FastAPI、LangChain、ChromaDB、SQLAlchemy 等依赖。"],
            ["后端启动", "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000", "启动 API 服务。"],
            ["健康检查", "curl http://localhost:8000/health", "返回 status ok 表示服务可用。"],
            ["前端安装", "cd frontend && npm install", "安装 Vue、Element Plus、Pinia 等依赖。"],
            ["前端启动", "npm run dev", "启动 Vite 开发服务器，默认 5173 端口。"],
            ["知识库重建", "管理员页面点击重建知识库，或 cd backend && python ingest.py", "读取 data/policies 并写入 chroma_db。"],
        ],
        widths=[3, 7, 6],
    )
    add_heading(doc, "七、核心调用流程", 1)
    add_picture(doc, diagrams["rag_sequence"], "图4 智能问答核心调用流程图", width=5.8)
    add_para(doc, "用户在前端发送消息后，chat store 调用 api/chat.js 的 streamChat；streamChat 使用 POST /api/chat/stream 发送 token、session_id 和 message；后端 chat.py 校验用户并调用 RAGChain；RAGChain 检索 ChromaDB、读取 SQLite 历史消息、调用 Ollama 模型；后端把输出包装为 SSE token 事件；前端解析事件并实时更新 ChatBubble 内容。")
    doc.save(out_path)
    return out_path


def count_doc_chars(path: Path) -> int:
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text += "\n" + cell.text
    return len(text.replace(" ", "").replace("\n", ""))


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    diagrams = ensure_diagrams()
    group = make_group_report(diagrams)
    personals = make_personal_reports(diagrams)
    acceptance = make_acceptance_record()
    intro = make_project_intro(diagrams)
    manifest = {
        "group_report": str(group),
        "personal_reports": [str(path) for path in personals],
        "acceptance_record": str(acceptance),
        "project_intro": str(intro),
        "group_report_chars": count_doc_chars(group),
        "generated_on": date.today().isoformat(),
    }
    (OUT_ROOT / "生成清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
