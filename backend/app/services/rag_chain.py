import ast
import json
import re
from functools import lru_cache  # 用于缓存函数返回值，提升性能

# LangChain相关依赖：用于构建LLM应用的核心组件
from langchain_classic.memory import ConversationBufferWindowMemory  # 对话窗口记忆（只保留最近k轮）
from langchain_core.messages import AIMessage, HumanMessage  # 定义AI/人类消息类型
from langchain_core.output_parsers import StrOutputParser  # 字符串输出解析器
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # 提示词模板/消息占位符
from langchain_core.runnables.history import RunnableWithMessageHistory  # 带对话历史的可运行链
from langchain_openai import ChatOpenAI  # OpenAI兼容在线模型接口
from sqlalchemy import select  # SQLAlchemy查询构造器
from sqlalchemy.orm import Session  # 数据库会话

# 项目内部依赖
from app.core.config import get_settings  # 配置项获取
from app.models.chat import Message  # 聊天消息模型
from app.services.chat_history import DatabaseChatMessageHistory  # 数据库存储的聊天历史
from app.services.vector_store import get_vector_store  # 向量库获取

# ===================== 核心提示词定义 =====================
# 系统提示词：定义LLM的角色和回答规则（核心业务逻辑）
SYSTEM_PROMPT = """
你是“高校资助中心专家顾问”。你的职责是依据学校奖助学金政策条款，评估学生的申请资格并给出下一步建议。

回答规则：
1. 必须严格依据提供的政策条款，不要编造政策。
2. 默认按政策咨询回答，不输出「资格匹配度」、百分比、进度或类似估算。
3. 只有当本轮回答模式明确要求资格评估，且用户已经提供个人学业/资格相关信息（如绩点、排名、综测、成绩、年级、专业、获奖、违纪、挂科、困难认定等）时，才可以输出「资格匹配度：XX%」。
4. 如果用户只是询问政策、名词、申请条件、流程、金额、材料或“学业优秀奖学金”等项目介绍，不要输出匹配度，直接解释政策条款。
5. 如果用户询问自己能否申请但个人信息不足，先列出需要补充的信息并反问，不要给暂估匹配度。
6. 做资格评估时，用分点方式说明：
   - 评估依据
   - 已满足的条件
   - 尚未满足或缺失的条件
   - 建议补充的材料和申请步骤
7. 如果政策条款之间存在差异，要显式指出差异来源。
8. 如果检索上下文不足以支持结论，要明确说明“当前知识库证据不足”。
""".strip()

SCORE_MODE_PROMPT = """
本轮回答模式：资格评估模式。
用户已提供个人条件，且问题需要判断其奖助学金申请资格。可以输出「资格匹配度：XX%」，并说明计算依据与不确定项。
""".strip()

NO_SCORE_MODE_PROMPT = """
本轮回答模式：政策咨询或资料补充模式。
严禁输出「资格匹配度」、百分比匹配、暂估匹配度或类似内容。若用户没有提供足够个人条件，只说明还需要补充哪些信息。
""".strip()

PERSONAL_INFO_PATTERN = re.compile(
    r"(大一|大二|大三|大四|研一|研二|研三|"
    r"绩点|gpa|GPA|排名|名次|前\s*\d+%|综测|综合测评|成绩|分数|平均分|学分|专业|学院|年级|"
    r"获奖|奖项|竞赛|三好学生|优秀学生干部|违纪|处分|挂科|补考|重修|"
    r"家庭经济|困难认定|贫困|低保|收入)",
)
EVALUATION_INTENT_PATTERN = re.compile(
    r"(我.*(能|可以|可不可以|能不能|是否|符合|达标|申请)|"
    r"(能|可以|可不可以|能不能|是否).*(申请|符合|达标)|"
    r"评估|判断|看看|帮我看|资格|匹配度|符合.*吗|推荐.*奖|适合.*奖)",
)
POLICY_QUERY_PATTERN = re.compile(
    r"(是什么|有哪些|有什么|介绍|说明|要求|条件|标准|流程|步骤|材料|金额|多少钱|怎么申请|如何申请|"
    r"什么时候|截止|评定办法|管理办法)",
)
AWARD_QUERY_PATTERN = re.compile(r"(奖学金|助学金|补助|困难补助|荣誉称号|优秀学生|国家奖|励志奖)")


def _has_personal_info(text: str) -> bool:
    return bool(PERSONAL_INFO_PATTERN.search(text or ""))


def _should_show_qualification_score(user_input: str, recent_user_context: str = "") -> bool:
    """
    判断本轮是否应展示资格匹配度。
    规则偏保守：没有个人条件时不展示；纯政策查询不展示。
    """
    current = user_input or ""
    combined = f"{recent_user_context}\n{current}"

    if not _has_personal_info(combined):
        return False
    if POLICY_QUERY_PATTERN.search(current) and not EVALUATION_INTENT_PATTERN.search(current):
        return False
    if EVALUATION_INTENT_PATTERN.search(current):
        return True
    return bool(AWARD_QUERY_PATTERN.search(current) and _has_personal_info(current))


def _remove_qualification_score_text(answer: str) -> str:
    """
    兜底移除模型在非评估场景中误输出的匹配度内容。
    """
    lines = []
    for line in answer.splitlines():
        if re.search(r"(资格)?匹配度\s*[:：]?\s*\d{1,3}\s*%", line):
            continue
        if re.search(r"(暂估|预估|当前).{0,8}匹配度|匹配度.{0,8}(为|是|约)", line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or answer.strip()
# 跟进问题生成提示词：要求LLM基于用户问题和助手回答，生成3个后续可能的问题
FOLLOW_UP_PROMPT = """
你需要根据用户刚才的问题和助手刚才的回答，预测用户接下来最可能继续问的 3 个问题。

要求：
1. 只输出 JSON 数组，不要输出任何解释。
2. 数组里必须正好 3 个字符串，不能嵌套数组、不能包裹在对象里。
3. 每个问题都要具体、自然、贴合当前回答，不要使用固定模板。
4. 问题应帮助用户继续完成奖助学金资格评估、材料准备或申请决策。
5. 每个问题不超过 40 个中文字符。
6. 不要在句末添加问号，系统会统一处理。
""".strip()


# ===================== 工具函数：跟进问题解析相关 =====================
def _strip_follow_up_noise(text: str) -> str:
    """
    清洗跟进问题文本中的无关噪声（如代码块标记、标点、空白符、特殊符号等）
    :param text: 原始文本
    :return: 清洗后的纯文本
    """
    # 移除首尾的代码块标记（```json/```）
    value = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.DOTALL)
    value = value.strip()
    # 移除句末标点
    value = re.sub(r"[?？。.!！]+$", "", value).strip()
    # 移除首尾引号
    value = value.strip("“”\"'")
    # 移除行首的列表符号（-/*/数字/顿号等）
    value = re.sub(r"^\s*[-*•\d.、)）]+\s*", "", value)
    # 移除首尾的括号/方括号/大括号
    value = re.sub(r"^\s*[\[\(\{]+\s*", "", value)
    value = re.sub(r"\s*[\]\)\}]+\s*$", "", value)
    # 合并多个空格为单个空格
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _try_parse_literal(text: str):
    """
    尝试将文本解析为Python字面量（列表/字典等），优先用json.loads，失败则用ast.literal_eval
    :param text: 待解析文本
    :return: 解析后的对象/None（解析失败）
    """
    # 先移除句末标点
    candidate = re.sub(r"[?？。.!！]+$", "", text.strip())
    if not candidate:
        return None
    # 依次尝试JSON解析和Python字面量解析
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(candidate)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
    return None


def _flatten_follow_up_items(value) -> list[str]:
    """
    递归扁平化跟进问题的嵌套结构（支持字符串/字典/列表/元组等），提取纯文本问题列表
    :param value: 任意类型的待扁平化数据
    :return: 扁平化后的纯文本问题列表
    """
    # 空值直接返回空列表
    if value is None:
        return []

    # 字符串类型：尝试解析为结构化数据，再递归处理；否则清洗后返回
    if isinstance(value, str):
        parsed = _try_parse_literal(value)
        if parsed is not None and parsed != value:
            return _flatten_follow_up_items(parsed)
        cleaned = _strip_follow_up_noise(value)
        return [cleaned] if cleaned else []

    # 字典类型：优先解析指定关键字段，再遍历所有值
    if isinstance(value, dict):
        prioritized_keys = ("items", "suggestions", "questions", "data")  # 优先字段
        for key in prioritized_keys:
            if key in value:
                flattened = _flatten_follow_up_items(value[key])
                if flattened:
                    return flattened
        # 遍历所有值并扁平化
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_follow_up_items(nested))
        return flattened

    # 列表/元组/集合类型：遍历每个元素并扁平化
    if isinstance(value, (list, tuple, set)):
        flattened: list[str] = []
        for nested in value:
            flattened.extend(_flatten_follow_up_items(nested))
        return flattened

    # 其他类型：转为字符串后清洗
    cleaned = _strip_follow_up_noise(str(value))
    return [cleaned] if cleaned else []


def _parse_follow_up_questions(raw_output: str) -> list[str]:
    """
    核心解析函数：将LLM返回的原始文本解析为3个去重的跟进问题
    :param raw_output: LLM原始输出
    :return: 最多3个跟进问题的列表
    """
    text = raw_output.strip()
    candidates: list[str] = []

    # 第一步：提取代码块内的内容（优先处理```包裹的JSON）
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # 第二步：尝试解析为结构化数据（列表/字典）
    structured = _try_parse_literal(text)
    if structured is not None:
        candidates = _flatten_follow_up_items(structured)

    # 第三步：结构化解析失败则按行拆分文本
    if not candidates:
        snippet = None
        # 尝试提取括号/大括号内的内容
        for left, right in (("[", "]"), ("{", "}")):
            start = text.find(left)
            end = text.rfind(right)
            if start != -1 and end != -1 and start < end:
                snippet = text[start: end + 1]
                break
        if snippet:
            structured = _try_parse_literal(snippet)
            if structured is not None:
                candidates = _flatten_follow_up_items(structured)

    # 第四步：仍失败则按行拆分清洗
    if not candidates:
        for line in text.splitlines():
            cleaned = _strip_follow_up_noise(line)
            if cleaned:
                candidates.append(cleaned)

    # 最终处理：去重、取前3个
    output: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        question = _strip_follow_up_noise(item)
        if not question:
            continue
        if question in seen:
            continue
        seen.add(question)
        output.append(question)
        if len(output) == 3:  # 只保留3个
            break

    return output


# ===================== 核心类：RAG对话链 =====================
class RAGChain:
    """
    基于RAG（检索增强生成）的奖助学金资格评估对话链
    核心能力：
    1. 检索政策条款作为上下文
    2. 结合对话历史生成符合规则的回答
    3. 基于用户问题和助手回答生成跟进问题
    """

    def __init__(self) -> None:
        """初始化RAG链：加载配置、向量库、LLM、提示词模板"""
        settings = get_settings()
        settings.require_online_api_keys()
        self.vector_store = get_vector_store()  # 获取向量库（存储奖助学金政策）
        # 构建检索器：使用MMR算法（最大化边际相关性），返回top5，候选12个
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 12},
        )
        # 初始化 OpenAI 兼容在线模型。
        self.llm = ChatOpenAI(
            model=settings.llm_chat_model,
            base_url=settings.llm_api_base_url,
            api_key=settings.llm_api_key,
            temperature=0.2,
            timeout=settings.llm_request_timeout,
            max_retries=settings.llm_max_retries,
            max_completion_tokens=settings.llm_max_output_tokens,
            stream_chunk_timeout=30,
            extra_body={"enable_thinking": settings.llm_enable_thinking},
        )
        # 构建核心回答提示词模板
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),  # 系统角色定义
                (
                    "system",
                    "最近5轮对话摘要：\n{chat_history}\n\n检索到的政策条款：\n{context}",
                ),  # 对话历史+检索上下文
                ("system", "{answer_mode}"),
                MessagesPlaceholder(variable_name="history_messages"),  # 实时对话历史占位符
                ("human", "{input}"),  # 用户输入占位符
            ]
        )
        # 构建跟进问题生成提示词模板
        self.follow_up_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", FOLLOW_UP_PROMPT),  # 跟进问题生成规则
                (
                    "human",
                    "用户问题：\n{user_input}\n\n助手回答：\n{assistant_answer}",
                ),  # 输入输出上下文
            ]
        )
        # 构建基础链：提示词 → LLM → 字符串解析
        base_chain = self.prompt | self.llm | StrOutputParser()
        # 构建带对话历史的链：关联数据库存储的对话历史
        self.chain = RunnableWithMessageHistory(
            base_chain,
            self._get_message_history,  # 自定义获取对话历史的方法
            input_messages_key="input",  # 用户输入的参数名
            history_messages_key="history_messages",  # 对话历史的参数名
        )
        # 构建跟进问题生成链
        self.follow_up_chain = self.follow_up_prompt | self.llm | StrOutputParser()

    @staticmethod
    def _get_message_history(session_id: str) -> DatabaseChatMessageHistory:
        """
        获取指定会话的对话历史（数据库存储）
        :param session_id: 会话ID
        :return: 数据库对话历史对象（保留最近10条）
        """
        return DatabaseChatMessageHistory(session_id=int(session_id), window_size=10)

    def _build_history_summary(self, db: Session, session_id: int) -> str:
        """
        构建对话历史摘要：从数据库读取最近10条消息，生成5轮摘要
        :param db: 数据库会话
        :param session_id: 会话ID
        :return: 格式化的对话历史摘要
        """
        # 构造查询：按时间倒序、ID倒序取最近10条消息
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp.desc(), Message.id.desc())
            .limit(10)
        )
        # 执行查询并反转（恢复正序）
        rows = list(reversed(db.execute(stmt).scalars().all()))

        # 使用ConversationBufferWindowMemory生成5轮摘要
        memory = ConversationBufferWindowMemory(k=5, return_messages=False)
        for row in rows:
            if row.role == "user":
                memory.chat_memory.add_message(HumanMessage(content=row.content))
            else:
                memory.chat_memory.add_message(AIMessage(content=row.content))
        # 加载记忆变量（返回"history"字段）
        history_vars = memory.load_memory_variables({})
        return history_vars.get("history", "暂无历史对话。")

    def _build_recent_user_context(self, db: Session, session_id: int) -> str:
        """提取最近用户消息，用于判断是否已有个人条件。"""
        stmt = (
            select(Message)
            .where(Message.session_id == session_id, Message.role == "user")
            .order_by(Message.timestamp.desc(), Message.id.desc())
            .limit(5)
        )
        rows = list(reversed(db.execute(stmt).scalars().all()))
        return "\n".join(row.content for row in rows)

    def _replace_latest_assistant_answer(self, db: Session, session_id: int, answer: str) -> None:
        """把 LangChain 已写入数据库的最新助手消息替换为清洗后的回答。"""
        stmt = (
            select(Message)
            .where(Message.session_id == session_id, Message.role == "assistant")
            .order_by(Message.timestamp.desc(), Message.id.desc())
            .limit(1)
        )
        row = db.execute(stmt).scalar_one_or_none()
        if row and row.content != answer:
            row.content = answer
            db.commit()

    async def astream_answer(self, db: Session, session_id: int, user_input: str):
        """
        异步流式生成回答：核心业务入口
        :param db: 数据库会话
        :param session_id: 会话ID
        :param user_input: 用户输入
        :yield: 回答的逐块内容（流式输出）
        """
        # 1. 检索：根据用户输入从向量库检索政策条款
        docs = await self.retriever.ainvoke(user_input)
        context_parts = []
        for idx, doc in enumerate(docs, start=1):
            source = doc.metadata.get("source", "未知来源")  # 获取条款来源
            context_parts.append(f"[条款{idx}] 来源：{source}\n{doc.page_content}")
        # 拼接检索上下文（无结果则提示"证据不足"）
        context = "\n\n".join(context_parts) if context_parts else "当前知识库证据不足。"

        # 2. 构建对话历史摘要
        history_summary = self._build_history_summary(db, session_id)
        recent_user_context = self._build_recent_user_context(db, session_id)
        should_show_score = _should_show_qualification_score(user_input, recent_user_context)
        answer_mode = SCORE_MODE_PROMPT if should_show_score else NO_SCORE_MODE_PROMPT

        # 3. 调用链生成回答；非评估场景做兜底清洗，避免模型误输出匹配度。
        answer_parts: list[str] = []
        async for chunk in self.chain.astream(
                {
                    "context": context,  # 检索到的政策上下文
                    "chat_history": history_summary,  # 对话历史摘要
                    "answer_mode": answer_mode,  # 本轮是否允许展示匹配度
                    "input": user_input,  # 用户输入
                },
                config={"configurable": {"session_id": str(session_id)}},  # 关联会话ID
        ):
            if chunk:
                answer_parts.append(chunk)

        answer = "".join(answer_parts)
        if not should_show_score:
            answer = _remove_qualification_score_text(answer)
            self._replace_latest_assistant_answer(db, session_id, answer)
        if answer:
            yield answer

    async def agenerate_follow_ups(self, user_input: str, assistant_answer: str) -> list[str]:
        """
        异步生成跟进问题：基于用户问题和助手回答，生成3个后续问题
        :param user_input: 用户原始问题
        :param assistant_answer: 助手的回答
        :return: 最多3个跟进问题的列表
        """
        if not assistant_answer.strip():
            return []

        # 调用跟进问题生成链
        raw_output = await self.follow_up_chain.ainvoke(
            {
                "user_input": user_input,
                "assistant_answer": assistant_answer,
            }
        )
        # 解析原始输出为标准问题列表
        return _parse_follow_up_questions(raw_output)


@lru_cache
def get_rag_chain() -> RAGChain:
    """
    单例模式获取RAGChain实例（缓存装饰器保证全局唯一）
    :return: RAGChain实例
    """
    return RAGChain()
