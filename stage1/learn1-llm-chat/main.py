import os

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "gpt-5.5")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url if base_url else None,
)

messages = [
    {
        "role": "developer",
        "content": "你是一个简洁、可靠的中文助手。",
    }
]

print("LLM Chat started. Type 'exit' to quit.")

while True:
    user_input = input("\nYou: ").strip()

    if user_input.lower() in ["exit", "quit", "退出"]:
        break

    messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    response = client.responses.create(
        model=model,
        input=messages,
    )

    assistant_text = response.output_text

    print(f"\nAssistant: {assistant_text}")

    messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
        }
    )
