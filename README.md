# Agent Learning Hub

这是我的 Agent 学习代码仓库，会按照 Datawhale 的 [Agent Learning Hub](https://datawhalechina.github.io/Agent-Learning-Hub/) 路线持续更新。

每讲一节，如果有代码，我都会把对应示例放到这里。目标不是只做笔记，而是把每个知识点变成一个能运行、能复盘、能继续扩展的小项目。

我的个人博客：[yuhao.bbroot.com](https://yuhao.bbroot.com)

## 学习路线

本仓库会跟随 Agent Learning Hub 的阶段推进：

| 阶段 | 主题 | 仓库进度 | 视频地址 |
| --- | --- | --- | --- |
| Stage 0 | 理解 Agent 是什么 | 已完成 | [Bilibili](https://www.bilibili.com/video/BV1VwJn6wEsi) |
| Stage 1 | 构建最小 Agent Loop | 进行中 | 待更新 |
| Stage 2 | 学习工具调用、RAG 与记忆 | 待更新 | 待更新 |
| Stage 3 | 深入研究一个现代 Agent Harness | 待更新 | 待更新 |
| Stage 4 | 多 Agent 是协调问题，不是魔法 | 待更新 | 待更新 |
| Stage 5 | 学习 Skills、协议与能力打包 | 待更新 | 待更新 |
| Stage 6 | 浏览器与 Computer-Use Agent | 待更新 | 待更新 |
| Stage 7 | 评测、可观测性与安全 | 待更新 | 待更新 |
| Stage 8 | 交付一个真正的 Agent | 待更新 | 待更新 |

## 当前内容

```text
agent-learning-hub/
└── stage1/
    └── learn1-llm-chat/
        ├── main.py
        ├── requirements.txt
        ├── .env.example
        └── README.md
```

### Stage 1 / Learn 1

主题：用一个 LLM API 完成普通多轮对话。

这一节会实现一个命令行聊天程序：

1. 读取用户输入
2. 调用 LLM API
3. 打印模型回复
4. 保存历史消息
5. 在下一轮请求中带上上下文

代码位置：[stage1/learn1-llm-chat](./stage1/learn1-llm-chat)

## 快速开始

进入当前课程目录：

```bash
cd stage1/learn1-llm-chat
```

安装依赖：

```bash
py -3 -m pip install -r requirements.txt
```

如果你的系统已经配置好了 `pip`，也可以使用：

```bash
pip install -r requirements.txt
```

创建 `.env` 文件：

```bash
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://你的中转站地址/v1
OPENAI_MODEL=你的模型名
```

如果使用官方 OpenAI API，可以不写 `OPENAI_BASE_URL`。

运行：

```bash
py -3 main.py
```

或者：

```bash
python main.py
```

## 目录约定

后续课程会按下面的方式组织：

```text
stage1/
  learn1-llm-chat/
  learn2-structured-json/
  learn3-tool-function/
stage2/
  learn1-tool-calling/
  learn2-rag/
  learn3-memory/
```

命名规则：

1. `stageN` 表示学习阶段
2. `learnN-topic` 表示该阶段的第 N 节
3. 每一节尽量包含独立的 `README.md`
4. 有代码的章节尽量保证可以单独运行

## 安全提醒

不要把真实 API Key 提交到 GitHub。

本仓库已经通过 `.gitignore` 忽略 `.env` 文件。公开仓库里只保留 `.env.example`。

## 相关链接

- 学习路线：[Datawhale Agent Learning Hub](https://datawhalechina.github.io/Agent-Learning-Hub/)
- 我的博客：[yuhao.bbroot.com](https://yuhao.bbroot.com)
- OpenAI API 文档：[OpenAI Developers](https://developers.openai.com/api/docs)
