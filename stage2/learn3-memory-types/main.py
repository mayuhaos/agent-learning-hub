import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Learn 3 的目标：
# 区分三种“记忆”到底存在哪里、什么时候生效、什么时候会丢失。
#
# 这一节故意不引入 Qdrant 和 embedding，避免把“记忆类型”讲成“向量检索”。
# 我们只用：
# 1. Python 列表：模拟短期上下文
# 2. SQLite 表：保存会话记忆
# 3. SQLite 表：保存长期记忆
#
# 核心观念：
# 模型本身不会自动永久记住这些内容。
# 程序需要把记忆保存起来，并在下一次请求模型时重新放进上下文。

DEFAULT_SESSION_ID = "session-a"
DEFAULT_USER_ID = "demo-user"
SHORT_TERM_LIMIT = 6
LONG_TERM_LIMIT = 8
SESSION_MEMORY_LIMIT = 8


def load_config() -> dict[str, str | None]:
    """读取 Stage 2 共享的模型配置。"""
    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.5"),
    }


def init_database() -> sqlite3.Connection:
    """初始化本节专用 SQLite 数据库。

    数据库文件放在 runtime_data/ 目录下，并通过 .gitignore 忽略。
    这样课堂演示时产生的数据不会被误提交到仓库。
    """
    lesson_dir = Path(__file__).resolve().parent
    data_dir = lesson_dir / "runtime_data"
    data_dir.mkdir(exist_ok=True)

    connection = sqlite3.connect(data_dir / "memory_demo.db")
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS session_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS long_term_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    return connection


def add_session_memory(connection: sqlite3.Connection, session_id: str, content: str) -> None:
    """写入当前 session 的会话记忆。"""
    connection.execute(
        "INSERT INTO session_memories (session_id, content) VALUES (?, ?)",
        (session_id, content),
    )
    connection.commit()


def get_session_memories(connection: sqlite3.Connection, session_id: str) -> list[str]:
    """只读取当前 session_id 对应的会话记忆。"""
    rows = connection.execute(
        """
        SELECT content
        FROM session_memories
        WHERE session_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (session_id, SESSION_MEMORY_LIMIT),
    ).fetchall()
    return [row["content"] for row in rows]


def add_long_term_memory(connection: sqlite3.Connection, user_id: str, content: str) -> None:
    """写入长期记忆。

    长期记忆按 user_id 区分，而不是按 session_id 区分。
    所以同一个用户切换 session 后，仍然能看到这些长期事实或偏好。
    """
    connection.execute(
        "INSERT INTO long_term_memories (user_id, content) VALUES (?, ?)",
        (user_id, content),
    )
    connection.commit()


def get_long_term_memories(connection: sqlite3.Connection, user_id: str) -> list[str]:
    """读取当前用户的长期记忆。"""
    rows = connection.execute(
        """
        SELECT content
        FROM long_term_memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, LONG_TERM_LIMIT),
    ).fetchall()
    return [row["content"] for row in rows]


def format_list(title: str, items: list[str]) -> str:
    """把记忆列表整理成 prompt 中容易阅读的文本。"""
    if not items:
        return f"{title}：无"

    lines = [f"{title}："]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def build_memory_context(
    connection: sqlite3.Connection,
    session_id: str,
    user_id: str,
    recent_messages: list[dict[str, str]],
) -> str:
    """组装三类记忆，准备放进本轮模型请求。

    这里是本节最重要的一行逻辑：
    记忆只有被程序读取出来，并放进模型输入，模型才可能使用它。
    """
    short_term = [
        f"{message['role']}: {message['content']}"
        for message in recent_messages[-SHORT_TERM_LIMIT:]
    ]
    session_memories = get_session_memories(connection, session_id)
    long_term_memories = get_long_term_memories(connection, user_id)

    return "\n\n".join(
        [
            f"当前 session_id：{session_id}",
            f"当前 user_id：{user_id}",
            format_list("短期上下文 recent_messages", short_term),
            format_list("当前会话记忆 SQLite session_memories", session_memories),
            format_list("长期记忆 SQLite long_term_memories", long_term_memories),
        ]
    )


def chat_once(
    client: OpenAI,
    model: str,
    connection: sqlite3.Connection,
    session_id: str,
    user_id: str,
    recent_messages: list[dict[str, str]],
) -> None:
    """执行一轮聊天，并把这轮对话追加到短期上下文。"""
    user_text = input("User: ").strip()
    if not user_text:
        print("输入不能为空。")
        return

    memory_context = build_memory_context(connection, session_id, user_id, recent_messages)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": (
                    "你是一个教学用中文助手。"
                    "你会根据程序提供的短期上下文、会话记忆和长期记忆回答。"
                    "如果某类记忆里没有信息，请明确说当前记忆不足，不要假装知道。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"下面是程序管理的记忆：\n{memory_context}\n\n"
                    f"用户本轮问题：\n{user_text}"
                ),
            },
        ],
    )

    answer = response.output_text
    print("\nAssistant:")
    print(answer)

    recent_messages.append({"role": "user", "content": user_text})
    recent_messages.append({"role": "assistant", "content": answer})
    del recent_messages[:-SHORT_TERM_LIMIT]


def show_memory_state(
    connection: sqlite3.Connection,
    session_id: str,
    user_id: str,
    recent_messages: list[dict[str, str]],
) -> None:
    """打印三类记忆当前状态，方便录视频时直接观察差异。"""
    print("\n========== 当前记忆状态 ==========")
    print(f"session_id: {session_id}")
    print(f"user_id: {user_id}")
    print("\n[短期上下文：Python 内存 recent_messages]")
    if recent_messages:
        for message in recent_messages:
            print(f"- {message['role']}: {message['content'][:120]}")
    else:
        print("- 无")

    print("\n[会话记忆：SQLite session_memories，只属于当前 session]")
    session_memories = get_session_memories(connection, session_id)
    if session_memories:
        for memory in session_memories:
            print(f"- {memory}")
    else:
        print("- 无")

    print("\n[长期记忆：SQLite long_term_memories，属于当前 user，跨 session 可见]")
    long_term_memories = get_long_term_memories(connection, user_id)
    if long_term_memories:
        for memory in long_term_memories:
            print(f"- {memory}")
    else:
        print("- 无")
    print("==================================\n")


def print_menu(session_id: str, user_id: str) -> None:
    print("\nStage 2 Learn 3: 短期上下文、会话记忆、长期记忆")
    print(f"当前 session_id = {session_id}，user_id = {user_id}")
    print("1. chat：带着三类记忆问模型")
    print("2. 添加会话记忆：只属于当前 session")
    print("3. 添加长期记忆：属于当前 user，跨 session 可见")
    print("4. 查看三类记忆状态")
    print("5. 清空短期上下文")
    print("6. 切换 session")
    print("0. 退出")


def main() -> None:
    config = load_config()
    client = OpenAI(
        api_key=config["openai_api_key"],
        base_url=config["openai_base_url"] or None,
    )
    connection = init_database()

    current_session_id = DEFAULT_SESSION_ID
    current_user_id = DEFAULT_USER_ID
    recent_messages: list[dict[str, str]] = []

    while True:
        print_menu(current_session_id, current_user_id)
        choice = input("请选择: ").strip()

        if choice == "1":
            chat_once(
                client=client,
                model=str(config["openai_model"]),
                connection=connection,
                session_id=current_session_id,
                user_id=current_user_id,
                recent_messages=recent_messages,
            )
        elif choice == "2":
            content = input("请输入要保存到当前会话的记忆: ").strip()
            if content:
                add_session_memory(connection, current_session_id, content)
                print("已写入会话记忆。")
            else:
                print("内容不能为空。")
        elif choice == "3":
            content = input("请输入要保存为长期记忆的事实或偏好: ").strip()
            if content:
                add_long_term_memory(connection, current_user_id, content)
                print("已写入长期记忆。")
            else:
                print("内容不能为空。")
        elif choice == "4":
            show_memory_state(connection, current_session_id, current_user_id, recent_messages)
        elif choice == "5":
            recent_messages.clear()
            print("已清空短期上下文。SQLite 中的会话记忆和长期记忆不会受影响。")
        elif choice == "6":
            new_session_id = input("请输入新的 session_id，例如 session-b: ").strip()
            if new_session_id:
                current_session_id = new_session_id
                recent_messages.clear()
                print("已切换 session，并清空短期上下文。")
            else:
                print("session_id 不能为空。")
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("未知选项，请重新输入。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n程序运行失败：")
        print(exc)
