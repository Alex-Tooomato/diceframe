# DF Agent 实现与能力边界

DF Agent 是 DiceFrame 的全局应用代理。展示名称统一为 `DF Agent`；既有 assistant API、storage key 与内部 identity 保持稳定。

## 用户路径

- 所有房主业务页面共享悬浮入口，可在右侧抽屉与居中大窗口间切换，切换页面保留任务。悬浮入口支持鼠标和触屏拖动，位置保存在当前浏览器，窗口缩小后夹紧到可见区域；短点与键盘激活仍打开聊天，拖动不会误触打开。
- 顶部“扩大窗口”按钮打开最大 1060×800 的居中窗口，四周保留页面空隙；同一按钮可缩回侧栏。桌面大窗口左侧聊天、右侧草稿/审批/结果工作区，窄屏采用单列。切换只调整同一组件的布局，保留正在输入的文字、未保存的草稿编辑和进行中的请求。
- 设置 → 外观可关闭入口；偏好存于当前浏览器。登录、公开分享、玩家与联机公开入口不挂载房主管理助手。
- 操作依据真实工具目录与运行时观察。仅在需要使用说明时调用只读 `search_documentation`，不为每次聊天自动检索文档；使用当前本地说明或经过程序版本校验的内置索引，排除移动远程指南。没有主模型时给出服务商目录配置指引，并提供打开设置的入口。
- 聊天收到 SSE 正文后，通过 `ProgressiveTextQueue` 平滑逐字显示，长段自动提高显示速度；后端仍先完成框架规划与输出校验，再返回答复。工具、草稿、审批与导航事件即时处理，不等待正文动画。停止保留全部已收文字，清空/重置取消旧队列；显示结束后再保存完整历史，扩大窗口与切页共享同一状态。
- 生成世界、世界书、角色模板、冒险包先得到草稿。卡片允许编辑并重新审查；编辑使旧保存计划失效。
- 保存内容、创建游戏、切换角色控制、提交行动、生成规则/图片、运行插件显示执行卡片。客户端只回传计划 ID、摘要和确认意图，不能改写待执行参数。
- 活动确认卡、草稿与执行结果显示在对话记录下方；活动确认卡位于任务区域末尾，收到确认请求后自动滚动到按钮。没有正文回复的审批步骤在最新回复显示“等待确认”，输入框旁保留同一状态提示。
- 结果提供对应工作台或游戏页入口。继续任务会携带已有草稿摘要和执行结果，无需重新讲述目标。

## 模块

| 模块 | 职责 |
| --- | --- |
| `components/assistant/AssistantShell.vue` | 全局入口、抽屉、首页欢迎气泡 |
| `composables/useAssistantPreferences.ts` | 浏览器显示偏好 |
| `composables/useAssistant.ts` | 会话、事件、恢复、确认与客户端历史 |
| `composables/progressiveTextQueue.ts` | Unicode 码点安全的正文显示队列、积压加速与取消 |
| `components/assistant/AgentTaskCard.vue` | 内容草稿编辑与重新审查 |
| `routes/assistant_agent.py` | owner 门控、请求验证、SSE/JSON 传输 |
| `services/assistant_agent.py` | 业务工具适配、计划、会话与执行记录 |
| `services/assistant_agent_framework.py` | 直接使用 Pydantic AI Agent 执行器，适配现有模型传输 |
| `services/assistant_agent_application.py` | 显式依赖适配现有应用服务 |
| `services/assistant_content.py` | 无副作用生成 → 既有内容 review/commit |
| `services/assistant_authoring.py` | 读取现有内容、修改自建世界/角色叙事、写入具有明确可见性的资料册条目 |
| `services/content_recovery.py` / `content_metadata_recovery.py` | owner 私有快照、版本检查、内容撤销与回收站 |
| `lorebook/operations.py` | owning SQLite 操作日志、无覆盖的 canonical 恢复 |
| `services/game_lorebooks.py` | 开局后本局选书、portable refs、保存与补偿 |

## 已注册能力

`read_catalog`、`read_game`、`navigate`、`draft_content`、`save_content`、`create_game`、`set_player_control`、`submit_action`、`create_rule`、`generate_image`、`invoke_plugin_tool`、`set_plugin_enabled`、`diagnose_runtime`、`read_content`、`edit_world`、`write_lorebook_entries`、`edit_character_card`。

另已注册 `list_content_operations`、`set_lorebook_enabled`、`set_lorebook_entries_enabled`、`archive_lorebook_entries`、`archive_lorebook`、`undo_content_operation`、`restore_content_operation`、`read_game_lorebooks`、`set_game_lorebooks`，合计 26 项。

目录可读取世界、世界模板、世界书、冒险、角色卡、规则、游戏、已安装插件与插件工具。模型须从目录选择 canonical ID。创建游戏明确选择角色卡、冒险来源与世界书引用，沿用游戏创建事务与规则校验；创建同时生成开场。已有内容的复杂编辑、导入/导出和设置通过对应工作台继续。

内容草稿采用现有 `ContentTextReview` 契约。世界与角色模板是可复用的叙事内容，不推断专业规则数值；专业建卡仍由规则工作台处理。世界书草稿当前保存为一本完整资料册中的文本条目。冒险通过原生脚本解析器生成 graph v2；引用未解析、图无效或目标冲突阻止保存，文本不会被转换为未经授权的 mechanics。

已接入用户批准的 [内容纠错、撤销与删除策略](DF_AGENT_DELETE_POLICY.md)。修改和启停可按记录撤销，自建条目与未被引用的非主册可有限归档并恢复；每批最多 10 条归档/启停条目，整册最多 10 条。内置、插件来源及整本主册受保护，永久删除留在手动流程。只有新路径记录的操作支持撤销，历史操作与世界/冒险/角色创建不自动回滚。插件调用仅接受明确 `agent_effect=read_only` 声明，未知或破坏性工具交给手动流程；此声明不替代宿主权限或原生进程安全边界。

开局后可在 GM 工作台 → 场景 → 本局资料册调整最多 16 本来源，预览后确认，只替换本局绑定，角色来源锁定。内容 → 资料册 → 内容撤销 / 回收站提供同一服务器审批链的恢复界面，包含结果待核实、已撤销和已恢复状态；普通手动恢复/选书不需要模型调用。

公开世界、世界书与角色模板不接收带隐私标记的生成或编辑结果，避免把 GM 内容写入公开字段。冒险的 `GM:` 行通过现有解析器成为 GM-only reference 节点。`write_lorebook_entries` 可批量补写/修改一本资料册，明确选择 public 或 gm；新条目缺省 GM-only，更新缺省保留原可见性，不能把 GM 标记写入公开条目。跨资料册猜测条目 ID 会拒绝；生产路径整批内容与快照在 owning SQLite 事务中提交，失败全部回滚。

## API

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/assistant/chat` | 保留原有只读问答契约 |
| POST | `/api/assistant/agent/run` | messages/language/context/session_id → SSE |
| POST | `/api/assistant/agent/review` | 重新校验当前会话草稿 |
| POST | `/api/assistant/agent/confirm` | 确认或取消服务器保存的执行计划 |
| POST | `/api/assistant/agent/plan` | 明确白名单工具的手动计划，无需模型 |
| GET | `/api/assistant/agent/content-operations` | 当前 owner 的恢复记录元数据，不传快照正文 |
| GET | `/api/games/{game_key}/lorebooks` | 房主读取本局实际来源与锁定角色来源 |
| GET | `/api/assistant/agent/session/{session_id}` | 恢复草稿、计划与执行记录 |

SSE 保留 delta/sources/reset/done，并增加 session/status/tool_start/tool_result/draft/approval/navigate。导航只允许已知本地业务 route 和受限 query，模型不能提供可执行 URL。

## 运行保证

- 所有 Agent API 明确 owner-only。会话绑定服务端用户身份，页面上下文只是提示，不授权 actor/game/tool。
- 执行内核直接使用 [Pydantic AI](https://github.com/pydantic/pydantic-ai/tree/v1.107.7) 的 `Agent`、`Tool`、`ModelRetry`、`DeferredToolRequests` 和 `UsageLimits`，依赖固定为 `pydantic-ai-slim==1.107.7`，支持项目的 Python 3.10+ 契约。MIT 许可保留于 `THIRD_PARTY_NOTICES.md`。
- 移除自写 `agent_step / respond` 包装与循环。26 项业务工具分别公开具名函数和参数 schema；普通回答可使用正文或独立 `FinalAnswer` 输出，不再要求回答带空参数对象。工具和输出校验失败由框架携带纠错信息重试，单工具/输出最多 3 次重试，每轮最多 8 次模型请求及 8 次工具调用。模型一次返回多个已注册的非审批查询或草稿工具时，由框架按顺序执行；含审批写操作、最终回答或未知工具的批次整批拒绝，向下一轮附上明确格式纠正信息，不执行其中任何业务工具。审批仍每次只允许一个写操作。
- 框架收到修改工具时先校验参数和业务前提，再产生延迟审批请求；它不会执行写操作。原确认接口仍拥有派发权，前端事件与持久化 schema 1 保持不变。
- 现有 `LLMClient` 保留共享服务商引用、请求超时、代理和备用模型；Agent 明确选择 auto 工具模式。原游戏判定强制工具模式保持默认契约。不支持原生工具的服务商仍使用完整具名工具 schema 的 JSON 回退。框架历史保留工具结果、调用关联和纠错反馈；不另建配置来源。
- 模型调用全部失败时保留 HTTP 状态事实。Agent 将服务商余额不足（402）、凭据/权限拒绝（401/403）、请求限制（429）和其它不可用状态转成明确的用户提示，不把服务商原始响应、地址或凭据放进错误卡片。
- 工具或输出格式连续纠正失败时返回 `MODEL_RESPONSE_INVALID`，说明模型工具调用未通过校验和已有草稿仍可继续处理；不把框架堆栈或原始模型参数放进提示，也不再落入通用执行失败。
- 修改必须确认。计划与会话、身份、参数、目标状态和 15 分钟有效期绑定；草稿修改或资源变化要求重新计划。
- `data/assistant_agent` 保存 schema 1 会话与执行记录，不保存服务商凭据。会话 24 小时失效、每会话最多 16 个草稿。模型观察与结果中的凭据字段及常见令牌文本脱敏。
- 确认并发串行，重复提交返回原执行记录。浏览器断开不取消已派发写操作；结果可恢复。
- 重启遇到派发后尚未记录结果的操作，标为 recovery_required，禁止盲目重放。SQLite 内容修改整批提交；跨文件的世界/角色叙事与游戏选书先写 prepared 日志，未能核实结果时不标为可自动恢复，也不重复执行。
- Agent 不提供 shell、任意 HTTP、任意文件/数据库写入或直接权威状态编辑。游戏行动使用当前服务器身份与服务器骰，插件调用仍经过宿主 schema 与现有权限边界。
- 运行日志仅在用户明确请求诊断时进入上下文；文档、插件、草稿、日志和工具输出均按外部数据处理。

## 验证

覆盖全局入口/公开页隔离/显示偏好、真实格式草稿编辑、SSE 协议、owner 与会话隔离、参数伪造、计划完整性/失效/取消、重复与并发提交、持久化恢复、隐私标记拒绝，以及真实内容落库与游戏存档创建。执行器测试使用真实 Pydantic AI，模型响应使用可控替身；HTTP 集成覆盖真实 `LLMClient` 的 OpenAI、Anthropic 和 JSON 回退，以及错误参数纠正到审批的路径。生产模型响应质量依赖配置的服务商。

### 2026-10-13 接入验收

- 已移除生产路径中的自写执行循环与 `agent_step / respond` 包装；执行图、输出校验、纠错重试、步骤预算和延迟审批来自已固定版本的 Pydantic AI。
- 现有 17 项能力、全局入口、设置开关、草稿编辑、确认/取消、恢复和幂等契约保持有效。真实领域服务覆盖内容落库及游戏创建，模型与客户端不能直接修改权威游戏状态。
- 桌面与手机端完成草稿编辑 → 重新审查 → 保存确认 → 页面跳转 → 关闭入口。前端 Agent 定向 25 项测试、类型检查和构建通过。
- 使用当前已配置服务商的真实模型，在临时数据目录完成世界书和冒险包生成、内容审查、保存计划、确认落库与重复确认。此验收不写入用户内容库或游戏存档。可显式设置 `DICEFRAME_AGENT_LIVE=1` 运行 live 验收；默认自动化不访问付费模型。
- 便携版和 Docker 保留原有依赖版本，新增依赖全部使用实际 wheel 的 SHA-256 固定。两平台完整锁经 `--require-hashes` 下载验证；Windows 独立虚拟环境按完整锁安装，并通过真实框架和业务集成测试。许可声明进入源码与便携版打包范围。
- 验收由本会话 Codex（GPT-6）主代理负责，`gpt-5.6-luna` 子代理仅执行限定的传输、测试夹具和依赖接入；没有另行安排高阶规划代理。
- 正在运行的进程不会热更新已导入的 Python 模块；源码接入后需要通过应用的正常重启流程加载。本次没有改版本号、提交、发布、重置密码或覆盖用户配置。

### 2026-10-14 六项问题验收

- 日志复现模型响应被判为 `invalid_provider_response`、连续重试耗尽后落入通用执行失败。查询/草稿批次现在由真实框架顺序执行，包含审批或最终回答的批次仍整批拒绝；下一轮获得具体格式纠正信息，耗尽时返回明确错误并保留草稿。OpenAI、Anthropic 与 JSON 回退均覆盖该路径，写操作未确认前不派发。
- 使用当前已配置服务商和原话“随便想一个冒险包”，在临时目录完成真实生成、脚本审查、保存确认、落库及重复确认。验收不写入用户资料库或存档。
- 存档卡 hover/选中时仅背景艺术轻微放大，文字和按钮位置保持稳定；取消选中或移开恢复，减少动态效果偏好取消缩放变化。保留方形毛玻璃进入按钮。
- 内容库“打开”携带 canonical book ID 和实际世界绑定；资料页选中目标册，entry 深链接选择对应条目。用户后续切换不被迟到响应覆盖，编辑期间保留草稿。普通资料册菜单明确显示“删除资料册”，主资料册展示保护说明；删除继续使用已有确认/API，不扩大 Agent 删除权限。
- 悬浮入口完成真实鼠标与 Chromium 触屏拖动验收，拖动不打开聊天，短点/触摸/键盘可打开，刷新保留位置，缩窄视口后仍可见。
- Freeform D&D 轻量装备编辑开放独立 `damage_dice` 字段，支持既有解析器的 `NdM`、`NdM+K`、`NdM-K`，固定伤害保留为无骰式时的回退。创建/编辑保存和显示保留骰式，非法公式在角色服务拒绝，弹窗保留输入并显示错误，手机控件换行。专业 `dnd2024` 继续使用自身已有的骰式装备/战斗契约。
- 验证：195 项后端测试、97 项前端测试、真实模型冒险用例、生产构建与针对性 ESLint 通过。浏览器分批覆盖 15 个桌面/手机有效场景，包括原有草稿审批、回收站工具栏和赞助图回归；另有 3 个按输入设备/项目条件跳过的场景。主代理负责总验收，三个 `gpt-5.6-luna` 子代理执行限定修改，没有额外高阶规划代理。

### 2026-10-14 关联世界缺失的资料册导航

- 只读核实用户报错的资料册：Book 与 primary world binding 仍存在，关联世界数据库记录与模板文件已缺失，资料册当前为空。没有推断世界缺失的历史原因，也没有修改用户内容或关联。
- 内容库链接只携带实际存在的世界；canonical book ID 决定打开目标。旧链接同时包含缺失 world 与有效 book 时独立打开资料册并提示；失效 world-only 链接继续拒绝。空册、条目定位、语言切换和手动换书后的刷新保持正确上下文，主资料册删除保护保留。
- 先在隔离数据库复现新增与移入该 Book 的外键失败，再修复 owning store 的兼容投影：只有真实存在的 primary world 才投影到条目 `world_id`，否则为 NULL；canonical `book_id` 与原 binding 保持不变。独立浏览支持手动新增、编辑和导出，需要世界上下文的功能保持原有条件。
- 验证：118 项后端、59 项前端测试，桌面/手机 4 项真实浏览器场景、生产构建和针对性 ESLint 通过。浏览器验证新增保存、编辑、导出、旧链接、条目定位和 primary 删除保护；核对前后 world 名单与 bindings 未改变。GPT-6 主代理完成总验收，Luna 协助限定前端修改，没有额外高阶规划代理。
