import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


# Pydantic 模型就是本节的“结构定义”。
# 我们先在代码里定义清楚 JSON 应该长什么样，再让模型按这个结构返回。
class EventInfo(BaseModel):
    # Field(description=...) 会进入结构化输出的 schema，帮助模型理解每个字段的含义。
    title: str = Field(description="事件标题")
    # str | None 表示这个字段可以是字符串，也可以是 None。
    # 序列化成 JSON 时，None 会变成 null。
    date: str | None = Field(description="日期或时间描述，无法判断时为 null")
    # list[str] 表示 participants 必须是字符串数组，而不是一段逗号分隔的文本。
    participants: list[str] = Field(description="事件参与者列表")
    location: str | None = Field(description="地点，无法判断时为 null")
    summary: str = Field(description="一句话摘要")


# 所有 Stage 1 示例共享 stage1/.env。
stage_dir = Path(__file__).resolve().parents[1]
load_dotenv(stage_dir / ".env")

# 从环境变量读取模型配置，避免把 API Key 写进代码。
base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "gpt-5.5")

# 初始化 OpenAI 客户端。
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=base_url if base_url else None,
)

print("Structured JSON Extractor")
print("请输入一句包含事件信息的话，模型会把它解析成固定 JSON。")

user_input = input("\nText: ").strip()

# responses.parse 是 SDK 提供的结构化输出便捷方法。
# text_format=EventInfo 表示：让模型输出符合 EventInfo 的结构，
# 并且 SDK 会把结果直接解析成 EventInfo 对象。
response = client.responses.parse(
    model=model,
    input=[
        {
            # developer 消息告诉模型任务边界：只做信息抽取，不要编造缺失内容。
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

# output_parsed 是已经解析好的 Pydantic 对象。
# 这和“拿到一段 JSON 字符串再自己解析”不同，SDK 已经帮我们完成了结构校验和对象转换。
event = response.output_parsed

print("\nParsed object:")
print(event)

print("\nJSON:")
# model_dump_json 把 Pydantic 对象重新序列化成标准 JSON。
# ensure_ascii=False 可以让中文直接显示，而不是变成 \u4e2d\u6587 这种转义形式。
print(event.model_dump_json(indent=2, ensure_ascii=False))
