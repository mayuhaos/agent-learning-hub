<div align="center">

# Agent Learning Hub

从零开始实践 Agent 开发，把每一节学习内容沉淀成可运行代码。

<p>
  <a href="https://github.com/mayuhaos/agent-learning-hub/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  </a>
  <a href="https://datawhalechina.github.io/Agent-Learning-Hub/">
    <img src="https://img.shields.io/badge/route-Datawhale%20Agent%20Learning%20Hub-orange.svg" alt="Learning Route">
  </a>
  <a href="https://www.bilibili.com/video/BV1ymjN6YEz8">
    <img src="https://img.shields.io/badge/video-Bilibili-00A1D6.svg" alt="Bilibili">
  </a>
  <a href="https://yuhao.bbroot.com">
    <img src="https://img.shields.io/badge/blog-yuhao.bbroot.com-black.svg" alt="Blog">
  </a>
</p>

<p>
  <a href="#学习路线">学习路线</a> ·
  <a href="#内容索引">内容索引</a> ·
  <a href="#目录约定">目录约定</a> ·
  <a href="#star-history">Star History</a>
</p>

</div>

---

<table>
  <tr>
    <td width="50%">
      <strong>学习路线</strong><br>
      跟随 Datawhale 的 <a href="https://datawhalechina.github.io/Agent-Learning-Hub/">Agent Learning Hub</a> 持续推进。
    </td>
    <td width="50%">
      <strong>更新方式</strong><br>
      每讲一节，如果有代码，就把对应示例整理到这个仓库。
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>项目目标</strong><br>
      不只做笔记，而是把知识点变成能运行、能复盘、能继续扩展的小项目。
    </td>
    <td width="50%">
      <strong>个人博客</strong><br>
      更多文章和学习记录会同步到 <a href="https://yuhao.bbroot.com">yuhao.bbroot.com</a>。
    </td>
  </tr>
</table>

---

## 学习路线

本仓库会跟随 Agent Learning Hub 的阶段推进：

| 阶段 | 主题 | 仓库进度 | 视频地址 |
| --- | --- | --- | --- |
| Stage 0 | 理解 Agent 是什么 | 已完成 | [Bilibili](https://www.bilibili.com/video/BV1VwJn6wEsi) |
| Stage 1 | 构建最小 Agent Loop | 已完成 | [Bilibili](https://www.bilibili.com/video/BV1ymjN6YEz8) |
| Stage 2 | 学习工具调用、RAG 与记忆 | 待更新 | 待更新 |
| Stage 3 | 深入研究一个现代 Agent Harness | 待更新 | 待更新 |
| Stage 4 | 多 Agent 是协调问题，不是魔法 | 待更新 | 待更新 |
| Stage 5 | 学习 Skills、协议与能力打包 | 待更新 | 待更新 |
| Stage 6 | 浏览器与 Computer-Use Agent | 待更新 | 待更新 |
| Stage 7 | 评测、可观测性与安全 | 待更新 | 待更新 |
| Stage 8 | 交付一个真正的 Agent | 待更新 | 待更新 |

## 内容索引

```text
agent-learning-hub/
└── stage1/
    ├── README.md
    ├── requirements.txt
    ├── .env.example
    ├── learn1-llm-chat/
    │   ├── main.py
    │   └── README.md
    ├── learn2-structured-json/
    │   ├── main.py
    │   ├── prompt_json.py
    │   └── README.md
    ├── learn3-tool-function/
    │   ├── main.py
    │   ├── sample_note.txt
    │   └── README.md
    ├── learn4-tool-call-parse/
    │   ├── main.py
    │   └── README.md
    ├── learn5-execute-tool/
    │   ├── main.py
    │   ├── sample_note.txt
    │   └── README.md
    └── learn6-agent-loop-controls/
        ├── main.py
        ├── sample_note.txt
        └── README.md
```

具体运行方式见每个 `learn` 目录下的 `README.md`。

## 目录约定

后续课程会按下面的方式组织：

```text
stage1/
  requirements.txt
  .env.example
  learn1-llm-chat/
  learn2-structured-json/
  learn3-tool-function/
  learn4-tool-call-parse/
  learn5-execute-tool/
  learn6-agent-loop-controls/
stage2/
  requirements.txt
  .env.example
  learn1-tool-calling/
  learn2-rag/
  learn3-memory/
```

命名规则：

1. `stageN` 表示学习阶段
2. `learnN-topic` 表示该阶段的第 N 节
3. 每个 `stageN` 目录维护本阶段共享的 `.env.example` 和 `requirements.txt`
4. 每一节尽量包含独立的 `README.md`
5. 有代码的章节尽量保证可以单独运行

## 安全提醒

不要把真实 API Key 提交到 GitHub。

本仓库已经通过 `.gitignore` 忽略 `.env` 文件。公开仓库里只保留 `.env.example`。

## 相关链接

- 学习路线：[Datawhale Agent Learning Hub](https://datawhalechina.github.io/Agent-Learning-Hub/)
- 我的博客：[yuhao.bbroot.com](https://yuhao.bbroot.com)
- OpenAI API 文档：[OpenAI Developers](https://developers.openai.com/api/docs)

## Star History

<div align="center">
  <a href="https://www.star-history.com/#mayuhaos/agent-learning-hub&Date">
    <img src="https://api.star-history.com/svg?repos=mayuhaos/agent-learning-hub&type=Date" alt="Star History Chart">
  </a>
</div>
