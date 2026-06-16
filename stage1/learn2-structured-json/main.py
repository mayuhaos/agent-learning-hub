import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


class EventInfo(BaseModel):
    title: str = Field(description="事件标题")
    date: str | None = Field(description="日期或时间描述，无法判断时为 null")
    participants: list[str] = Field(description="事件参与者列表")
    location: str | None = Field(description="地点，无法判断时为 null")
    summary: str = Field(description="一句话摘要")


stage_dir = Path(__file__).resolve().parents[1]
load_dotenv(stage_dir / ".env")

base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "gpt-5.5")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url if base_url else None,
)

print("Structured JSON Extractor")
print("请输入一句包含事件信息的话，模型会把它解析成固定 JSON。")

user_input = input("\nText: ").strip()

response = client.responses.parse(
    model=model,
    input=[
        {
            "role": "developer",
            "content": "你是一个信息抽取助手。请只根据用户输入抽取事件信息，不要编造缺失内容。",
        },
        {
            "role": "user",
            "content": user_input,
        },
    ],
    text_format=EventInfo,
)

event = response.output_parsed

print("\nParsed object:")
print(event)

print("\nJSON:")
print(event.model_dump_json(indent=2, ensure_ascii=False))
