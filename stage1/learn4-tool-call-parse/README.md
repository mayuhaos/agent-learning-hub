# Learn 4: 解析模型的 Tool Call / Function Call

这是 Stage 1 的第四个代码示例。

## 这个示例做了什么

这一节学习：模型如何表达“我想调用哪个工具，以及参数是什么”。

程序会把三个工具的说明传给模型：

- `search(query: str)`：查询已有知识。
- `calculator(expression: str)`：计算数学表达式。
- `read_file(path: str)`：读取文件。

注意，这里传给模型的是工具 schema，不是真正执行的 Python 函数。schema 的作用是告诉模型：现在有哪些工具、每个工具叫什么、每个工具需要什么参数。

本节只解析模型返回的 tool call / function call，不会根据 `name` 调用本地函数，也不会把工具结果发回模型。执行工具是下一节的内容。

工具 schema 的写法参考 OpenAI 官方文档：[Function Calling](https://developers.openai.com/api/docs/guides/function-calling)。

## 准备环境

下面的命令都在 `stage1` 目录下执行。

安装依赖：

```bash
pip install -r requirements.txt
```

Windows 如果没有配置 `pip` 命令，可以使用：

```bash
py -3 -m pip install -r requirements.txt
```

创建 `.env` 文件：

```bash
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://你的中转站地址/v1
OPENAI_MODEL=你的模型名
```

如果你直接使用官方 OpenAI API，可以删除 `OPENAI_BASE_URL` 这一行。

## 运行

```bash
python learn4-tool-call-parse/main.py
```

Windows 如果没有配置 `python` 命令，可以使用：

```bash
py -3 learn4-tool-call-parse/main.py
```

可以输入这些例子：

```text
帮我查一下 Agent 是什么
计算 1 + 2 * 3
读取 sample_note.txt
你好，介绍一下你自己
```

前三个输入通常会让模型返回 function call。最后一个输入可能只返回普通文本，因为它不一定需要工具。

## 代码核心

一个 function call 里最重要的是这些字段：

- `type`：输出项类型，工具调用通常是 `function_call`
- `call_id`：这次工具调用的唯一 ID
- `name`：模型想调用的工具名，例如 `search`
- `arguments`：模型给这个工具准备的参数，通常是 JSON 字符串

程序会打印两份参数：

1. `arguments(raw)`：模型返回的原始 JSON 字符串
2. `arguments(dict)`：程序用 `json.loads(...)` 解析后的 Python 字典

比如用户输入：

```text
计算 1 + 2 * 3
```

模型可能会返回类似：

```text
name: calculator
arguments(raw): {"expression":"1 + 2 * 3"}
arguments(dict):
{
  "expression": "1 + 2 * 3"
}
```

这说明模型还没有真的完成计算。它只是表达了一个调用意图：想调用 `calculator`，并把 `1 + 2 * 3` 作为参数传进去。

## 课堂讲解重点

这一节只讲解析，不讲执行。

可以把这一节总结成一句话：

> Tool call / function call = 模型用结构化方式告诉程序：我要调用哪个工具，以及参数是什么。

下一节会继续学习：程序如何根据 `name` 找到真正的函数、执行它，并把工具结果喂回模型。
