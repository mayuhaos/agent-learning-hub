import os
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv


# 当前文件在 stage1/learn1-llm-chat/main.py。
# parents[1] 表示向上两级，也就是 stage1 目录。
# 这样每一节代码都可以共享 stage1/.env，而不用在每个 learn 目录放一份配置。
stage_dir = Path(__file__).resolve().parents[1]
load_dotenv(stage_dir / ".env")

# 从 .env 读取模型配置。
# OPENAI_BASE_URL 是可选的：如果使用中转站，就填写它；如果直接使用官方 API，可以不填。
base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "gpt-5.5")

# 创建 OpenAI 客户端。
# api_key 来自环境变量 OPENAI_API_KEY。
# base_url 如果为空就传 None，让 SDK 使用默认官方地址。
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url if base_url else None,
)

# messages 保存完整对话历史。
# developer 消息相当于给模型的“行为说明”，这里要求它做一个简洁可靠的中文助手。
# 后面每轮用户输入和模型回复都会 append 到这个列表里，所以模型能看到上下文。
messages = [
    {
        "role": "developer",
        "content": "你是一个简洁、可靠的中文助手。",
    }
]

print("LLM Chat started. Type 'exit' to quit.")

# 一个最小的命令行多轮聊天循环。
# 每次循环做四件事：
# 1. 读取用户输入
# 2. 把用户输入加入 messages
# 3. 调用模型生成回复
# 4. 把模型回复也加入 messages，供下一轮继续使用
while True:
    user_input = input("\nYou: ").strip()

    # 允许用户用常见退出词结束程序。
    if user_input.lower() in ["exit", "quit", "退出"]:
        break

    # 把用户这一轮说的话加入对话历史。
    messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # 调用 Responses API。
    # input 传入完整 messages，就能实现最基础的“多轮对话”。
    response = client.responses.create(
        model=model,
        input=messages,
    )

    # output_text 是 SDK 提供的便捷字段，用来直接拿到模型最终文本。
    assistant_text = response.output_text

    print(f"\nAssistant: {assistant_text}")

    # 把助手回复也保存到对话历史。
    # 如果不保存，下一轮模型就不知道自己上一轮说过什么。
    messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
        }
    )
