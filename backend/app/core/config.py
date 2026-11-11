from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_api_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_chat_model: str = "qwen-plus"
    llm_request_timeout: float = 60.0
    llm_max_retries: int = 1
    llm_max_output_tokens: int = 3000
    llm_enable_thinking: bool = False
    embedding_api_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v4"
    secret_key: str = "change-this-to-a-long-random-string"
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./app.db"
    chroma_persist_directory: str = "./chroma_db"
    policy_data_dir: str = "./data/policies"
    policy_search_index: str = "./data/policy_search_index.json"
    frontend_origin: str = "http://localhost:5173"
    jwt_algorithm: str = "HS256"
    chroma_collection_name: str = "policy_documents_online_v1"
    admin_username: str = "admin"
    admin_password: str = "admin123456"
    agent_max_steps: int = 12
    mcp_transport: str = "stdio"
    agent_checkpoint_db: str = "./agent_checkpoints.db"
    generated_reports_dir: str = "./generated_reports"

    @field_validator("frontend_origin", mode="before")
    @classmethod
    def strip_origin(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw_path = self.database_url[len(prefix) :]
            if raw_path.startswith("./"):
                return f"{prefix}{(ROOT_DIR / raw_path[2:]).as_posix()}"
        return self.database_url

    @property
    def resolved_chroma_dir(self) -> Path:
        return (ROOT_DIR / self.chroma_persist_directory.replace("./", "", 1)).resolve()

    @property
    def resolved_policy_dir(self) -> Path:
        return (ROOT_DIR / self.policy_data_dir.replace("./", "", 1)).resolve()

    @property
    def resolved_policy_search_index(self) -> Path:
        return (ROOT_DIR / self.policy_search_index.replace("./", "", 1)).resolve()

    @property
    def scholarship_mcp_script(self) -> Path:
        return (ROOT_DIR / "mcp_servers" / "scholarship_server.py").resolve()

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key

    def require_online_api_keys(self) -> None:
        if not self.llm_api_key or self.llm_api_key == "sk-your-api-key":
            raise RuntimeError("未配置 LLM_API_KEY，请在 .env 中填写线上模型 API Key")
        if not self.resolved_embedding_api_key:
            raise RuntimeError("未配置 EMBEDDING_API_KEY，且无法复用 LLM_API_KEY")

    @property
    def resolved_agent_checkpoint_db(self) -> Path:
        return (ROOT_DIR / self.agent_checkpoint_db.replace("./", "", 1)).resolve()

    @property
    def resolved_generated_reports_dir(self) -> Path:
        return (ROOT_DIR / self.generated_reports_dir.replace("./", "", 1)).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
