# 导入必要的模块和库
import io  # 内存字节流操作
import json  # JSON数据处理
import re  # 正则表达式处理
from datetime import datetime, timezone  # 时间处理

# 导入docx相关模块，用于生成Word文档
from docx import Document
from docx.shared import Pt, RGBColor  # 字体大小、颜色设置
# FastAPI相关导入，用于构建API路由和处理请求
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse  # 流式响应返回
# Pydantic数据验证
from pydantic import BaseModel, Field
# SQLAlchemy ORM相关，数据库会话管理
from sqlalchemy.orm import Session

# 项目内部模块导入
from app.core.deps import get_current_user  # 获取当前登录用户的依赖项
from app.db.session import get_db  # 获取数据库会话的依赖项
from app.models.chat import ChatSession, Message  # 聊天会话与消息模型
from app.models.user import User  # 用户模型
from app.schemas.chat import ApprovalResumeRequest, ChatStreamRequest  # 聊天流式请求的Schema
from app.services.agent_runtime import get_agent_runtime

# 创建API路由实例，前缀和标签可在注册时配置
router = APIRouter()

EMPTY_MODEL_RESPONSE = "本轮模型没有返回有效正文，请重新发送问题；系统已保留当前会话上下文。"
TRUNCATED_RESPONSE_SUFFIX = (
    "\n\n> 本轮生成达到长度上限，内容可能不完整。"
    "如果本轮执行了报告保存，请勿直接使用该文件，请重新生成并保存完整报告。"
)


def _sse(data: dict) -> str:
    """
    构建Server-Sent Events (SSE) 格式的响应字符串
    SSE用于服务端向客户端推送流式数据，格式为"data: JSON字符串\n\n"

    Args:
        data: 要发送的字典类型数据

    Returns:
        符合SSE格式的字符串
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_session_title(message: str) -> str:
    """
    根据用户输入的消息构建聊天会话标题

    Args:
        message: 用户输入的原始消息文本

    Returns:
        处理后的会话标题，最多24个字符，超出则截断并添加省略号，空消息返回"新对话"
    """
    # 去除多余空格（连续空格、首尾空格）
    cleaned = " ".join(message.strip().split())
    # 截断过长文本，添加省略号，处理空字符串情况
    return cleaned[:24] + ("..." if len(cleaned) > 24 else "") or "新对话"


@router.post("/stream")
async def stream_chat(
        payload: ChatStreamRequest,  # 请求体数据，包含会话ID、用户消息等
        current_user: User = Depends(get_current_user),  # 依赖注入获取当前登录用户
        db: Session = Depends(get_db),  # 依赖注入获取数据库会话
):
    """
    聊天流式响应接口，处理用户的聊天请求并返回流式回答

    Args:
        payload: 聊天请求参数，包含session_id（可选）和message（用户消息）
        current_user: 当前登录用户，通过依赖项自动获取
        db: 数据库会话对象，通过依赖项自动获取

    Returns:
        StreamingResponse: SSE格式的流式响应，包含会话信息、回答token、建议问题等
    """
    agent_runtime = get_agent_runtime()
    # 初始化会话对象
    session = None

    # 如果请求中包含session_id，尝试获取已有会话
    if payload.session_id is not None:
        session = db.get(ChatSession, payload.session_id)
        # 校验会话是否存在且属于当前用户
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"  # 会话不存在返回404
            )
    else:
        # 无session_id时创建新会话
        session = ChatSession(
            user_id=current_user.id,  # 关联当前用户ID
            session_title=_build_session_title(payload.message),  # 生成会话标题
        )
        # 将新会话添加到数据库
        db.add(session)
        db.commit()  # 提交事务
        db.refresh(session)  # 刷新会话对象获取数据库生成的ID等字段

    pending_approval = await agent_runtime.pending_approval(str(session.id))
    if pending_approval:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前会话有待审批操作，请先处理审批后再发送新消息",
        )

    # Agent 的检查点只负责执行状态；用户可见消息仍统一写入原有数据库。
    db.add(Message(session_id=session.id, role="user", content=payload.message))
    db.commit()

    async def event_generator():
        """
        异步生成器函数，用于产生SSE流式响应数据
        包含会话信息、逐字回答、后续建议问题、结束/错误标识
        """
        try:
            # 首先推送会话基本信息（ID和标题）
            yield _sse(
                {
                    "type": "session",
                    "session_id": session.id,
                    "session_title": session.session_title,
                }
            )
            answer_parts: list[str] = []
            approval_required = False
            generation_truncated = False
            async for event in agent_runtime.stream(str(session.id), payload.message):
                if event.get("type") == "token":
                    answer_parts.append(str(event.get("content", "")))
                elif event.get("type") == "approval_required":
                    approval_required = True
                elif event.get("type") == "generation_truncated":
                    generation_truncated = True
                yield _sse(event)

            answer = "".join(answer_parts).strip()
            if not answer and not approval_required:
                answer = EMPTY_MODEL_RESPONSE
                yield _sse({"type": "token", "content": answer})
            elif generation_truncated and not approval_required:
                answer += TRUNCATED_RESPONSE_SUFFIX
                yield _sse({"type": "token", "content": TRUNCATED_RESPONSE_SUFFIX})
            if answer and not approval_required:
                db.add(Message(session_id=session.id, role="assistant", content=answer))

            # 更新会话的最后修改时间
            session.updated_at = datetime.now(timezone.utc)
            db.commit()  # 提交更新
            # 推送结束标识
            finish_reason = "approval_required" if approval_required else "stop"
            yield _sse({"type": "end", "finish_reason": finish_reason})
        except Exception as exc:
            # 异常处理：回滚数据库事务
            db.rollback()
            # 推送错误信息
            yield _sse({"type": "error", "content": str(exc)})
            # 推送结束标识
            yield _sse({"type": "end", "finish_reason": "error"})

    # 返回流式响应，配置SSE相关参数
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",  # SSE媒体类型
        headers={
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive",  # 保持连接
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲，确保流式传输
        },
    )


def _owned_session(db: Session, session_id: int, current_user: User) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.get("/{session_id}/pending-approval")
async def get_pending_approval(
        session_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    _owned_session(db, session_id, current_user)
    approval = await get_agent_runtime().pending_approval(str(session_id))
    return {"pending": approval is not None, "approval": approval}


@router.post("/{session_id}/resume")
async def resume_chat(
        session_id: int,
        payload: ApprovalResumeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    session = _owned_session(db, session_id, current_user)
    agent_runtime = get_agent_runtime()
    pending = await agent_runtime.pending_approval(str(session_id))
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前会话没有待审批操作，可能已经处理或失效",
        )
    if len(payload.decisions) != len(pending.get("actions", [])):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="审批决定数量必须与待审批操作数量一致",
        )

    async def event_generator():
        try:
            yield _sse(
                {
                    "type": "session",
                    "session_id": session.id,
                    "session_title": session.session_title,
                }
            )
            answer_parts: list[str] = []
            approval_required = False
            generation_truncated = False
            decisions = [decision.model_dump(exclude_none=True) for decision in payload.decisions]
            async for event in agent_runtime.resume(str(session_id), decisions):
                if event.get("type") == "token":
                    answer_parts.append(str(event.get("content", "")))
                elif event.get("type") == "approval_required":
                    approval_required = True
                elif event.get("type") == "generation_truncated":
                    generation_truncated = True
                yield _sse(event)

            answer = "".join(answer_parts).strip()
            if not answer and not approval_required:
                answer = EMPTY_MODEL_RESPONSE
                yield _sse({"type": "token", "content": answer})
            elif generation_truncated and not approval_required:
                answer += TRUNCATED_RESPONSE_SUFFIX
                yield _sse({"type": "token", "content": TRUNCATED_RESPONSE_SUFFIX})
            if answer and not approval_required:
                db.add(Message(session_id=session.id, role="assistant", content=answer))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            finish_reason = "approval_required" if approval_required else "stop"
            yield _sse({"type": "end", "finish_reason": finish_reason})
        except Exception as exc:
            db.rollback()
            yield _sse({"type": "error", "content": str(exc)})
            yield _sse({"type": "end", "finish_reason": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ExportDocxRequest(BaseModel):
    """
    导出Word文档的请求体模型

    Attributes:
        content: 要导出的markdown格式文本，长度限制1-50000字符
    """
    content: str = Field(min_length=1, max_length=50000)


# 正则表达式编译，用于匹配markdown格式
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")  # 匹配粗体 **内容**
_MARKDOWN_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)  # 匹配1-3级标题 ### 标题
_MARKDOWN_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)  # 匹配无序列表项 -/* 内容
_MARKDOWN_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+)$", re.MULTILINE)  # 匹配有序列表项 1. 内容/1) 内容


def _add_markdown_paragraph(doc: Document, text: str) -> None:
    """
    向Word文档中添加支持markdown粗体的段落

    Args:
        doc: Document对象，目标Word文档
        text: 要添加的文本，包含可能的**粗体**标记
    """
    # 空文本添加空段落
    if not text.strip():
        doc.add_paragraph()
        return
    # 创建新段落
    para = doc.add_paragraph()
    # 按粗体标记分割文本
    parts = _MARKDOWN_BOLD.split(text)
    for idx, part in enumerate(parts):
        if not part:
            continue
        # 向段落添加文本片段
        run = para.add_run(part)
        run.font.size = Pt(11)  # 设置字体大小11号
        # 奇数索引的片段是粗体（因为split后格式为：普通文本、粗体文本、普通文本...）
        if idx % 2 == 1:
            run.bold = True


def convert_markdown_to_docx(content: str) -> bytes:
    """
    将markdown格式的文本转换为Word文档（docx格式），并返回字节数据

    支持的markdown语法：
    - 1-3级标题（#/##/###）
    - 粗体（**内容**）
    - 无序列表（-/* 内容）
    - 有序列表（数字. / 数字) 内容）
    - 分隔线（---）

    Args:
        content: markdown格式的文本内容

    Returns:
        生成的docx文件的字节数据
    """
    # 创建新的Word文档对象
    doc = Document()
    # 设置默认样式（Normal）的字体
    style = doc.styles["Normal"]
    font = style.font
    font.name = "SimSun"  # 设置字体为宋体
    font.size = Pt(11)  # 设置默认字体大小11号

    # 按行分割文本
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # 匹配标题行（1-3级）
        heading_match = _MARKDOWN_HEADING.match(line)
        if heading_match:
            level = len(heading_match.group(1))  # 获取标题级别（1-3）
            # 添加标题，设置级别
            heading = doc.add_heading(heading_match.group(2), level=level)
            # 设置标题字体颜色为蓝色（RGB: 0x1A, 0x56, 0xDB）
            for run in heading.runs:
                run.font.color.rgb = RGBColor(0x1A, 0x56, 0xDB)
            i += 1
            continue

        # 匹配无序列表项
        list_match = _MARKDOWN_LIST_ITEM.match(line)
        if list_match:
            # 创建带项目符号的段落
            para = doc.add_paragraph(style="List Bullet")
            # 添加列表项文本（支持粗体）
            _add_list_run(para, list_match.group(1))
            i += 1
            continue

        # 匹配有序列表项
        num_match = _MARKDOWN_NUMBERED.match(line)
        if num_match:
            # 创建带数字编号的段落
            para = doc.add_paragraph(style="List Number")
            # 添加列表项文本（支持粗体）
            _add_list_run(para, num_match.group(1))
            i += 1
            continue

        # 匹配分隔线（---）
        if line.strip() == "---":
            para = doc.add_paragraph()
            # 设置分隔线上下间距
            para.paragraph_format.space_before = Pt(4)
            para.paragraph_format.space_after = Pt(4)
            # 手动构建XML元素添加底部边框（分隔线效果）
            pPr = para._p.get_or_add_pPr()
            pBdr = pPr.makeelement(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr", {},
            )
            bottom = pBdr.makeelement(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}bottom",
                {
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val": "single",  # 单线条
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz": "6",  # 线条大小
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}space": "1",  # 间距
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}color": "CCCCCC",  # 灰色
                },
            )
            pBdr.append(bottom)
            pPr.append(pBdr)
            i += 1
            continue

        # 普通文本行，添加支持粗体的段落
        _add_markdown_paragraph(doc, line)
        i += 1

    # 将文档保存到内存字节流
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)  # 重置文件指针到开头
    return buf.read()  # 返回字节数据


def _add_list_run(para, text: str) -> None:
    """
    向列表项段落中添加支持粗体的文本

    Args:
        para: 列表项的Paragraph对象
        text: 列表项文本，包含可能的**粗体**标记
    """
    # 按粗体标记分割文本
    parts = _MARKDOWN_BOLD.split(text)
    for idx, part in enumerate(parts):
        if not part:
            continue
        # 添加文本片段
        run = para.add_run(part)
        run.font.size = Pt(11)  # 设置字体大小11号
        # 奇数索引为粗体片段
        if idx % 2 == 1:
            run.bold = True


@router.post("/export-docx")
async def export_docx(
        payload: ExportDocxRequest,  # 导出请求体，包含markdown内容
        current_user: User = Depends(get_current_user),  # 当前登录用户
):
    """
    导出markdown内容为Word文档（docx）的接口

    Args:
        payload: 导出请求参数，包含要转换的markdown内容
        current_user: 当前登录用户，通过依赖项自动获取

    Returns:
        StreamingResponse: docx文件的流式下载响应
    """
    # 将markdown内容转换为docx字节数据
    docx_bytes = convert_markdown_to_docx(payload.content)
    # 返回流式响应，支持文件下载
    return StreamingResponse(
        io.BytesIO(docx_bytes),  # 字节流作为响应体
        # 设置docx文件的媒体类型
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            # 设置下载文件名
            "Content-Disposition": "attachment; filename=scholarship-advice.docx",
        },
    )
