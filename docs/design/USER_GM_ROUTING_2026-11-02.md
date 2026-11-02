# 设计：本局 GM 路由（user GM / 服务端 GM）

- 日期：2026-11-02
- 状态：已实现（本地工作区；对应 `ARCHITECTURE_CN.md` 头部 R12 条目）
- 关联：ADR-0007（runtime state ownership）、AISeatRuntime（`src/webui/services/ai_seats.py`，本设计的行为模板）、独立检定模型路由（`CHECK_MODEL_NOT_CONFIGURED` 失败语义模板）

## 1. 背景与目标

上游 DiceFrame 的 GM 统一由服务端扮演：所有对局共用 `config` 里的主模型与独立检定模型。两个痛点：

1. **多局并行时服务端消耗大**：N 局同时进行时，全部 GM 调用打向同一个服务端模型。
2. **能力错配**：很多模型不适合所有 GM 职责——例如叙事用大模型、检定规划用小而快的结构化模型，统一模型两头不讨好。

目标（用户原话）：

> 在对局时确保有一个 GM 存在就可以进行游戏，GM 可选 user/服务端，当 user GM 掉线时自动用服务端 GM 补上。user GM 可自由配置使用的模型，这样可以使用 user 本地部署的小模型。

非目标：

- 不引入多用户账号体系（保持 owner + 席位模型）。
- 不给 user GM 开内联 `base_url/api_key` 输入（凭据契约见 AGENTS.md：共享服务商目录 + `resolve_provider` 唯一出口）。user GM 的"本地小模型"以服务商条目形式登记在服务端共享目录里（例如 LM Studio / Ollama 的局域网地址），存档只保存引用。
- 不做 GM 权限细分：user GM 与服务端 GM 的**身份与权限完全相同**，区别只在"GM 大脑用哪个模型"。

## 2. 核心决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 状态归属 | `modules.gm_routing` 持久槽（schema 1） | 与 ai_seats / session_stats 同模式：模块拥有自己的槽位，迁移物化 fresh，未知 schema fail closed |
| 存档内容 | 只存 `provider_ref`/`model` 引用 + `mode` + `fallback_to_server` + `revision` | 存档绝不存凭据；删除服务商条目后引用自然失效并回退 |
| 并发控制 | `revision` 乐观并发 + `authoritative_write` 栅栏 | 与 ai_seats 完全同构 |
| 解析时机 | 调用期 `begin()`（每次 GM 生成独立解析 + 独立临时客户端） | 配置热重载、GM 掉线/重连、模型失效都能即时生效；临时 LLMClient 用完即关不泄漏 |
| presence | SSE 连接池 `is_online` + 建局后 180s 宽限窗 | 不引入第二套心跳；宽限窗覆盖"纯 AI 桌建局即自动推进"（GM 的 SSE 尚未建立） |
| 掉线语义 | 解析期回退服务端（reason=`gm_offline`），不在飞行中的生成里换模型 | 在飞结果以 `revision` 快照令牌废弃；掉线瞬间的语义简单可解释 |
| 失败语义 | 稳定错误码 `GM_MODEL_NOT_CONFIGURED`（409 + 回滚 + 行动保留可重试） | 与 `CHECK_MODEL_NOT_CONFIGURED` 同构；user GM 上线或配置修复后**直接重试**，无需重新提交 |
| 创建门槛 | user 主模型可解析即放宽服务端 LLM gate | "对局只需确保有一个 GM 存在"；服务端模型从前置条件降级为掉线兜底 |
| 核心流程耦合 | 创建路径经依赖注入钩子（`validate_gm_routing` / `apply_gm_routing`） | `tests/architecture/test_module_pluggability.py` 的 shrink-only 基线禁止核心创建流程 import 能力模块 |

## 3. 状态模型（`src/engine/modules/gm_routing.py`）

```text
modules.gm_routing = {
  schema_version: 1,
  revision: 0,            # 乐观并发；每次整体替换 +1
  mode: "server" | "user",
  user: null | {          # mode=user 时必须 main 非空
    main:       {provider_ref, model} | null,   # 必填（user 模式）
    fallback1:  {provider_ref, model} | null,   # 可选备用
    fallback2:  {provider_ref, model} | null,   # 可选备用
    check:      {provider_ref, model} | null,   # null = 跟随主模型
    fallback_to_server: true,                   # false = 不允许服务端兜底
  },
}
```

- 路由校验：`provider_ref` 必须是合法 provider id、`model` ≤160 字符、两者必须同时提供；`None` = 该能力继承服务端全局配置。
- `mode=user` 且 `main=null` → `main_required`（不允许"空配置"切到 user）。
- 迁移 47→48：旧存档无槽 → 物化 fresh（server 模式）；已有槽（含未来 schema）原样保留。

## 4. 运行时解析（`src/webui/services/gm_routing.py`）

### 4.1 presence 判定

```text
user_gm_online(instance)
  = presence(game_key, gm_uid)                      # SSE 连接池 is_online（bootstrap 注入；热重载由 config_controller 重绑）
    or started_at 距今 ≤ 180s                       # 建局宽限窗（activate 时 mark_started）
```

SSE 侧配套（`src/webui/routes/sse.py`）：

- 每 20 tick（≈10s）写注释帧 `:ka\n\n`——EventSource 忽略，但让死连接尽快被内核发现，把"GM 掉线 → 回退服务端"的延迟从"下一次广播"压到 ~10s。
- GM 连接：初始事件（baseline/run_story_changed 契约）写完后广播 `gm_source_changed`（`exclude_uid` 自身——它刚拿到完整快照）。
- GM 断开（finally，且该用户在池中已无连接）：广播 `gm_source_changed`。
- 前端对未知 SSE type 默认 refresh，`gm_source_changed` 无需专用分支即生效。

### 4.2 解析矩阵（`_resolve_view` + `begin`）

| 局面 | source | 说明 |
|---|---|---|
| mode=server | server | 透传服务端客户端（不 owns，绝不关闭） |
| mode=user + GM 在线 + main 可解析 | **user** | 主链 = user main → user fallback1 → user fallback2 →（`fallback_to_server` 且服务端可解析时）服务端主模型；dedicated check 链 = user check →（fallback_to_server 时）服务端检定模型，不可解析则降级到主链 |
| mode=user + GM 离线 | server | reason=`gm_offline`，自动兜底 |
| mode=user + main 失效 + fallback_to_server=true + 服务端客户端在位 | server | reason=`main_<原因>`（provider_missing / model_missing / model_not_chat…） |
| mode=user + main 失效 + fallback_to_server=false | 不可用 | reason=`model_unavailable` → 回合边界抛 `GmModelNotConfigured` |
| mode=user + GM 离线 + 服务端无客户端 | 不可用 | reason=`model_unavailable` |

**服务端可用性以 composition 注入的真实客户端为准**（`server_clients()[0] is not None`），而不是 live 配置字段——配置热重载的间隙里客户端仍然可用；反过来，`_server_main_ready(config)` 只用于构建兜底 provider 链（拿得到 ref 才 append）。

### 4.3 生成路径接入（谁在什么时候 begin/close）

| 路径 | 位置 | 行为 |
|---|---|---|
| 回合处理 | `round_processor.process_round` / `process_round_impl` | wrapper begin → impl 用 `generation.llm_client`（user）或 `self.llm_client`（server）→ finally close |
| 检定规划 | `prepare_round_checks_ai` | 同上；`check_client = generation.check_llm_client`，user 检定链独立 |
| swipe 改写 | `swipe_generator.generate` | 同上 |
| KP 问答 | `kp_questions.answer` | 同上 |
| 剧情概览 | `story_recap.generate` | 同上 |
| 开场叙事 | `game_lifecycle.start_game` | `gm_assume_online=True` 时跳过 presence（创建请求正由 user GM 本人发起，GM 席位/SSE 尚未建立） |
| 恢复叙事 | `game_lifecycle.resume_game` | 正常 presence 判定 |
| 摘要压缩 / 分镜草稿 / 场景图 | `_background_gm_client`（asynccontextmanager） | 后台任务**独立解析**并自管生命周期；reason=`model_unavailable` 时 yield None（调用方跳过该任务），绝不把配置问题当错误上抛 |

server 来源一律沿用**本组件自己的**服务端客户端（同一 composition 注入、热重载后同批更换），只有 user 来源使用路由层构建的临时客户端——临时客户端由 `GmGeneration.close()` 统一关闭，透传的服务端客户端 `owns_clients=False` 永不关闭。

### 4.4 投影（`project`）

`GET /api/games/{key}/gm-routing` 返回：`revision` / `mode` / `user`（已校验）/ `effective{source, reason, user_gm_online, main, fallbacks, check_mode, check}` / `providers`（仅 chat 能力模型）/ `application`（服务端主模型与检定模型引用）。**绝不含 base_url / api_key**（测试断言）。

## 5. 失败语义：`GM_MODEL_NOT_CONFIGURED`

- 抛点：`RoundProcessor._begin_gm_generation`（reason=`model_unavailable` 时，先 close 临时客户端）。
- 回合边界（`turns._process_round` 及三处 advance/prepare 调用点）：与 `CHECK_MODEL_NOT_CONFIGURED` 完全同构——`_rollback_unprocessed_advance` → 409 + `error_code` + `advanced=false`，行动保留在队列，**user GM 重新连接或配置修复后直接重试**。
- 前端：`ActionComposer` 的 code 白名单 + `recovery/copy.ts` 五语文案（`gmModel`）。
- `error_code` 是对外契约，不得随文案改动。

## 6. 创建路径

- 载荷：`POST /api/games/create` 可带 `gm_routing = {mode, user}`。
- 校验（`api._validate_creation_gm_routing` → `runtime.validate_settings`）：mode 白名单 + user 形状 + user 主模型在共享目录中可解析（reason 码 → 可操作中文提示）。失败返回 `INVALID_GM_ROUTING`（400）。
- **gate 放宽**：user 主模型可解析时跳过 `llm_configuration_error`（`llm_not_configured`）——服务端模型从"必须配置"降级为"掉线兜底"。server 模式不放宽。
- 槽位写入：`create_game` 在 `INSTANCE_CONFIGURED` 阶段经 `apply_gm_routing` 钩子写入（revision 从 fresh 的 0 起步），随后的开场生成（`gm_assume_online=True`）即按 user 路由解析。
- 依赖注入而非直接 import：`GameLifecycleDependencies.validate_gm_routing / apply_gm_routing`，保持核心创建流程不依赖能力模块（shrink-only 基线）。
- v1 限制：`create-from-seed` 不带 gm_routing（种子重开沿用原局配置语义，未扩展）。

## 7. 权限

- `GET/PUT /api/games/{game_key}/gm-routing` 为 **GM-only**（`viewer_for(request, inst).is_gm`；非 GM 403，局不存在 404）。
- 不加入 access_control 的 share 白名单——与 `GM_SEAT_REQUIRES_OWNER` 一致：非 owner 的 share 身份永远不能代表 GM。
- GM 身份仍是 `gm_uid`（严格绑定第一个成功创建的角色 = 创建者，`force_uid`）；user GM 的"人"就是这个席位后面的人。

## 8. 前端

- `frontend-v2/src/features/gm-routing/`：`types.ts`（严格解析器）、`copy.ts`（五语）、`GmRoutingEditor.vue`（受控编辑器：模式卡片 + main/fallback1/fallback2/check 四组 provider::model 下拉 + fallback_to_server 开关）。
- 创建向导（`CreateView` 第 2 步）：GM 来源字段集；user 主模型可解析时隐藏"请先配置服务端主模型"的提示（`showApiSetupHint`），确认页显示所选来源。
- 对局（`PlayView` #party 槽，AI 座位面板之后）：`GmRoutingPanel` —— 状态卡（当前生效来源/模型/在线状态/回退原因）+ 4s 轮询 + Modal 编辑 + `expected_revision` 乐观并发保存。
- SSE：未知 type 默认 refresh，已覆盖 `gm_source_changed`。

## 9. 已知 v1 限制

1. **bot / P2P 对局无 SSE presence**：user 模式不可用（宽限窗过后按掉线回退服务端）。建议此类对局保持 server 模式。
2. 后台任务（摘要/分镜/场景图）用各自解析的客户端：GM 离线回退服务端；服务端也无模型则跳过该任务（不阻塞对局主流程）。
3. user GM 的"本地小模型"需要以服务商条目登记（如 `http://<用户机器>:1234/v1`）；服务端必须能访问该地址。纯离线本地模型只能用"服务端就跑在用户机器上"的部署形态（Portable/Docker 本机）承载。
4. `create-from-seed` 不支持 gm_routing。

## 10. 测试

后端 `tests/test_gm_routing.py`（25 例）：模块校验/revision/持久化不含凭据、迁移 47→48（fresh 物化/已存槽保留/未来 schema 保留/幂等）、解析矩阵（server 透传不持有、在线链构建、离线回退、宽限窗、presence 探针参数、main 失效 + 服务端兜底、无可用模型、check 继承）、投影不含凭据、validate_settings 全 reason 码、服务层（revision 冲突/未知字段/保存失败回滚/局不存在）、`GM_MODEL_NOT_CONFIGURED` 抛点与 turns 409 结果、后台客户端 None 语义与临时客户端关闭、生命周期 assume 标志、路由权限（403/404/200/400）+ 更新、连接池 is_online、创建 gate 放宽矩阵、`apply_creation_settings`。

前端 `frontend-v2/tests/GmRoutingPanel.test.ts`（7 例）：状态卡渲染、离线回退说明、PUT 载荷与 revision、非 GM/预览不拉取、payload 助手（server 无 user 残留/失效路由清空）、解析器拒绝畸形投影。

回归：后端全量（除 3 个 docker 文件的 7 个基线即失败的环境用例）通过；前端 vitest 1403 例、vue-tsc、eslint、vite build 全绿。
