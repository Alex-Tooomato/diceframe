# user GM 本地小模型推荐（CPU / RTX 5070 Ti · Windows）

- 日期：2026-11-02
- 适用：本局 GM 路由（user GM 模式）下，把 GM 的主叙事 / 备用 / 独立检定模型放到本机跑，减轻服务端与云端开销、提升判定速度。
- 运行环境假设：Windows + RTX 5070 Ti 16GB 显存（或纯 CPU 兜底）；推理后端推荐 [LM Studio](https://lmstudio.ai)（开 Local Server 即得 OpenAI 兼容 `/v1`，直接登记进 DiceFrame 的 AI 服务商目录）或 [Ollama](https://ollama.com)（`OLLAMA_HOST=0.0.0.0` 后同样 OpenAI 兼容）。

> 登记方式：设置 → AI 服务商 → 添加服务商，Base URL 填 `http://<本机IP>:1234/v1`，模型列表填下表中的模型名。DiceFrame 存档只保存引用，不存密钥。若 DiceFrame 服务端与这台 GPU 机器不在同一台机器上，需保证服务端能访问该地址。

## 按能力推荐（16GB 显存优先级序）

| 能力（配置位） | 首选 | 备选 | 说明 |
|---|---|---|---|
| **主叙事模型**（user main） | **Qwen3 27B · Q4_K_M**（≈16GB，需关闭系统占显存；建议 Q4_0/IQ4_XS 稳妥放下） | **gpt-oss-20b**（≈12–13GB，5070 Ti 上约 189 tok/s，MXFP4 原生量化） | 叙事要长文风与指令跟随，27B Q4 是 16GB 卡的甜点；显存吃紧就用 gpt-oss-20b，速度更块 |
| **备用模型 1**（user fallback1） | **Mistral Small 3.1 24B · Q4_K_M**（≈14GB） | **Gemma 4 12B · Q4** | 与主模型不同家族，避免同源故障；Mistral Small 3.1 中文与工具调用都稳 |
| **备用模型 2**（user fallback2） | **Gemma 4 12B · Q4**（≈7–8GB） | Qwen3 14B | 换小一级，失败场景常常是显存/超时，降规格比换家族更有效 |
| **独立检定模型**（user check） | **Qwen3.5-9B**（结构化 JSON 快而稳） | **gpt-oss-20b** / **Phi-4-mini** / **Gemma 4 E4B** | 检定规划输出结构化 JSON，小模型在此任务上与大模型差距最小；速度收益最大（40–80+ tok/s CPU 亦可兜底）。注意：**可靠工具调用**建议 27B+，检定规划属"受控 JSON 输出"不在其列 |
| 服务端兜底（fallback_to_server） | 云端任一廉价对话模型 | — | user GM 掉线时的保险，不必追求质量 |

## 不推荐 / 注意

- **Qwen3.6-35B-A3B**：MoE 效果好但权重 ≥24GB 显存，16GB 卡放不下（量化后激活值仍高），不建议。
- 27B Q4 与 24B Q4 **不要同时常驻**：合计超 16GB。LM Studio / Ollama 按需换入换出会有首 token 延迟，GM 路由的备用链触发时可能已换页——建议同一时刻只常驻 1 个 ≥20B 模型 + 1 个 ≤9B 小模型（合计 ≈19GB 会溢出，实际请选 27B 主模型 **或** 24B 备用其一常驻，另一个只做云端备选）。
- 纯 CPU 场景：Qwen3.5-9B / Gemma 4 E4B / Phi-4-mini 的 Q4 量化在主流桌面 CPU 上 5–15 tok/s，可胜任检定规划与 KP 问答；叙事生成建议仍走 GPU 或云端。
- embedding（记忆检索，服务端能力，与 user GM 路由无关）：Qwen3-Embedding 0.6B / 4B。

## 一组可抄的配置（5070 Ti 单卡）

```text
user main      = <LM Studio> qwen3-27b-q4          # 主叙事
user fallback1 = <LM Studio> gemma-4-12b-q4        # 同机小备胎（≈8GB，可与 27B 共存需注意总显存）
user check     = <LM Studio> qwen3.5-9b-q4         # 独立检定（可 CPU 跑）
fallback_to_server = true                          # 掉线自动回退服务端 GM
```

> 实测显存提示：27B Q4_K_M + 12B Q4 同时加载约 23GB，超出 16GB。若要双常驻，主模型降到 gpt-oss-20b（≈13GB）+ 9B 检定（≈6GB）≈ 19GB 仍略超；**最稳妥是 20B 级主模型单常驻 + 检定模型用 CPU 跑**，或主模型 27B 单常驻、备用走云端。

## 为什么检定模型值得独立

DiceFrame 的检定规划（`plan_round_checks`）是"读行动 → 产出结构化检定提案"的短输出任务：延迟直接影响每轮手感，质量对小模型不敏感。把它从 27B 叙事模型换成 9B 级结构化模型，通常是单轮延迟下降最明显的一处改动——这也是本功能把 check 从"跟随主模型"独立出来的原因。
