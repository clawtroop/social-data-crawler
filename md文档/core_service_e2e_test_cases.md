# Core Service E2E 用户旅程测试矩阵

这份文档按两层组织：

- 第一层：用户旅程 `UJ-xxx`，描述真实用户目标
- 第二层：子用例 `TC-UJxxx-yy`，描述该旅程下可独立执行、可独立失败、可独立回归的验收点

这样可以同时满足三件事：

- 保持“以用户旅程为主线”的测试设计
- 保持 Given / When / Then 的系统化表达
- 避免把多个独立验收点塞进一个大用例，导致失败定位困难

## 1. Spec 锚点索引

| 锚点 ID | Spec 文件 | 关键 Requirement / Scenario |
|---|---|---|
| SPEC-API-001 | `c-20260326-core-service-http-postgres-auth/specs/core-http-api/spec.md` | 统一响应封装；DataSet 协议字段；URL 占用预检查 |
| SPEC-AUTH-001 | `c-20260326-core-service-http-postgres-auth/specs/jwt-role-authz/spec.md` | Bearer Token 校验；按角色授权；admin / miner / validator 分工 |
| SPEC-OBS-001 | `c-20260326-core-service-http-postgres-auth/specs/service-runtime-observability/spec.md` | `healthz` / `readyz` / `metrics`；request_id 日志与指标 |
| SPEC-VAL-001 | `c-20260326-core-service-http-postgres-auth/specs/validation-result-settlement/spec.md` | ValidationResult 创建；按验证结果参与结算；幂等 |
| SPEC-DS-001 | `c-20260326-core-service-settlement-loop/specs/dataset-lifecycle/spec.md` | DataSet 创建校验；仅 active DataSet 可接收 Submission |
| SPEC-SUB-001 | `c-20260326-core-service-settlement-loop/specs/submission-ingestion/spec.md` | Submission 以 `pending` 落库；confirmed 才算已发布数据 |
| SPEC-OCC-001 | `c-20260326-core-service-settlement-loop/specs/url-occupancy-control/spec.md` | 规范化 URL 占用；重复 URL 拒绝；rejected 释放占用；confirmed 保留占用 |
| SPEC-EPOCH-001 | `c-20260326-core-service-settlement-loop/specs/epoch-settlement/spec.md` | Epoch 结算；原子更新 Submission 与 Occupancy；幂等 |
| SPEC-EPOCH-002 | `c-20260328-core-service-epoch-automation/specs/core-epoch-automation/spec.md` | `/epochs` 查询/触发；失败重试；空 Epoch；自动 UTC 结算 |
| SPEC-EPOCH-003 | `c-20260328-core-service-epoch-automation/specs/core-submission-epoch-partitioning/spec.md` | `Submission.epoch_id` 固化；refresh / 迟到提交归属规则 |

## 2. 用户旅程总览

| # | 旅程 ID | 用户目标 | 主要参与者 | 子用例数 | 结果类型 |
|---|---|---|---|---|---|
| 1 | UJ-001 | 管理员开通一个可供挖矿的新 DataSet | admin | 3 | 正向主链路前置 |
| 2 | UJ-002 | miner 将一条新 URL 成功提交到已激活 DataSet，并形成占用 | miner | 3 | 正向主链路 |
| 3 | UJ-003 | validator 独立完成一次验证结果提交，并保证重试不重复写入 | validator | 4 | 正向角色旅程 |
| 4 | UJ-004 | admin 发起 Epoch 结算，将通过验证的 Submission 纳入 DataSet 成果 | admin | 5 | 正向主链路 |
| 5 | UJ-005 | admin 结算未通过验证的 Submission，并释放 URL 供重新提交 | admin | 3 | 负向后恢复链路 |
| 6 | UJ-006 | 接入方 / 运维确认服务可用、鉴权有效、越权被拦截、响应与观测信息稳定 | operator, client | 4 | 横切保障链路 |
| 7 | UJ-007 | admin 观测系统在 UTC 跨日后自动补齐上一日 Epoch，并通过 `/epochs` 查看状态 | admin | 1 | 自动化与可观测性 |

## 3. 用户旅程与子用例

### 3.1 UJ-001 管理员开通新 DataSet

旅程目标：
作为 admin，我要创建并激活一个新 DataSet，让 miner 后续可以提交数据。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 1 | TC-UJ001-01 | admin 可成功创建 DataSet | 服务已启动；admin Bearer Token 可用；目标 `dataset_id` 尚不存在 | 调 `POST /api/v1/datasets` 创建 DataSet | 返回 `201` 且 `success=true`；DataSet 初始状态为 `pending_review`；`total_entries=0` | SPEC-AUTH-001, SPEC-DS-001, SPEC-API-001 |
| 2 | TC-UJ001-02 | DataSet 返回模型符合协议字段约定 | DataSet 已创建成功 | 查询创建响应或详情响应 | 返回模型使用 `id` 而不是 `dataset_id`，并包含 `name/creator/creation_fee/status/source_domains/schema/refresh_interval/created_at/total_entries` | SPEC-API-001 |
| 3 | TC-UJ001-03 | 激活后的 DataSet 进入可提交状态 | DataSet 当前为 `pending_review` | 调 `POST /api/v1/datasets/{id}/activate` | 返回 `200`；状态变为 `active`；后续可接收 Submission | SPEC-AUTH-001, SPEC-DS-001 |

### 3.2 UJ-002 miner 提交新 URL 并形成占用

旅程目标：
作为 miner，我要把一条新 URL 提交进已激活的 DataSet，并确保系统为这条 URL 建立独占占用。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 4 | TC-UJ002-01 | 提交前占用检查返回未占用 | 已存在 `active` DataSet；miner Bearer Token 可用；目标 URL 尚无有效占用 | 调 `GET /api/v1/url-occupancies/check` | 返回未占用，且只暴露最小占用判断信息 | SPEC-API-001, SPEC-OCC-001 |
| 5 | TC-UJ002-02 | 合法提交以 `pending` 状态落库 | 提交前检查未占用 | 调 `POST /api/v1/submissions` 提交 entries | Submission 创建成功并以 `pending` 状态落库；记录包含 DataSet、Miner、规范化 URL、原始内容和 crawl timestamp | SPEC-AUTH-001, SPEC-DS-001, SPEC-SUB-001 |
| 6 | TC-UJ002-03 | 系统为新提交建立 URL occupancy | 已成功创建 pending Submission | 查询 occupancy / submission | occupancy 已建立并指向该 `pending` Submission；响应仍保持统一 envelope | SPEC-API-001, SPEC-SUB-001, SPEC-OCC-001 |

### 3.3 UJ-003 validator 独立完成验证结果提交

旅程目标：
作为 validator，我要对一条 `pending` Submission 提交验证结果，并在重试时避免重复写入。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 7 | TC-UJ003-01 | validator 首次提交 ValidationResult 成功 | 存在一条 `pending` Submission；validator Bearer Token 可用 | 调 `POST /api/v1/validation-results` 提交合法 `verdict/score/comment/idempotency_key` | 首次提交成功并返回 ValidationResult 资源 | SPEC-AUTH-001, SPEC-VAL-001 |
| 8 | TC-UJ003-02 | ValidationResult 返回字段完整 | ValidationResult 已创建成功 | 检查创建响应 | 结果中包含 `submission_id/validator_id/verdict/score/created_at`，并可选带回 `comment/idempotency_key` | SPEC-VAL-001 |
| 9 | TC-UJ003-03 | validator 写入不会直接改变结算状态 | ValidationResult 已创建；尚未执行 Epoch 结算 | 查询对应 Submission | Submission 仍保持 `pending`，证明 validator 写入不会直接修改结算状态 | SPEC-VAL-001, SPEC-SUB-001 |
| 10 | TC-UJ003-04 | 幂等重试与角色边界正确 | 已存在相同 `idempotency_key` 的 ValidationResult；同时准备非 validator 角色 token | validator 用相同 `idempotency_key` 重试；再由非 validator 角色写入 | 重试时返回已存在结果而不新增记录；非 validator 角色写入被拒绝 | SPEC-AUTH-001, SPEC-VAL-001 |

### 3.4 UJ-004 admin 发起 Epoch 结算，将通过验证的 Submission 纳入 DataSet 成果

旅程目标：
作为 admin，我要发起一次 Epoch 结算，让系统消费已有验证结果，把满足确认条件的 `pending` Submission 结算为 `confirmed`，并纳入 DataSet 成果。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 11 | TC-UJ004-01 | 达阈值的 ValidationResult 进入结算输入集 | 存在 `pending` Submission；validator / admin Bearer Token 可用；当前还没有达到阈值的 accepted ValidationResult | validator 提交 `accepted` 且 `score >= threshold` 的结果 | ValidationResult 创建成功，并可被后续 Epoch 结算消费 | SPEC-VAL-001 |
| 12 | TC-UJ004-02 | 系统在 Epoch 中消费验证结果并完成 confirmed 结算 | 已存在达阈值 accepted ValidationResult | admin 调 `POST /api/v1/epochs/{epoch_id}/settle` 发起结算 | Epoch 完成后该 Submission 变为 `confirmed`；`summary.confirmed` 与实际一致 | SPEC-VAL-001, SPEC-EPOCH-001, SPEC-EPOCH-002 |
| 13 | TC-UJ004-03 | confirmed 结算结果进入 DataSet 成果 | Submission 已被结算为 `confirmed` | 查询 DataSet 与 Submission | DataSet 的 `total_entries` 增加；confirmed Submission 被视为已发布数据 | SPEC-SUB-001, SPEC-EPOCH-001 |
| 14 | TC-UJ004-04 | confirmed 结算后的 URL 继续保持占用并阻止重复提交 | 某规范化 URL 已对应 confirmed Submission | 查询 occupancy，并由 miner 再次提交同一规范化 URL | URL occupancy 继续保持有效；重复提交被拒绝，证明 confirmed 会继续锁定 URL | SPEC-OCC-001, SPEC-EPOCH-001 |
| 15 | TC-UJ004-05 | admin 可按 `epoch_id` 查询 Epoch 状态 | 某个 Epoch 已完成结算 | 调 `GET /api/v1/epochs/{epoch_id}` | 返回 `status`、`summary` 与对应 `epoch_id`，无需内部资源 id | SPEC-EPOCH-002 |

### 3.5 UJ-005 admin 结算未通过验证的 Submission，并释放 URL 供重新提交

旅程目标：
作为 admin，我要发起一次 Epoch 结算，让系统把不满足确认条件的 `pending` Submission 结算为 `rejected`，并释放其 URL 占用，使后续 miner 可以重新提交。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 16 | TC-UJ005-01 | 不满足 confirmed 条件的验证结果进入 rejected 结算路径 | 已存在一条新的 `pending` Submission；validator / admin / miner Bearer Token 可用 | validator 提交 `rejected` 或 `accepted` 但 `score < threshold` 的 ValidationResult；admin 发起 Epoch 结算 | 该 Submission 在结算后变为 `rejected`；这一步强调 rejected 是结算结果，而不是验证结果写入的即时效果 | SPEC-VAL-001, SPEC-EPOCH-001, SPEC-EPOCH-002 |
| 17 | TC-UJ005-02 | 系统在 rejected 结算中释放 URL occupancy | 同一 Submission 已在 Epoch 结算后被标记为 `rejected` | 查询 occupancy 或执行占用检查 | 该 URL 的 occupancy 在 rejected 结算中被释放，而不是在 validator 提交结果时立即释放 | SPEC-OCC-001, SPEC-EPOCH-001 |
| 18 | TC-UJ005-03 | rejected 结算后被释放的 URL 可以重新提交 | rejected Submission 对应 URL 已在结算后释放 | miner 对同一规范化 URL 再次提交 | 重提成功，新 Submission 重新进入 `pending` | SPEC-OCC-001, SPEC-EPOCH-001, SPEC-EPOCH-003 |

### 3.6 UJ-006 接入与运维边界保障

旅程目标：
作为外部接入方 / 运维，我要确认服务存活、依赖就绪、统一响应契约稳定、非法请求被正确拦截、日志和指标可追踪。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 19 | TC-UJ006-01 | 健康与就绪接口反映服务可用状态 | 服务已启动；Postgres 已连接 | 调 `GET /healthz` 和 `GET /readyz` | `healthz` 返回进程健康；`readyz` 在依赖正常时返回 ready | SPEC-OBS-001 |
| 20 | TC-UJ006-02 | 认证与授权边界正确 | 服务已启动；存在无 token 与错误角色请求 | 无 token 访问受保护接口；错误角色调用 admin 写接口 | 无 token 请求返回 `401`；错误角色请求返回 `403` | SPEC-AUTH-001, SPEC-OBS-001 |
| 21 | TC-UJ006-03 | 成功与失败响应都符合统一 envelope | 分别存在一个成功请求和一个失败请求 | 检查两类响应 | 成功响应包含 `success=true`；失败响应包含 `success=false`；两类响应都带 `meta.request_id` | SPEC-API-001, SPEC-OBS-001 |
| 22 | TC-UJ006-04 | 指标与日志具备可观测性 | 已完成至少一轮业务请求 | 调 `GET /metrics` 并检查日志 | `metrics` 暴露 HTTP 指标；日志中能关联 request_id 与 principal | SPEC-OBS-001 |

### 3.7 UJ-007 admin 观测自动 UTC 结算结果

旅程目标：
作为 admin，我要在 UTC 跨日后观察系统自动补齐上一日 Epoch，并通过 `/epochs` 查看结算状态和时间戳。

| # | 子用例 ID | 验收点 | GIVEN | WHEN | THEN | Spec 锚点 |
|---|---|---|---|---|---|---|
| 23 | TC-UJ007-01 | 自动结算会补齐上一日 Epoch 并返回完成态 | 已存在归属到上一 UTC 日的 `pending` Submission 与达阈值 ValidationResult | 系统运行自动 catch-up / UTC 结算，再由 admin 调 `GET /api/v1/epochs/{epoch_id}` | 返回 `completed` Epoch；`summary` 与上一日数据一致；`settlement_started_at` / `settlement_completed_at` 可观测 | SPEC-EPOCH-002, SPEC-OBS-001 |

## 4. 建议的自动化落地方式

- 当前已经迁移到 `platform-service` 宿主下运行，用例位于 `apps/platform-service/test/e2e/core`
- 自动化按旅程拆分为 confirmed / rejected / operability 三组测试文件，并在每组内部继续使用 `TC-UJxxx-yy` 编号
- 执行入口统一为 `make e2e-core-service`，底层运行 `cd apps/platform-service && go test ./test/e2e/core -v`
