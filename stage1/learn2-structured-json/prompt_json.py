import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


stage_dir = Path(__file__).resolve().parents[1]
load_dotenv(stage_dir / ".env")

base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "gpt-5.5")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url if base_url else None,
)

print("Prompt JSON Extractor")
print("请输入一句包含事件信息的话，模型会按提示词要求输出 JSON。")

user_input = input("\nText: ").strip()

response = client.responses.create(
    model=model,
    input=[
        {
            "role": "developer",
            "content": """
你是一个信息抽取助手。请从用户输入中抽取事件信息。

你必须只输出 JSON，不要输出 Markdown，不要输出解释文字。

JSON 格式必须是：

{
  "title": "事件标题",
  "date": "日期或时间描述，无法判断则为 null",
  "participants": ["参与者1", "参与者2"],
  "location": "地点，无法判断则为 null",
  "summary": "一句话摘要"
}

要求：
1. 不要编造用户没有提到的信息。
2. 如果日期、地点无法判断，对应字段用 null。
3. participants 必须是数组。
4. 输出必须是合法 JSON。
""",
        },
        {
            "role": "user",
            "content": user_input,
        },
    ],
)

print("\nJSON text:")
print(response.output_text)
