# Learn 2: 让模型输出结构化 JSON

这是 Stage 1 的第二个代码示例。

## 这个示例做了什么

这个程序会读取一句自然语言，并让模型把里面的事件信息解析成固定结构的 JSON。

这一节的重点不是在提示词里写“请返回 JSON”，而是用结构化输出约束模型的返回格式。程序会用 Pydantic 定义一个 `EventInfo` 结构，再通过 `client.responses.parse(...)` 让 SDK 直接把模型输出解析成 Python 对象。

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

也可以先复制 `.env.example`，再把里面的值替换成自己的 API Key、中转站地址和模型名。

如果你直接使用官方 OpenAI API，可以删除 `OPENAI_BASE_URL` 这一行，SDK 会使用默认地址。

## 运行

结构化输出版本：

```bash
python learn2-structured-json/main.py
```

Windows 如果没有配置 `python` 命令，可以使用：

```bash
py -3 learn2-structured-json/main.py
```

也可以运行提示词约束版本，对比两种做法的区别：

```bash
python learn2-structured-json/prompt_json.py
```

Windows 可以使用：

```bash
py -3 learn2-structured-json/prompt_json.py
```

可以输入类似下面的话：

```text
明天下午三点，张三和李四在上海办公室讨论 Agent 课程第二节。
```

也可以试试这些不同写法：

```text
下周一上午十点，产品组在 3 号会议室开需求评审会，王敏、赵雷和陈晨都会参加。
今晚八点我和小李线上复盘今天的 RAG 学习内容。
6 月 20 日，Datawhale 社区会发布新的 Agent 学习资料。
周五下午，刘老师要讲结构化输出这一节。
后天下午两点半，运营同学在杭州办公室讨论活动排期。
```

程序会输出两部分：

1. `Parsed object`：SDK 解析后的 Pydantic 对象
2. `JSON`：把对象序列化后的标准 JSON

如果运行的是 `prompt_json.py`，程序会直接打印模型返回的 JSON 文本。

## 代码核心

`EventInfo` 是这一节的结构定义：

- `title`：事件标题
- `date`：日期或时间描述，无法判断则为 `null`
- `participants`：参与者列表
- `location`：地点，无法判断则为 `null`
- `summary`：一句话摘要

`client.responses.parse(...)` 会根据 `EventInfo` 约束模型输出，并把结果放到 `response.output_parsed` 里。

所以，结构化 JSON 的关键不是让模型“尽量像 JSON”，而是先在代码里定义清楚结构，再让模型按这个结构返回。

`prompt_json.py` 是对照版本。它没有使用 Pydantic，也没有使用 `responses.parse(...)`，而是在提示词里要求模型只输出 JSON。这个方式更直观，但本质上还是依赖模型遵守提示词。

## 课堂讲解重点

这一节只讲结构化输出，不讲 tool calling，也不讲复杂 agent loop。

可以把这节课总结成一句话：

> 结构化输出 = 先定义数据结构，再让模型按结构返回可解析结果。
