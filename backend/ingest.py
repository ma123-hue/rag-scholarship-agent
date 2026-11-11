import json
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader, UnstructuredFileLoader
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.services.vector_store import get_vector_store


def export_policy_search_index(vector_store, target: Path) -> int:
    """导出 MCP 可直接读取的轻量向量索引，避免 stdio 子进程加载 Chroma。"""
    data = vector_store.get(include=["documents", "metadatas", "embeddings"])
    documents = data.get("documents") or []
    metadatas = data.get("metadatas") or []
    embeddings = data.get("embeddings")
    if embeddings is None:
        embeddings = []
    entries = [
        {"content": document, "metadata": metadata or {}, "embedding": list(embedding)}
        for document, metadata, embedding in zip(documents, metadatas, embeddings, strict=False)
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps({"version": 1, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return len(entries)

#文档加载函数，加载多格式文档
def load_documents(policy_dir: Path):
    loaders = [
        DirectoryLoader(
            str(policy_dir),
            glob="**/*.pdf",
            loader_cls=PyPDFLoader,     # PDF专用加载器（解析PDF文本）
            show_progress=True,         #展示加载进程
            use_multithreading=True,    #多线程并行读取文件
        ),
        DirectoryLoader(
            str(policy_dir),
            glob="**/*.docx",
            loader_cls=UnstructuredFileLoader,    #加载Word文件
            show_progress=True,
            use_multithreading=True,
        ),
        DirectoryLoader(
            str(policy_dir),
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},    # TXT编码配置
            show_progress=True,
            use_multithreading=True,
        ),
    ]

    docs = []
    # 循环遍历 3 个加载器，分别读取 PDF/Word/TXT，把所有文件解析后的文本对象合并到 docs 列表返回
    for loader in loaders:
        docs.extend(loader.load())
    return docs

#重建知识库
def rebuild_knowledge_base(policy_dir: Path | None = None) -> tuple[int, int]:
    #读取全局配置：优先用传入的目录，否则用配置文件中的目录
    settings = get_settings()
    policy_dir = policy_dir or settings.resolved_policy_dir
    if not policy_dir.exists():
        raise FileNotFoundError(f"Policy data directory not found: {policy_dir}")

    #调用文档加载函数load_documents，无文件则终止程序并报错。
    documents = load_documents(policy_dir)
    if not documents:
        raise RuntimeError(f"No policy documents found in {policy_dir}")
    #长文本分片切割：解决大文档向量化效率/效果问题
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)  #按字符递归切割，优先按段落、句子分割，最大500，重叠50，保证连贯性
    chunks = splitter.split_documents(documents)


    #初始化向量库：先清空旧数据，再重新获取实例
    vector_store = get_vector_store()
    if hasattr(vector_store, "delete_collection"):
        try:
            vector_store.delete_collection()
        except Exception:
            pass
        vector_store = get_vector_store()
    elif hasattr(vector_store, "reset_collection"):
        vector_store.reset_collection()
    #批量向量化入库
    vector_store.add_documents(chunks)
    export_policy_search_index(vector_store, settings.resolved_policy_search_index)

    return len(documents), len(chunks)



#封装执行流程，打印执行结果（文档数、分片数、向量库存储路径）
def main() -> None:
    settings = get_settings()
    doc_count, chunk_count = rebuild_knowledge_base(settings.resolved_policy_dir)

    print(f"Loaded documents: {doc_count}")         # 打印加载的文档总数
    print(f"Generated chunks: {chunk_count}")       # 打印分片总数
    print(f"Persisted to: {settings.resolved_chroma_dir}")   # 打印向量库存储路径



if __name__ == "__main__":
    main()
