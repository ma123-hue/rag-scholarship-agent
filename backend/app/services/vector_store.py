from pathlib import Path

#LangChain对接 Chroma 向量数据库的核心类Chroma，用于创建 / 操作向量存储。
from langchain_chroma import Chroma

# OpenAI 兼容在线嵌入接口，默认连接阿里云百炼。
from langchain_openai import OpenAIEmbeddings
from app.core.config import get_settings


# 创建并返回在线嵌入模型实例。
def get_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    settings.require_online_api_keys()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_api_base_url,
        api_key=settings.resolved_embedding_api_key,
        chunk_size=10,
        timeout=settings.llm_request_timeout,
        max_retries=settings.llm_max_retries,
        # 百炼兼容接口要求 input 为原始字符串，不接受 OpenAI 客户端预分词后的 token ID。
        check_embedding_ctx_length=False,
    )


def get_vector_store(persist_directory: str | Path | None = None) -> Chroma:
    settings = get_settings()
    persist_path = Path(persist_directory) if persist_directory else settings.resolved_chroma_dir   #确定持久化路径
    persist_path.mkdir(parents=True, exist_ok=True)                                                 #确保目录存在
    return Chroma(
        # 初始化 Chroma 向量库
        collection_name=settings.chroma_collection_name,
        persist_directory=str(persist_path),    #Chroma 向量数据的持久化存储路径（转换为字符串，Chroma 要求字符串路径）；
        embedding_function=get_embeddings(),   #指定用于文本向量化的函数 / 模型
    )
