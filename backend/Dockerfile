# 后端镜像：FastAPI + DeepAgent + MCP + RAG
# 构建上下文必须是项目根目录：
#   docker build -f backend/Dockerfile -t scholarship-backend .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# unstructured 解析 PDF/DOCX 所需的系统库：
#   libmagic1   -> 文件类型识别（magic）
#   poppler-utils -> PDF 解析（pdftoppm/pdftotext）
#   libglib2.0-0  -> unstructured 部分依赖
# 先切换 Debian 软件源为清华镜像（国内网络加速）
RUN sed -i -e 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' \
           -e 's|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
           /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
        poppler-utils \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先拷贝依赖清单，利用构建缓存（国内网络使用清华 PyPI 镜像加速）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /app/requirements.txt

# 拷贝后端源码（config.py 通过 parents[3] 定位项目根 /app）
COPY backend /app/backend
COPY mcp_servers /app/mcp_servers

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
