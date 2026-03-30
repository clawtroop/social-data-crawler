# Mining Service E2E 用户旅程测试矩阵

这份文档按两层组织：

- 第一层：用户旅程 `UJ-xxx`，描述真实用户目标
- 第二层：子用例 `TC-UJxxx-yy`，描述可独立执行、可独立失败、可独立回归的验收点，并在表格中直接体现协议分支与异常分支

这样可以同时满足四件事：

- 保持“以用户旅程为主线”的测试设计
- 保持 Given / When / Then 的系统化表达
- 在子用例表格中直接覆盖协议关键分支，而不是额外维护一段分支清单
- 让每条用例都能追溯到 `spec.md` 和协议文档中的具体要求

执行入口统一为：

- `make e2e-mining-service` → `cd apps/platform-service && go test ./test/e2e/mining -v`
- `make e2e-mining-core-integration` → `cd apps/platform-service && go test ./test/e2e/mining -run 'TestUJ201CoreSubmissionIntegrationJourney$$' -v`

## 1. Spec 锚点索引

| 锚点 ID | Spec 文件 | 关键 Requirement / Scenario |
|---|---|---|
| SPEC-HTTP-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/mining-service-http-runtime/spec.md` | `GET /healthz` / `GET /readyz` / `GET /metrics`；Miner / Validator / Admin 受保护业务接口 |
| SPEC-AUTH-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/mining-service-http-runtime/spec.md` | Bearer Token 校验；按 `admin` / `miner` / `validator` 角色授权 |
| SPEC-MINER-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/miner-runtime-guardrails/spec.md` | Miner 心跳、在线状态、TTL 下线 |
| SPEC-MINER-002 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/miner-runtime-guardrails/spec.md` | 信用分分层、同 IP 衰减、提交前限流 |
| SPEC-MINER-003 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/miner-runtime-guardrails/spec.md` | AI PoW 挑战创建、答题校验、一次性放行 |
| SPEC-REPEAT-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/repeat-crawl-task-orchestration/spec.md` | Repeat Crawl Task 创建与候选人排除 |
| SPEC-REPEAT-002 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/repeat-crawl-task-orchestration/spec.md` | Step 1 / Step 2 一致性裁决 |
| SPEC-REPEAT-003 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/repeat-crawl-task-orchestration/spec.md` | Repeat score 沉淀与 Miner Epoch 统计 |
| SPEC-VAL-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/validator-evaluation-orchestration/spec.md` | Validator 资格状态、最小任务间隔、ready_pool |
| SPEC-VAL-002 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/validator-evaluation-orchestration/spec.md` | 单 Validator / Peer Review 派发与降级 |
| SPEC-VAL-003 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/validator-evaluation-orchestration/spec.md` | Golden Task 注入、评分结果持久化、同行校准 |
| SPEC-EPOCH-001 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/mining-epoch-performance-metrics/spec.md` | Miner `task_count` / `avg_score` 聚合 |
| SPEC-EPOCH-002 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/mining-epoch-performance-metrics/spec.md` | Validator `eval_count` / `accuracy` / `peer_review_accuracy` / `consecutive_idle` 聚合 |
| SPEC-EPOCH-003 | `openspec/changes/c-20260327-mining-service-runtime-tasks/specs/mining-epoch-performance-metrics/spec.md` | Epoch 快照查询 |

## 2. 协议锚点索引

| 锚点 ID | 协议章节 | 关键规则 |
|---|---|---|
| PROTO-MINER-001 | `docs/Subnet_协议设计_v1.6 (1).md` 第四章 | Miner 注册、信用分、AI PoW、IP 衰减 |
| PROTO-REFRESH-001 | `docs/Subnet_协议设计_v1.6 (1).md` 第二章刷新机制 / 第三章 URL 唯一性 | RefreshTask 随机指派、排除历史提交者和同 IP、失败重分配、计入 `task_count` |
| PROTO-REPEAT-001 | `docs/Subnet_协议设计_v1.6 (1).md` 重复爬取 / Phase A 章节 | Step 1 / Step 2 真实性校验、随机指派、排除同 IP |
| PROTO-VAL-001 | `docs/Subnet_协议设计_v1.6 (1).md` Validator / Phase B 章节 | ready_pool、单评估、Peer Review、Golden Task |
| PROTO-EPOCH-001 | `docs/Subnet_协议设计_v1.6 (1).md` Epoch / 评分章节 | `avg_score`、`accuracy`、`peer_review_accuracy`、`consecutive_idle` |
| PROTO-RUNTIME-001 | `docs/Subnet_协议设计_v1.6 (1).md` 协调器与运行态相关章节 | 在线 Miner/Validator、随机分配、刷新/重复任务不开放自由抢跑 |

## 3. 用户旅程总览

| # | 旅程 ID  | 用户目标 | 主要参与者 | 子用例数 | 结果类型 |
|---|--------|---|---|---|---|
| 1 | UJ-101 | miner 完成上线登记并获得提交资格 | miner, admin | 4 | 正向前置链路 |
| 2 | UJ-102 | 低信用 miner 遇到限流或 PoW，完成挑战后继续提交 | miner | 9 | 防滥用主链路 |
| 3 | UJ-103 | admin 发起重复爬取校验并完成 Step1/Step2 裁决 | admin, miner | 9 | 真实性校验链路 |
| 4 | UJ-104 | validator 进入 ready_pool 并完成单评估 / 降级评估 | validator, admin | 9 | 评估派发链路 |
| 5 | UJ-105 | peer review / golden task 完成后沉淀评分与准确率 | validator, admin | 9 | 评分沉淀链路 |
| 6 | UJ-106 | admin 查询 epoch 快照并确认统计结果可用于结算 | admin | 5 | 结算前核对链路 |
| 7 | UJ-107 | 被指派 miner 完成 refresh task，并让新版本进入正常评估链路 | miner, admin | 6 | 刷新任务链路 |
| 8 | UJ-108 | 运维确认服务存活、鉴权边界与观测性 | operator, admin | 3 | 横切保障链路 |
| 9 | UJ-201 | 管理员确保 core 侧 submission 进入完整质检与结算链路 | admin, miner, validator | 7 | 跨服务用户旅程 |
| 10 | UJ-202 | admin 获取某个 Epoch 的最终结算结果，作为奖励结算与风控判断依据 | admin | 5 | 结算结果消费旅程 |

## 3.1 范围说明

- 本文档聚焦 `Mining Service` 单服务与其 HTTP / 运行时编排职责。
- 协议中 `Validator` 的链上质押准入、容量上限、竞争替换、保护期属于跨链上 / 跨服务边界；若后续由 `Mining Service` 直接实现，再单独补充新的用户旅程。
- `UJ-107` 虽然涉及 `RefreshTask`，但这里关注的是 mining 侧被指派 miner 的 claim / 执行 / 统计沉淀链路，不覆盖 Core Service 的过期扫描和 URL 重新开放实现细节。
- `UJ-202` 关注的是 admin 如何消费“已经完成”的 Epoch 最终结算结果，用于奖励结算和风控判断；它不重复覆盖 Core Service 侧的结算调度实现细节。

## 4. 用户旅程与子用例

### 4.1 UJ-101 miner 完成上线登记并获得提交资格

旅程目标：  
作为 miner，我要完成心跳登记并进入在线候选集合，使系统后续可以把提交前检查和重复爬取任务分配给我。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 1 | TC-UJ101-01 | miner 心跳成功后进入在线集合 | 服务已启动；miner Bearer Token 可用；该 miner 尚未登记 | 调 `POST /api/v1/miners/heartbeat` 上报 `ip_address` 和 `client` | 返回 `200` 且 `success=true`；返回模型包含 `miner_id/ip_address/client/last_heartbeat_at/online`；`online=true` | SPEC-HTTP-001, SPEC-AUTH-001, SPEC-MINER-001, PROTO-RUNTIME-001 |
| 2 | TC-UJ101-02 | admin 查询在线列表可见新上线 miner | 至少已有一个 miner 成功心跳；admin Bearer Token 可用 | 调 `GET /api/v1/miners/online` | 返回列表包含该 miner，且不会返回已过期离线 miner | SPEC-HTTP-001, SPEC-AUTH-001, SPEC-MINER-001 |
| 3 | TC-UJ101-03 | TTL 过期后 miner 自动离线 | 某 miner 已成功心跳；测试时钟可推进到 TTL 之后 | 在不继续上报心跳的情况下查询在线列表或触发候选筛选 | 该 miner 不再被视为在线，也不再进入任务候选集合 | SPEC-MINER-001, SPEC-REPEAT-001, PROTO-RUNTIME-001 |
| 4 | TC-UJ101-04 | 非 admin 不能查询全量在线列表 | 服务已启动；存在 miner / validator token | 由 `miner` 或 `validator` 访问 `GET /api/v1/miners/online` | 请求被拒绝，返回 `403` 或等价授权失败 | SPEC-AUTH-001, SPEC-HTTP-001 |

### 4.2 UJ-102 低信用 miner 遇到限流或 PoW，完成挑战后继续提交

旅程目标：  
作为低信用 miner，我在提交前检查时可能遇到 AI PoW 或额度限制；我需要在符合协议规则的前提下完成挑战并继续一次合法提交。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 5 | TC-UJ102-01 | 低信用 miner 提交前检查命中 PoW | 某低信用 miner 已在线；PoW 触发概率被测试固定命中 | 调 `POST /api/v1/miners/preflight` | 返回 `200`；`allowed=false`；响应包含 `challenge_id`；不会直接授予提交权限 | SPEC-MINER-002, SPEC-MINER-003, PROTO-MINER-001 |
| 6 | TC-UJ102-02 | PoW 错答不会放行提交 | 已存在待完成的 challenge | 调 `POST /api/v1/pow-challenges/{id}/answer` 提交错误答案 | challenge 被记录为已答但未通过；后续再次 preflight 仍不能消费该次挑战放行 | SPEC-MINER-003 |
| 7 | TC-UJ102-03 | PoW 答对后只放行一次 | 已存在待完成的 challenge；miner 提交正确答案 | 正确答题后连续两次调用 preflight | 第一次消耗放行机会并返回 `allowed=true`；第二次必须重新按限流 / PoW 规则判断，不能无限复用 | SPEC-MINER-003, PROTO-MINER-001 |
| 8 | TC-UJ102-04 | 低信用 miner 受同 IP 衰减影响 | 同一 IP 下已存在多个低信用 miner 且都在线 | 某低信用 miner 持续调用 preflight 直到接近上限 | 系统使用衰减后的额度，而不是原始信用额度；达到上限后返回 `rate_limit_exceeded` | SPEC-MINER-002, PROTO-MINER-001 |
| 9 | TC-UJ102-05 | 高信用 miner 不受同 IP 衰减影响 | 同一 IP 下同时存在低信用和高信用 miner | 高信用 miner 调用 preflight | 系统按其原始信用等级额度判断，不套用低信用 miner 的 IP 衰减规则 | SPEC-MINER-002 |
| 10 | TC-UJ102-06 | 超额提交后明确拒绝 | 某 miner 已达到当前 Epoch 提交上限 | 再次调用 preflight | 返回 `allowed=false` 且 `reason=rate_limit_exceeded` 或等价错误；剩余额度为 0 | SPEC-MINER-002 |
| 11 | TC-UJ102-07 | PoW 按 DataSet Schema 分类抽题 | 至少存在两类 Schema 不同的 DataSet；低信用 miner 对不同 DataSet 发起 preflight 且固定命中 PoW | 分别查询 challenge 内容 | 返回 challenge 的题面和校验元数据与目标 DataSet Schema 对应，不会跨 DataSet 错配题库 | SPEC-MINER-003, PROTO-MINER-001 |
| 12 | TC-UJ102-08 | 三类 PoW 题型都可被程序化校验 | 测试环境可固定抽到“结构化提取 / 内容理解 / 格式转换”三类题型 | miner 分别提交正确答案与错误答案 | 每类题型都能稳定判定通过或失败；不会出现需要人工介入的模糊结果 | SPEC-MINER-003, PROTO-MINER-001 |
| 13 | TC-UJ102-09 | 题库轮换后旧答案不能复用 | 某 miner 曾对同类 challenge 答对；测试环境触发题库轮换或版本切换 | 以旧 challenge 的答案回答新 challenge | 系统拒绝复用旧答案；新 challenge 必须按当前题面重新校验 | SPEC-MINER-003, PROTO-MINER-001 |

### 4.3 UJ-103 admin 发起重复爬取校验并完成 Step1/Step2 裁决

旅程目标：  
作为 admin，我要把抽样 Submission 送入 Repeat Crawl 校验，并让系统按协议完成候选人排除、Step 1 / Step 2 裁决和 repeat score 沉淀。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 11 | TC-UJ103-01 | 创建 Step 1 任务时排除原始提交者和同 IP miner | 存在原始提交 miner、若干在线候选 miner；其中部分与原始提交者同 IP | admin 调 `POST /api/v1/repeat-crawl-tasks` 创建任务 | 返回的 `assigned_miner_id` 不能是原始提交者，也不能是与原始提交者同 IP 的 miner | SPEC-REPEAT-001, PROTO-REPEAT-001 |
| 12 | TC-UJ103-02 | 无可用候选人时任务进入等待状态 | 只有原始提交者或同 IP miner 在线 | admin 创建任务 | 任务不会错误指派，状态为 `waiting_candidate` 或等价待分配状态 | SPEC-REPEAT-001 |
| 13 | TC-UJ103-03 | 被指派 miner 可以成功 claim 任务 | 已存在 `pending_claim` 的 Repeat Task；被指派 miner 在线且持有正确 token | 调 `POST /api/v1/repeat-crawl-tasks/claim` | 返回 `200`；任务进入 `claimed`；lease 生效 | SPEC-HTTP-001, SPEC-REPEAT-001 |
| 14 | TC-UJ103-04 | 非指派 miner 不能 report 结果 | 已有被其他 miner claim 的任务 | 非指派 miner 调 `POST /api/v1/repeat-crawl-tasks/{id}/report` | 请求被拒绝，不能篡改任务结果 | SPEC-AUTH-001, SPEC-REPEAT-002 |
| 15 | TC-UJ103-05 | Step 1 一致时直接通过 | Step 1 任务已 claim；上报结果与原始 `cleaned_data` 相似度达到 `consistency_threshold` | 被指派 miner 上报结果 | 任务直接标记通过，不生成 Step 2；repeat score 被记录 | SPEC-REPEAT-002, SPEC-REPEAT-003, PROTO-REPEAT-001 |
| 16 | TC-UJ103-06 | Step 1 不一致时生成 Step 2 | Step 1 任务已 claim；上报结果与原始结果不一致 | 被指派 miner 上报结果 | 原任务进入 `pending_step_two`；系统新建 Step 2 任务，且继续应用排除规则 | SPEC-REPEAT-002 |
| 17 | TC-UJ103-07 | Step 2 裁决原始提交造假 | 已存在 Step 2 任务；`M1` 与 `M2` 构成一致对而 `M0` 不在一致对中 | Step 2 结果上报完成 | Phase A 结果标记为失败；原始 Submission 对应 `miner_score=0` 或等价失败分数 | SPEC-REPEAT-002, PROTO-REPEAT-001 |
| 18 | TC-UJ103-08 | Step 2 命中动态阈值但无稳定一致对 | 已存在 Step 2 任务；三方结果没有稳定一致对，但最高相似度达到动态阈值 | 完成 Step 2 上报 | 系统进入动态阈值分支，输出通过或无效结果，不应错误落入“原始提交造假” | SPEC-REPEAT-002 |
| 19 | TC-UJ103-09 | lease 超时后任务允许重新 claim | 任务已被 claim 但未在 TTL 内完成；时间推进到 lease 过期之后 | 候选 miner 再次 claim | 任务可以重新进入可领取状态；旧 lease 不应永久锁死任务 | SPEC-REPEAT-001, PROTO-RUNTIME-001 |

### 4.4 UJ-104 validator 进入 ready_pool 并完成单评估 / 降级评估

旅程目标：  
作为 validator，我要在满足资格和最小间隔约束后进入 ready_pool，并让 admin 发起的评估任务按单评估或降级评估规则派发给我。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 20 | TC-UJ104-01 | 合格 validator 可进入 ready_pool | validator 已存在有效档案，`eligible=true`，且满足最小任务间隔 | 调 `POST /api/v1/validators/ready` | 返回成功；validator 进入 ready_pool | SPEC-VAL-001, PROTO-VAL-001 |
| 21 | TC-UJ104-02 | 不具资格 validator 不能入池 | validator 存在但 `eligible=false` | 调 `POST /api/v1/validators/ready` | 请求被拒绝；validator 不进入 ready_pool | SPEC-VAL-001 |
| 22 | TC-UJ104-03 | 未达到最小任务间隔时不能入池 | validator 刚完成上一任务，尚未满足 credit 对应的最小间隔 | 调 `POST /api/v1/validators/ready` | 请求被拒绝；ready_pool 不应错误包含该 validator | SPEC-VAL-001 |
| 23 | TC-UJ104-04 | 单评估模式可成功派发 | ready_pool 至少有 1 个合格 validator；admin Bearer Token 可用 | admin 调 `POST /api/v1/evaluation-tasks` 创建评估任务；validator 再 claim | 任务以单评估模式派发；被选中的 validator 可 claim 成功 | SPEC-VAL-002, SPEC-HTTP-001 |
| 24 | TC-UJ104-05 | Peer Review 可用人数不足时降级为单评估 | 任务命中 Peer Review，但 ready_pool 中可用 validator 少于 5 个 | admin 创建评估任务 | 系统降级为单评估，而不是创建无法完成的 Peer Review 任务 | SPEC-VAL-002, PROTO-VAL-001 |
| 25 | TC-UJ104-06 | ready_pool 为空时评估任务进入等待队列 | 当前没有可用 validator 入池；admin Bearer Token 可用 | admin 创建评估任务 | 任务进入等待状态；不会错误分配给不在池中的 validator | SPEC-VAL-002, PROTO-VAL-001, PROTO-RUNTIME-001 |
| 26 | TC-UJ104-07 | 等待中的评估任务会在 validator 入池后自动消费 | 已存在等待中的评估任务；某合格 validator 在稍后满足间隔并入池 | validator 调 `POST /api/v1/validators/ready` 或系统自动回池 | 任务被自动派发并进入可 claim / 已分配状态 | SPEC-VAL-001, SPEC-VAL-002, PROTO-VAL-001 |
| 27 | TC-UJ104-08 | validator 完成任务并过了间隔后可重新入池 | validator 刚完成一次评估并已被移出 ready_pool；测试时钟可推进 | 时间推进到最小间隔之后再次入池或观察自动回池 | validator 重新成为可分配候选，而不是永久离池 | SPEC-VAL-001, PROTO-VAL-001 |
| 28 | TC-UJ104-09 | 错误角色不能 claim 或 report 评估任务 | 服务已启动；存在 `miner` / `admin` token | 非 validator 主体调用评估 claim/report 接口 | 请求被拒绝，返回 `403` 或等价授权失败 | SPEC-AUTH-001, SPEC-HTTP-001 |

### 4.5 UJ-105 peer review / golden task 完成后沉淀评分与准确率

旅程目标：  
作为 admin 和 validator，我要让系统在 Peer Review 与 Golden Task 路径中正确沉淀 `miner_score`、`accuracy` 和 `peer_review_accuracy`。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 29 | TC-UJ105-01 | Peer Review 以中位数生成 miner_score | 已成功创建 Peer Review 任务；5 个 validator 都完成评分 | 完成全部 report 后查询任务或 Epoch 快照 | 任务 `miner_score` 取 5 个分数的中位数，而不是平均值或最后一个分数 | SPEC-VAL-003, PROTO-VAL-001 |
| 30 | TC-UJ105-02 | Golden Task 以 RMSE 计算 golden_accuracy | 同一 validator 在一个 Epoch 内完成多次 Golden Task，且正确答案已知 | 查询该 validator 的 Epoch 快照 | `golden_accuracy = 1 - sqrt(avg((v_score - correct_score)^2)) / 100`；不会退化为简单平均偏差 | SPEC-VAL-003, SPEC-EPOCH-002, PROTO-VAL-001, PROTO-EPOCH-001 |
| 31 | TC-UJ105-03 | Peer Review 以 RMSE 计算 peer_review_accuracy | Peer Review 任务全部完成，且某 validator 参与了多次 Peer Review | 查询该 validator 的 Epoch 快照 | `peer_review_accuracy = 1 - sqrt(avg(peer_deviation^2)) / 100`；不会退化为单次偏差或线性平均 | SPEC-VAL-003, SPEC-EPOCH-002, PROTO-VAL-001, PROTO-EPOCH-001 |
| 32 | TC-UJ105-04 | 最终 accuracy 按 golden 与 peer review 1:1 综合 | 同一 validator 在本 Epoch 同时拥有充足的 Golden 与 Peer Review 样本 | 查询 Epoch 快照 | `accuracy = (golden_accuracy + peer_review_accuracy) / 2` | SPEC-EPOCH-002, PROTO-EPOCH-001, PROTO-VAL-001 |
| 33 | TC-UJ105-05 | 单边样本不足时使用协议 fallback | 某 validator 在本 Epoch 只有 Golden Task 样本或只有 Peer Review 样本，另一侧样本数不足 2 | 查询 Epoch 快照 | `accuracy` 仅取有足够样本的一侧；两侧都不足时不进行 accuracy 判定 | SPEC-EPOCH-002, PROTO-EPOCH-001, PROTO-VAL-001 |
| 34 | TC-UJ105-06 | Peer Review 更新 peer_review_accuracy | Peer Review 任务全部完成 | 系统计算相对共识偏差 | 每个 validator 都产生相对共识的偏差输入，并沉淀到 `peer_review_accuracy` | SPEC-VAL-003, SPEC-EPOCH-002 |
| 35 | TC-UJ105-07 | Peer Review 的 5 个 validator 互不可见评分 | 已成功创建 Peer Review 任务；5 个 validator 分别 claim 同一评估包 | 任一 validator 在 report 前查询任务详情或其他 report 结果 | 其只能看到自身任务上下文，不能看到其他 validator 的评分结果或共识分 | SPEC-VAL-002, SPEC-VAL-003, PROTO-VAL-001 |
| 36 | TC-UJ105-08 | validator 完成任务后更新最后完成时间与 eval_count | 任一 validator 成功完成一次 report | report 完成后查询 validator 相关快照 | `last_task_completed_at` 更新；对应 Epoch 的 `eval_count` 增加 | SPEC-VAL-001, SPEC-EPOCH-002 |
| 37 | TC-UJ105-09 | 普通单评估与 Golden Task 统计口径分离 | 同一 validator 同时经历普通单评估和 Golden Task | 完成两类任务后查询快照 | 普通单评估不会错误写入 Golden accuracy；Golden Task 才更新已知答案准确率输入 | SPEC-VAL-003 |

### 4.6 UJ-106 admin 查询 epoch 快照并确认统计结果可用于结算

旅程目标：  
作为 admin，我要确认 Mining Service 的运行指标聚合正确，且能在结算前明确看到 miner / validator 的统计结果。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 38 | TC-UJ106-01 | admin 可查询指定 Epoch 快照 | 已存在某个 Epoch 的 Repeat / Evaluation 统计数据；admin Bearer Token 可用 | 调 `GET /api/v1/epochs/{id}/snapshot` | 返回 `200`；响应包含 Miner 与 Validator 聚合指标；字段契约稳定 | SPEC-EPOCH-003, SPEC-HTTP-001 |
| 39 | TC-UJ106-02 | avg_score 使用 3:2 权重公式 | 某 miner 在同一 Epoch 同时拥有 sampled score 和 repeat score | 查询 Epoch 快照 | 返回的 `avg_score` 按 sampled:repeat=`3:2` 计算 | SPEC-EPOCH-001, PROTO-EPOCH-001 |
| 40 | TC-UJ106-03 | 样本数少于 3 时应用 70 分保护 | 某 miner 的总评估条目数少于 3 且实际均分低于 70 | 查询 Epoch 快照 | `avg_score` 取 `max(actual,70)`，而不是直接返回低分 | SPEC-EPOCH-001 |
| 41 | TC-UJ106-04 | eval_count 不足时 consecutive_idle 递增 | 某 validator 在该 Epoch 的 `eval_count` 低于最低工作量要求 | 查询 Epoch 快照 | `consecutive_idle` 相比前值递增 1 | SPEC-EPOCH-002, PROTO-EPOCH-001 |
| 42 | TC-UJ106-05 | 达到最低工作量时 consecutive_idle 清零 | 某 validator 在该 Epoch 已满足最低工作量 | 查询 Epoch 快照 | `consecutive_idle=0` 或被清零，而不是继续沿用旧值 | SPEC-EPOCH-002 |

### 4.7 UJ-107 被指派 miner 完成 refresh task，并让新版本进入正常评估链路

旅程目标：  
作为被协调器选中的 miner，我要领取刷新任务、重新爬取过期 URL，并让新版本 Submission 进入正常 Phase A / Phase B 评估和统计沉淀。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 43 | TC-UJ107-01 | 创建 refresh task 时排除历史提交者和同 IP miner | 某 URL 已有历史 confirmed 记录且达到 refresh_interval；存在多名在线 miner，其中包含历史提交者及其同 IP miner | 上游触发 refresh task 分配 | 被选中的 `assigned_miner_id` 不能是历史提交者，也不能是同 IP miner | PROTO-REFRESH-001, PROTO-RUNTIME-001 |
| 44 | TC-UJ107-02 | 被指派 miner 可以成功 claim refresh task | 已存在 `pending_claim` 的 refresh task；被指派 miner 在线且持有正确 token | 调 `POST /api/v1/refresh-tasks/claim` | 返回 `200`；任务进入 `claimed`；lease 生效 | SPEC-HTTP-001, SPEC-AUTH-001, PROTO-REFRESH-001 |
| 45 | TC-UJ107-03 | 非指派 miner 不能 claim 或 report refresh task | 已存在分配给其他 miner 的 refresh task | 非指派 miner 尝试 claim 或 report | 请求被拒绝；不会篡改任务归属和结果 | SPEC-AUTH-001, PROTO-REFRESH-001 |
| 46 | TC-UJ107-04 | refresh 结果失败后任务可重新分配 | 某 refresh task 已被 claim，但上报失败或 lease 超时 | 其他候选 miner 再次 claim | 任务回到待分配或重新分配状态，不会永久卡死 | PROTO-REFRESH-001, PROTO-RUNTIME-001 |
| 47 | TC-UJ107-05 | refresh 产出的新 Submission 进入正常评估链路 | 某 refresh task 已成功 report 出新版本数据 | 系统创建后续任务并查询状态 | 新 Submission 会进入正常 Repeat / Evaluation 工作流，而不是停留在 refresh 任务内部 | PROTO-REFRESH-001, PROTO-REPEAT-001, PROTO-VAL-001 |
| 48 | TC-UJ107-06 | refresh task 计入 miner 的 task_count | 某 miner 在一个 Epoch 内成功完成至少一次 refresh task | 查询 Epoch 快照 | 对应 miner 的 `task_count` 增加，refresh 任务不会被漏记 | SPEC-EPOCH-001, PROTO-REFRESH-001, PROTO-EPOCH-001 |

### 4.8 UJ-108 运维确认服务存活、鉴权边界与观测性

旅程目标：  
作为运维，我要确认 Mining Service 的健康状态、权限边界和日志指标都正常，这样线上故障可以被快速发现和定位。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 49 | TC-UJ108-01 | 健康检查与就绪检查正确 | 服务已启动；依赖正常 | 调 `GET /healthz` 与 `GET /readyz` | `healthz` 返回存活；`readyz` 返回 ready | SPEC-HTTP-001 |
| 50 | TC-UJ108-02 | 受保护接口的鉴权边界正确 | 服务已启动；同时准备无 token 与错误角色请求 | 调任一受保护业务接口 | 无 token 返回 `401`；错误角色返回 `403` | SPEC-HTTP-001, SPEC-AUTH-001 |
| 51 | TC-UJ108-03 | 成功与失败响应、日志和指标都可观测 | 已完成至少一轮成功与失败请求 | 检查响应 envelope、日志输出和 `GET /metrics` | 成功响应 `success=true`；失败响应 `success=false`；都带 `meta.request_id`；日志含 `request_id/subject/role`；指标暴露 HTTP 请求数据 | SPEC-HTTP-001, SPEC-AUTH-001 |

### 4.9 UJ-201 管理员确保 core 侧 submission 进入完整质检与结算链路

旅程目标：  
作为平台管理员，我要确保来自 Core Service 的 submission 能进入 Mining Service 的完整质检与结算链路；无论是新 submission 还是 refresh 后的新版本，都应继续进入 repeat crawl、evaluation 和 epoch 聚合。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 52 | TC-UJ201-01 | core 侧已激活 dataset 可产生新 submission 供 mining 使用 | Core Service 与 Mining Service 都已启动；core admin / miner token 可用 | 在 Core Service 创建 dataset、激活并提交一条新 submission | 生成稳定的 `submission_id`，可作为 mining 侧跨服务输入 | SPEC-HTTP-001 |
| 53 | TC-UJ201-02 | 新 submission 可进入 repeat crawl 链路 | 已存在 core 侧新 submission；mining 侧有可用在线 miner | admin 调 `POST /api/v1/core-submissions/{id}/repeat-crawl-tasks`，随后被指派 miner claim/report | Repeat Task 创建成功，并按 mining 协议完成 claim/report | SPEC-HTTP-001, SPEC-REPEAT-001, PROTO-REPEAT-001 |
| 54 | TC-UJ201-03 | 新 submission 可进入 evaluation 链路 | 已存在 core 侧新 submission；mining 侧有可用 validator | admin 调 `POST /api/v1/core-submissions/{id}/evaluation-tasks`，随后 validator claim/report | Evaluation Task 创建成功，并进入正常评分链路 | SPEC-HTTP-001, SPEC-VAL-001, SPEC-VAL-002 |
| 55 | TC-UJ201-04 | 新 submission 链路结果会沉淀到 epoch 快照 | 新 submission 的 repeat / evaluation 都已完成 | admin 查询 `GET /api/v1/epochs/{id}/snapshot` | 返回的 miner / validator 指标包含这条新 submission 触发的沉淀结果 | SPEC-EPOCH-001, SPEC-EPOCH-002, SPEC-EPOCH-003 |
| 56 | TC-UJ201-05 | core 侧历史 submission 可触发 refresh | Core Service 与 Mining Service 都已启动；core admin / miner token 可用 | 在 Core Service 创建 dataset、激活并提交一条历史 submission | 生成可用于 refresh 的原始 URL 与 submission 输入 | SPEC-HTTP-001 |
| 57 | TC-UJ201-06 | refresh 后的新 submission 会继续进入完整质检链路 | 已存在 core 侧历史 submission；mining 侧 miner / validator 可用 | admin 在 mining 创建 refresh task，随后执行 downstream repeat 与 evaluation | 新 submission 不停留在 refresh 内部，而是继续进入 Phase A / Phase B 主链路 | SPEC-HTTP-001, PROTO-REFRESH-001, PROTO-REPEAT-001, PROTO-VAL-001 |
| 58 | TC-UJ201-07 | refresh 路径结果也会沉淀到 epoch 快照 | Refresh → Repeat → Evaluation 已完整完成 | admin 查询 `GET /api/v1/epochs/{id}/snapshot` | 返回的 `task_count / eval_count` 包含 refresh 路径的沉淀结果 | SPEC-EPOCH-001, SPEC-EPOCH-002, SPEC-EPOCH-003 |

### 4.10 UJ-202 admin 获取某个 Epoch 的最终结算结果，作为奖励结算与风控判断依据

旅程目标：  
作为 admin，我要在某个 `epoch_id` 完成结算后获取 miner 和 validator 的最终结果，用于后续奖励结算、风险识别和异常核查。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 59 | TC-UJ202-01 | 手动触发结算后可获取 miner 最终结果 | 某个 `epoch_id` 已有完整的 repeat / evaluation 输入，且 Core Service 已对该 `epoch_id` 成功执行 settle | admin 查询该 `epoch_id` 在 Mining 侧的结果视图 | 返回结果包含 miner 级 `qualified/weight/reward_amount/confirmed_submission_count/rejected_submission_count`，可直接用于奖励结算核对 | SPEC-EPOCH-001, SPEC-EPOCH-003 |
| 60 | TC-UJ202-02 | 手动触发结算后可获取 validator 最终结果 | 某个 `epoch_id` 已完成 settle，且 validator 侧存在 Golden / Peer Review 或处罚相关输入 | admin 查询该 `epoch_id` 在 Mining 侧的结果视图 | 返回结果包含 validator 级 `qualified/reward_amount/slashed_amount/redistributed_amount/penalty_reason`，可直接用于风控与处罚判断 | SPEC-EPOCH-002, SPEC-EPOCH-003 |
| 61 | TC-UJ202-03 | 重复 settle 或失败重试不会让最终结果重复累计 | 同一 `epoch_id` 已完成一次结算，或经历过 failed 后 retry 成功 | 对同一 `epoch_id` 再次触发 settle，随后查询 Mining 侧结果 | 最终 reward / slash / confirmed / rejected 输出保持稳定，不会因重复触发而翻倍 | SPEC-EPOCH-001, SPEC-EPOCH-002, SPEC-EPOCH-003 |
| 62 | TC-UJ202-04 | UTC 自动结算完成后同样可获取最终结果 | 某个 `epoch_id` 通过自动 UTC 结算而不是人工触发完成 | admin 查询该 `epoch_id` 在 Mining 侧的结果视图 | 自动结算产出的最终结果与手动 settle 一样可查询、可用于奖励结算与风控判断 | SPEC-EPOCH-001, SPEC-EPOCH-002, SPEC-EPOCH-003 |
| 63 | TC-UJ202-05 | 空 Epoch 完成后返回空结果而不是未处理状态 | 某个 `epoch_id` 没有 miner / validator 统计输入，但已经被系统处理完成 | admin 查询该 `epoch_id` 的最终结果 | 返回空集合或零值结果，并能明确区分“已完成但为空”与“尚未处理” | SPEC-EPOCH-003 |

## 5. 状态迁移断言清单

这部分不对应单独 UJ，但每条自动化测试都应尽量覆盖：

- Miner 在线状态：`online -> offline`
- Repeat Task：`pending_claim -> claimed -> completed` 或 `pending_claim -> waiting_candidate`
- Refresh Task：`pending_claim -> claimed -> completed` 或 `pending_claim -> reassigned`
- Repeat Step 1：`pending -> passed` 或 `pending -> pending_step_two`
- Evaluation Task：`pending_reports -> completed`
- Validator ready_pool：`not_ready -> ready -> removed_after_assignment -> ready_again`
- Epoch 指标：随任务完成持续累加，而不是只在查询时临时拼装

## 6. 持久化与恢复断言清单

这些建议作为仓储集成测试和服务重启测试补充：

- PostgreSQL 快照保存后可完整恢复 `miners/validators/pow_challenges/repeat_crawl_tasks/refresh_tasks/evaluation_tasks/evaluation_assignments/epoch_snapshots`
- Redis 运行态正确承载：
  - 心跳 TTL
  - 在线集合
  - ready_pool
  - 任务 lease
  - 提交计数器
  - PoW 放行 grant
- 服务重启后：
  - PostgreSQL 中的业务真相可恢复
  - Redis 中短期运行态按实际剩余 TTL 或重建逻辑生效

## 7. 自动化分层建议

- 单元测试：
  - 相似度计算
  - 信用分额度
  - IP 衰减
  - PoW 放行一次性语义
  - PoW 题型校验与题库轮换
  - Epoch 聚合公式
- 服务集成测试：
  - Postgres 快照仓储 round-trip
  - Redis TTL / ready_pool / lease / counter / waiting_queue 语义
- HTTP E2E：
  - `UJ-101`、`UJ-102`、`UJ-103`、`UJ-104`、`UJ-105`、`UJ-106`、`UJ-107`、`UJ-108`
- 跨服务联调 E2E：
  - `UJ-201`
  - `UJ-202`
  - 从 Core Service 拉 `submission + dataset schema`
  - 从 Core Service 拉取过期 URL / refresh assignment 输入
  - 基于 Core Submission 创建 Repeat / Evaluation 主链路
  - 验证 refresh 产出的新 Submission 能接上 Mining 侧 Phase A / Phase B
  - 查询 Mining Epoch 快照确认沉淀结果
  - 查询某个已完成结算 `epoch_id` 的最终结果，确认奖励与风控字段已可消费

## 8. 建议的自动化落地方式

- 当前 Mining E2E 统一位于 `apps/platform-service/test/e2e/mining`
- 建议测试文件按旅程分组：
  - `journey_miner_runtime_test.go`
  - `journey_repeat_crawl_test.go`
  - `journey_validator_assignment_test.go`
  - `journey_refresh_task_test.go`
  - `journey_epoch_operability_test.go`
  - `journey_core_integration_test.go`
- 每组测试内部继续使用 `TC-UJxxx-yy` 编号，保持文档与自动化编号一致
