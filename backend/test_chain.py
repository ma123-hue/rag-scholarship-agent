 # 异步IO标准库，用于运行异步RAG流式接口
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.chat import ChatSession
from app.models.user import User
from app.core.security import get_password_hash
from app.services.rag_chain import get_rag_chain


async def main() -> None:
    # 读取系统配置文件
    settings = get_settings()
    # 不打印 API Key，只展示线上服务地址和模型名。
    print(f"Online API: {settings.llm_api_base_url}")
    print(f"Chat model: {settings.llm_chat_model}")
    print(f"Embedding model: {settings.embedding_model}")

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == "cli_test_user")).scalar_one_or_none()
        if user is None:
            user = User(username="cli_test_user", password_hash=get_password_hash("cli-test-password"))
            db.add(user)
            db.commit()
            db.refresh(user)

        session = ChatSession(user_id=user.id, session_title="CLI Test Session")
        db.add(session)
        db.commit()
        db.refresh(session)

        prompt = (
            "我是计算机专业学生，绩点3.8/4.0，专业排名前5%，家庭年收入2万元，"
            "有贫困证明，获校级三好学生。请评估我可能符合哪些奖助学金。"
        )

        print("\nUser:", prompt)
        print("Assistant:")
        async for chunk in get_rag_chain().astream_answer(db, session.id, prompt):
            print(chunk, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
