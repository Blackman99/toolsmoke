---
title: 工具调用为什么会悄悄失效，以及怎么一条命令查出来
description: llama.cpp、Ollama、vLLM 和各种中转站上，工具调用经常悄悄坏掉。本文讲清原因、智能体到底需要接口做到什么，以及一条命令的检测方法，附 llama.cpp 实测结果。
---

# 号称"兼容 OpenAI"，智能体却跑不起来

*2026 年 10 月 · [English](tool-calling-breaks-silently.md)*

你把智能体接到本地的模型接口上，先发一条普通对话，能回，于是就接着往下做。结果智能体不调工具了，或者在同一步来回打转，或者隔几次请求就报一个 500。日志里不会写"工具调用坏了"，最后背锅的往往是模型。

其实模型多半没问题。出问题的是模型和 HTTP 接口之间的那一层：聊天模板、工具调用解析器、推理内容解析器、拼接流式增量的代码，如果你用了中转站或网关，还要再加上它们。

## 三个 issue，同一个规律

下面这三个 issue 加起来有两百多条评论：

- **[ollama#11621](https://github.com/ollama/ollama/issues/11621)**：Qwen3-Coder 本身支持工具调用，但 Ollama 给它配的聊天模板里没有工具支持。客户端传了 `tools`，拿回来的却是一段普通回复。直到 Ollama v0.12.0 专门为 qwen3-coder 写了渲染器和解析器才修好。
- **[llama.cpp#15012](https://github.com/ggml-org/llama.cpp/issues/15012)**：Qwen3-Coder 用自己的一套 XML 格式（`<function=...><parameter=...>`）输出工具调用，而不是 `<tool_call>` 里包 JSON。服务端没有对应的解析器，调用就会以纯文本的形式落进 `content`，客户端看到的是一句话，而不是 `tool_calls`。
- **[vllm#22403](https://github.com/vllm-project/vllm/issues/22403)**：用 chat completions 接口跑 gpt-oss-120b，会随机返回 200、400（`Expected 2 output messages (reasoning and final), but got 7`）或 500。用智能体框架带工具调用的人会直接报错，还有人遇到流式输出中途断掉。问题出在服务端对这个模型的推理、工具和流式响应格式的处理上。

三个案例的共同点：模型权重没问题，普通对话也正常，坏掉的是智能体依赖的那份接口约定，而且坏在服务层。中转站和网关又多了一层转换（OpenAI 和 Anthropic 格式互转、字段改名、流被缓冲），同样的字段在这里也可能被丢掉或者改了形状。

更麻烦的是，故障表现离根因很远。框架反复重试一个永远不会成功的调用；把 `<tool_call>{...}` 这段文本当成最终答案；或者在拼了一半的流式参数上报 JSON 解析错误。等你看到调用栈的时候，最后才会怀疑到接口头上。

## "能跑智能体"到底指什么

能回对话的接口，不一定能跑智能体。智能体依赖的是下面这些具体行为：

| 智能体需要 | toolsmoke 探针 |
|---|---|
| 工具调用放在 `tool_calls` 里返回，`finish_reason` 为 `tool_calls`，`content` 里没有残留标记 | `tools.single`、`tools.clean_content` |
| 参数是合法 JSON 并且符合 schema | `tools.args_schema` |
| 并行调用，每个调用有独立的 id | `tools.parallel` |
| `tool_choice` 的 `none`、`required` 和指定工具真正生效 | `tools.choice_none`、`tools.choice_required`、`tools.choice_named` |
| 工具结果在下一轮能传到模型 | `tools.result_roundtrip`、`tools.multi_result` |
| 流式的工具调用增量能拼回同一个调用 | `stream.tools`、`stream.tools_parallel` |
| 遵守 `response_format`（`json_object` 和严格 `json_schema`） | `json.mode`、`json.schema` |
| 推理内容放在 `reasoning_content`，而不是以 `<think>` 混进答案 | `reasoning.field` |
| 错误请求返回干净的 4xx，而不是 500 或者悄悄返回 200 | `errors.*` |
| 可选：Anthropic Messages 接口（`/v1/messages`） | `anthropic.*` |

每个探针的细节见[探针说明](../probes.md)。

## 一条命令检测

[toolsmoke](https://github.com/Blackman99/toolsmoke) 会向你的接口发送 31 个小探针，提示词都很简单，用 `temperature: 0`，结果按确定的规则判断。每个探针输出 PASS、WARN 或 FAIL，同时给出首字延迟、每秒 token 数，以及一个可以直接用在 CI 里的退出码。只需要 Python 3.9+，没有任何依赖。

```bash
uvx --from git+https://github.com/Blackman99/toolsmoke toolsmoke \
    --base-url http://localhost:8080/v1 --model qwen --anthropic
```

手边没有模型的话，可以跑 `toolsmoke --demo broken` 看效果。它会启动一个内置的模拟服务器，把常见的故障都打开：

![toolsmoke --demo broken 和 --demo good 的运行效果](https://blackman99.github.io/toolsmoke/demo.gif)

## 实测：llama.cpp 加一个小号 Qwen

环境：`llama-server --jinja`（b11490 版本），在 8 个 CPU 核上跑 Qwen2.5-0.5B-Instruct。输出节选：

```console
$ toolsmoke --base-url http://localhost:8080/v1 --model qwen --anthropic
  ...
  tools.single            PASS     499ms  get_weather({"city": "Paris", "unit": "celsius"}) finish_reason=tool_calls
  tools.parallel          PASS      1.0s  2 calls with distinct ids: Paris, Tokyo
  tools.choice_none       FAIL     491ms  tool call leaked into content as text: '<tool_call> {{"name": "get_weather"…
  tools.choice_required   FAIL     20.4s  no tool call although tool_choice=required (reply: 'Hello! How can I assist…
  tools.choice_named      FAIL     473ms  called 'get_weather'; named tool_choice get_time was ignored
  tools.result_roundtrip  PASS     429ms  final answer uses the tool result
  stream.tools            PASS     485ms  get_weather({"city": "Paris", "unit": "celsius"}) assembled from deltas
  json.schema             PASS      1.4s  output validates against the strict schema
  errors.bad_model        WARN     127ms  unknown model accepted with 200 (server ignores the model name)
  errors.bad_request      WARN     114ms  invalid message role accepted with 200
  anthropic.tools         PASS     519ms  tool_use get_weather {'city': 'Paris'}, stop_reason=tool_use
  perf.ttft               PASS     917ms  p50 22 ms (min 19, max 50, n=3)
  perf.throughput         PASS      4.2s  62.4 tok/s (256 tokens via usage, 4.2s total)

  TTFT p50 22 ms · 62.4 tok/s · 24 pass · 2 warn · 3 fail · 2 skip
  NOT AGENT-READY: 3 failing probes
```

（完整的 31 行输出见 [README](https://github.com/Blackman99/toolsmoke#usage)。）

大部分都通过了：结构化的工具调用、符合 schema 的参数、并行调用、流式增量、工具结果回传、严格 JSON schema，连 Anthropic Messages 接口都没问题。三个失败全都跟 `tool_choice` 有关：

- **`none`**：明确要求只用文字回答，结果还是调了工具，而且调用以原始的 `<tool_call>` 标记出现在 `content` 里。如果智能体在做总结那一步关掉了工具，总结里就会混进这段标记。
- **`required`**：完全没有调用工具，模型花了 20.4 秒写了一句问候。
- **指定工具**：要求调 `get_time`，实际调的是 `get_weather`。

0.5B 的模型本身确实可能用不好工具，[FAQ](../faq.md) 里也写了这一点。但强制执行 `tool_choice` 是服务端的职责，标记泄漏到正文、指定工具被无视，这些不管模型多大都说明是服务层的问题。落到实际使用上：如果你的智能体靠 `tool_choice` 强制走某一步（路由和结构化抽取经常这么做），在这套配置下这一步会被悄悄跳过。而普通的 `auto` 工具调用完全正常，这正是没人发现的原因。

两个警告相对轻微：llama.cpp 不管你传什么模型名，都用已加载的那个模型回答；非法的消息角色也照样返回 200。速度方面，纯 CPU 下首字延迟中位数 22 毫秒，生成速度 62.4 token/秒。

## 放进 CI

这类问题真正的代价出在升级的时候：换了新版 llama.cpp、换了聊天模板、改了 vLLM 的解析器参数、动了网关配置。每次有这类变动就跑一遍：

```yaml
- uses: Blackman99/toolsmoke@v0.1.1
  with:
    base-url: https://llm.example.com/v1
    model: qwen3-coder
    api-key: ${{ secrets.LLM_API_KEY }}
    max-ttft: "1500"
```

只要有探针失败，这一步就会失败，并且会把 Markdown 结果表写进 job summary。详见 [CI 与 GitHub Action](../github-action.md)，也可以直接从 [Marketplace](https://github.com/marketplace/actions/toolsmoke) 使用。

## 它不做什么

toolsmoke 不评测模型能力，只检查智能体依赖的接口约定。提示词故意设计得很简单，所以出现失败时，基本可以确定是服务层坏了，而不是模型太弱。每个探针的详情一栏会告诉你具体是哪种情况。

如果你觉得某个探针对你的服务端判断有误，欢迎[提 issue](https://github.com/Blackman99/toolsmoke/issues/new/choose)，附上 `--format json` 的输出。
