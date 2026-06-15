# Learn 1: 用一个 LLM API 完成普通多轮对话

这是 Stage 1 的第一个代码示例。

## 这个示例做了什么

这个程序会在命令行里启动一个简单的聊天助手。用户每输入一句话，程序就调用一次 LLM API，并把模型回复打印出来。

它支持多轮对话，因为程序会把用户和助手的历史消息保存在 `messages` 列表里，并在下一次请求时一起发给模型。

## 准备环境

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

也可以先复制 `.env.example`，再把里面的值替换成自己的 API Key、中转站地址和模型名。

如果你直接使用官方 OpenAI API，可以删除 `OPENAI_BASE_URL` 这一行，SDK 会使用默认地址。

## 运行

```bash
python main.py
```

Windows 如果没有配置 `python` 命令，可以使用：

```bash
py -3 main.py
```

退出聊天：

```text
exit
```

或者：

```text
quit
```

也可以输入：

```text
退出
```

## 代码核心

`messages` 是聊天历史。

每一轮对话都会做四件事：

1. 把用户输入加入 `messages`
2. 调用 `client.responses.create(...)`
3. 从 `response.output_text` 取出模型回复
4. 把助手回复继续加入 `messages`

所以，多轮对话的关键不是模型自动记住了所有内容，而是程序每次请求时都把历史对话一起发给模型。

## 课堂讲解重点

这一节只讲普通多轮对话，不讲 tool calling，也不讲复杂 agent loop。

可以把这节课总结成一句话：

> 普通多轮对话 = 用户输入 + 聊天历史 + 模型回复 + 把回复继续存进历史。
