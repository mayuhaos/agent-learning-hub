import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# 这里定义的是给模型看的“工具说明书”，不是 Python 函数本身。
# 格式依据 OpenAI Function Calling 文档：
# https://developers.openai.com/api/docs/guides/function-calling
# - type/name/description 用来告诉模型有哪些工具、什么时候用。
# - parameters 使用 JSON Schema，告诉模型调用工具时应该生成哪些参数。
# - strict=True 会要求模型更严格地按照 parameters 生成 arguments。
TOOLS = [
    {
        # 这是一个 function tool。后续模型返回的 tool call 里 type 会是 function_call。
        "type": "function",
        # 工具名。模型如果选择这个工具，返回结果里的 name 就会是 search。
        "name": "search",
        # 给模型看的工具说明，帮助模型判断什么时候该调用它。
        "description": "查询已有知识，适合回答 Agent、工具函数、课程概念等问题。",
        "strict": True,
        # parameters 是这个工具的参数 schema。这里表示 search 需要一个字符串 query。
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要查询的关键词或问题。",
                }
            },
            "required": ["query"],
            # strict=True 时，object schema 需要关闭额外参数，避免模型编造未知字段。
            "additionalProperties": False,
        },
    },
    {
        # calculator 的结构和 search 一样，只是工具名、说明、参数名不同。
        # 模型看到 expression 字段后，会把用户要计算的表达式放进 arguments。
        "type": "function",
        "name": "calculator",
        "description": "计算简单数学表达式，适合处理精确算术。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，例如 1 + 2 * 3。",
                }
            },
            "required": ["expression"],
            # 不允许出现 expression 之外的参数。
            "additionalProperties": False,
        },
    },
    {
        # read_file 演示“读取外部内容”这类工具。
        # 本节只解析模型想读哪个 path，不会真的读取文件。
        "type": "function",
        "name": "read_file",
        "description": "读取指定文件内容，适合用户明确要求查看某个文件时使用。",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径，例如 sample_note.txt。",
                }
            },
            "required": ["path"],
            # 不允许出现 path 之外的参数。
            "additionalProperties": False,
        },
    },
]


def parse_arguments(arguments: str) -> dict:
    # OpenAI 返回的 arguments 是 JSON 字符串，不是 Python dict。
    # 例如："{\"expression\":\"1 + 2 * 3\"}"
    # 所以要用 json.loads 把它解析成 Python 字典，后续才方便读取参数。
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as exc:
        # 正常情况下 strict schema 会让 arguments 是合法 JSON。
        # 这里保留错误分支，是为了教学时能看到“解析失败”应该如何暴露出来。
        return {"parse_error": f"参数不是合法 JSON：{exc}", "raw": arguments}


def print_function_call(item) -> None:
    # item 是 response.output 里的一个 function_call 输出项。
    # 这一节只打印它，不根据 name 去执行真正的 Python 函数。
    print("\nParsed tool/function call:")
    print(f"type: {item.type}")
    # call_id 是这次工具调用的唯一编号。
    # 下一节把工具结果回传模型时，会用它来对应“这是哪一次调用的结果”。
    print(f"call_id: {item.call_id}")
    # name 是模型选择的工具名，例如 search、calculator、read_file。
    print(f"name: {item.name}")
    # arguments 是模型生成的原始 JSON 字符串。
    print(f"arguments(raw): {item.arguments}")
    print("arguments(dict):")
    # 为了更容易阅读，再打印解析后的 Python dict。
    print(json.dumps(parse_arguments(item.arguments), indent=2, ensure_ascii=False))


def print_text_output(item) -> None:
    # 如果模型没有选择工具，它可能返回普通 message。
    # 本函数只负责把普通文本输出打印出来。
    if item.type != "message":
        return

    for content in item.content:
        if content.type == "output_text":
            print("\nModel text:")
            print(content.text)


def main() -> None:
    # 仍然使用 stage1/.env 里的共享配置。
    stage_dir = Path(__file__).resolve().parents[1]
    load_dotenv(stage_dir / ".env")

    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=base_url if base_url else None,
    )

    print("Tool Call Parser Demo")
    print("请输入一句话，模型会判断是否需要发出 tool/function call。")
    print("本节只解析调用意图，不执行工具，也不把工具结果回传模型。")

    user_input = input("\nUser: ").strip()

    # 把 tools=TOOLS 传给模型后，模型就知道自己有哪些可选工具。
    # 但这里不会执行工具。模型最多只会返回 function_call 这种“调用意图”。
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "developer",
                "content": (
                    "你是一个工具调用解析示例助手。"
                    "如果用户请求适合某个工具，请返回对应的 function call。"
                    "如果不需要工具，请直接用普通文本回答。"
                    "注意：程序只会解析 tool/function call，不会执行工具。"
                ),
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        tools=TOOLS,
    )

    # response.output 是一个列表，里面可能包含普通文本 message，也可能包含 function_call。
    # 本节的核心就是遍历这个列表，找出并解析 function_call。
    found_call = False
    for item in response.output:
        if item.type == "function_call":
            found_call = True
            print_function_call(item)
        else:
            print_text_output(item)

    if not found_call:
        # 没有 function_call 不代表出错，只是模型判断这次不需要工具。
        print("\nNo tool/function call parsed.")
        print("本次模型没有选择调用工具。")


if __name__ == "__main__":
    main()
