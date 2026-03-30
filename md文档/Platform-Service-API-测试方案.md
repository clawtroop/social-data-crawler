# Platform Service API 测试方案

> 基于 Swagger UI 完整接口文档更新
> 日期：2026-03-29
> 来源：`http://101.47.73.95/swagger/index.html` (浏览器缓存)

---

## 0. 环境现状

| 项目 | 状态 |
|------|------|
| Base URL | `http://101.47.73.95` |
| `/healthz` | 200, `"ok"` |
| `/readyz` | 200, `"ready"` |
| `/swagger/index.html` | 404 (服务端已移除，浏览器有缓存) |
| 鉴权模式 | **auth-disabled** — 自动使用 `auth-disabled-miner` / `auth-disabled-validator` |
| Authorization Header | `PLATFORM_SERVICE_JWT_SECRET_TEST` (Swagger 默认值) |

---

## 1. 完整 API 清单 (37 个接口)

### 1.1 Core 模块 (16 个)

| # | Method | Path | 说明 | 需鉴权 |
|---|--------|------|------|--------|
| C1 | GET | `/api/core/v1/datasets` | 数据集列表 | - |
| C2 | POST | `/api/core/v1/datasets` | 创建数据集 | Y |
| C3 | GET | `/api/core/v1/datasets/{id}` | 数据集详情 | - |
| C4 | POST | `/api/core/v1/datasets/{id}/activate` | 激活数据集 | Y |
| C5 | GET | `/api/core/v1/epochs` | Epoch 列表 | Y |
| C6 | GET | `/api/core/v1/epochs/{epochID}` | Epoch 详情 | Y |
| C7 | POST | `/api/core/v1/epochs/{epochID}/settle` | Epoch 结算 | Y |
| C8 | GET | `/api/core/v1/submissions` | 提交列表 | Y |
| C9 | POST | `/api/core/v1/submissions` | 创建提交 | Y |
| C10 | GET | `/api/core/v1/submissions/{id}` | 提交详情 | Y |
| C11 | GET | `/api/core/v1/url-occupancies` | URL 占位列表 | Y |
| C12 | GET | `/api/core/v1/url-occupancies/check` | URL 占位检查 | - |
| C13 | GET | `/api/core/v1/url-occupancies/{datasetId}/{urlHash}` | URL 占位详情 | Y |
| C14 | GET | `/api/core/v1/validation-results` | 验证结果列表 | Y |
| C15 | POST | `/api/core/v1/validation-results` | 提交验证结果 | Y |
| C16 | GET | `/api/core/v1/validation-results/{id}` | 验证结果详情 | Y |

### 1.2 Mining 模块 (19 个)

| # | Method | Path | 说明 | 需鉴权 |
|---|--------|------|------|--------|
| M1 | POST | `/api/mining/v1/core-submissions/{id}/evaluation-tasks` | 从提交创建评估任务 | Y |
| M2 | POST | `/api/mining/v1/core-submissions/{id}/repeat-crawl-tasks` | 从提交创建复核任务 | Y |
| M3 | GET | `/api/mining/v1/epochs/{id}/settlement-results` | Epoch 结算结果 | Y |
| M4 | GET | `/api/mining/v1/epochs/{id}/snapshot` | Epoch 快照 | Y |
| M5 | POST | `/api/mining/v1/evaluation-tasks` | 创建评估任务 | Y |
| M6 | POST | `/api/mining/v1/evaluation-tasks/claim` | 领取评估任务 | Y |
| M7 | POST | `/api/mining/v1/evaluation-tasks/{id}/report` | 上报评估结果 | Y |
| M8 | POST | `/api/mining/v1/miners/heartbeat` | Miner 心跳 | Y |
| M9 | GET | `/api/mining/v1/miners/online` | 在线 Miner 列表 | - |
| M10 | POST | `/api/mining/v1/miners/preflight` | 提交预检 | Y |
| M11 | POST | `/api/mining/v1/pow-challenges/{id}/answer` | PoW 答题 | Y |
| M12 | POST | `/api/mining/v1/refresh-tasks` | 创建刷新任务 | Y |
| M13 | POST | `/api/mining/v1/refresh-tasks/claim` | 领取刷新任务 | Y |
| M14 | POST | `/api/mining/v1/refresh-tasks/{id}/report` | 上报刷新结果 | Y |
| M15 | POST | `/api/mining/v1/repeat-crawl-tasks` | 创建复核任务 | Y |
| M16 | POST | `/api/mining/v1/repeat-crawl-tasks/claim` | 领取复核任务 | Y |
| M17 | POST | `/api/mining/v1/repeat-crawl-tasks/{id}/report` | 上报复核结果 | Y |
| M18 | POST | `/api/mining/v1/validators/heartbeat` | Validator 心跳 | Y |
| M19 | POST | `/api/mining/v1/validators/ready` | Validator 就绪 | Y |

### 1.3 平台公共接口 (2 个)

| # | Method | Path | 说明 | 需鉴权 |
|---|--------|------|------|--------|
| P1 | GET | `/healthz` | 健康检查 | - |
| P2 | GET | `/readyz` | 就绪检查 | - |

---

## 2. 数据模型 (从 Swagger Models 提取)

### 2.1 Core Domain

| Model | 说明 |
|-------|------|
| `Dataset` | 数据集定义 |
| `DatasetSchema` | 数据集字段 schema |
| `DatasetStatus` | 数据集状态枚举 |
| `Epoch` | Epoch 定义 |
| `EpochStatus` | Epoch 状态枚举 |
| `EpochSummary` | Epoch 统计摘要 |
| `Submission` | 数据提交 |
| `SubmissionStatus` | 提交状态枚举 |
| `UrlOccupancy` | URL 占位记录 |
| `OccupancyCheck` | URL 占位检查结果 |
| `ValidationResult` | 验证结果 |
| `ValidationVerdict` | 验证结论枚举 |
| `SchemaField` / `FieldType` | Schema 字段定义 |

### 2.2 Mining Domain

| Model | 说明 |
|-------|------|
| `MinerOnlineState` | Miner 在线状态 |
| `MinerRecord` | Miner 记录 |
| `MinerEpochSnapshot` | Miner 周期快照 |
| `MinerSettlementResult` | Miner 结算结果 |
| `ValidatorRecord` | Validator 记录 |
| `ValidatorEpochSnapshot` | Validator 周期快照 |
| `ValidatorSettlementResult` | Validator 结算结果 |
| `PoWChallenge` | PoW 挑战 |
| `PoWChallengeResult` | PoW 挑战结果 |
| `SubmissionPreflightResult` | 提交预检结果 |
| `EvaluationTask` | 评估任务 |
| `EvaluationAssignment` | 评估任务分配 |
| `EvaluationMode` | 评估模式枚举 |
| `RepeatCrawlTask` | 复核任务 |
| `RefreshTask` | 刷新任务 |
| `PhaseAResult` | 阶段 A 结果 |
| `EpochSnapshot` | Epoch 快照 |
| `EpochSettlementResults` | Epoch 结算结果 |

### 2.3 Request Models

| Model | 用于接口 |
|-------|---------|
| `CreateDatasetRequest` | POST /datasets |
| `CreateSubmissionsRequest` | POST /submissions |
| `CreateSubmissionEntryRequest` | 提交条目 |
| `CreateValidationResultRequest` | POST /validation-results |
| `MinerHeartbeatRequest` | POST /miners/heartbeat |
| `ValidatorHeartbeatRequest` | POST /validators/heartbeat |
| `SubmitPreflightRequest` | POST /miners/preflight |
| `AnswerPoWRequest` | POST /pow-challenges/{id}/answer |
| `CreateEvaluationTaskInput` | POST /evaluation-tasks |
| `CreateEvaluationTaskFromCoreRequest` | POST /core-submissions/{id}/evaluation-tasks |
| `CreateRepeatCrawlTaskInput` | POST /repeat-crawl-tasks |
| `CreateRepeatTaskFromCoreRequest` | POST /core-submissions/{id}/repeat-crawl-tasks |
| `CreateRefreshTaskInput` | POST /refresh-tasks |
| `ReportEvaluationTaskRequest` | POST /evaluation-tasks/{id}/report |
| `ReportTaskRequest` | POST /repeat-crawl-tasks/{id}/report, /refresh-tasks/{id}/report |

---

## 3. 测试方案：分 Phase 执行

### Phase 1: 数据集管理 (Admin)

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T1.1 | POST /datasets | 创建数据集，传完整 body | 201, `status=pending_review` |
| T1.2 | POST /datasets | body={} | 400, `code=invalid_dataset` |
| T1.3 | GET /datasets | 查询列表 | 200, 包含 T1.1 记录 |
| T1.4 | GET /datasets/{id} | 查询详情 | 200, 字段完整 |
| T1.5 | GET /datasets/nonexistent | 不存在 ID | 404 |
| T1.6 | POST /datasets/{id}/activate | 激活数据集 | 200, `status=active` |
| T1.7 | POST /datasets/{id}/activate | 重复激活 | 200 (幂等) 或 400 |

**CreateDatasetRequest 示例：**
```json
{
  "id": "ds_test_001",
  "name": "Test Dataset",
  "creator": "0xTestAdmin",
  "creation_fee": "10 $AWP",
  "source_domains": ["en.wikipedia.org"],
  "schema": {
    "title": {"type": "string", "required": true},
    "content": {"type": "string", "required": true}
  },
  "refresh_interval": "24h"
}
```

---

### Phase 2: Miner 上线与 PoW

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T2.1 | POST /miners/heartbeat | Miner 心跳 | 200, `online=true` |
| T2.2 | GET /miners/online | 查询在线 Miner | 200, 含心跳 Miner |
| T2.3 | POST /miners/preflight | 提交预检 | 200, 返回 `allowed` 或 `challenge` |
| T2.4 | POST /pow-challenges/{id}/answer | 正确答案 | 200, `passed=true` |
| T2.5 | POST /pow-challenges/{id}/answer | 错误答案 | 200, `passed=false` |
| T2.6 | POST /pow-challenges/{id}/answer | 过期 challenge | 错误/过期提示 |
| T2.7 | POST /miners/preflight | PoW 通过后 | 200, `allowed=true` |

**PoW 流程：**
```
preflight → challenge_id + prompt
→ 根据 prompt 计算 answer
→ POST /pow-challenges/{id}/answer {"answer": "..."}
→ passed=true → 允许提交一次
```

---

### Phase 3: 数据提交 (Submission)

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T3.1 | GET /url-occupancies/check | 检查未占用 URL | 200, `occupied=false` |
| T3.2 | POST /submissions | 创建提交 | 201, `status=pending` |
| T3.3 | GET /url-occupancies/check | 检查已占用 URL | 200, `occupied=true` |
| T3.4 | POST /submissions | 重复 URL | 被拒绝或去重 |
| T3.5 | GET /submissions | 查询列表 | 200, 含新提交 |
| T3.6 | GET /submissions/{id} | 查询详情 | 200, 字段完整 |
| T3.7 | GET /submissions?dataset_id=X | 按数据集过滤 | 200, 只返回对应记录 |
| T3.8 | POST /submissions | body={} | 400, `code=malformed_submission` |

**CreateSubmissionsRequest 示例：**
```json
{
  "dataset_id": "ds_posts",
  "entries": [
    {
      "url": "https://en.wikipedia.org/wiki/AI",
      "data": {
        "title": "Artificial Intelligence",
        "content": "AI is..."
      }
    }
  ],
  "pow_challenge_id": "<已通过的 challenge_id>"
}
```

---

### Phase 4: Validator 验证

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T4.1 | POST /validators/heartbeat | Validator 心跳 | 200, `eligible=true` |
| T4.2 | POST /validators/ready | Validator 就绪 | 200, `status=ready` |
| T4.3 | POST /validation-results | 提交验证结果 | 201 |
| T4.4 | POST /validation-results | 相同 idempotency_key | 返回已有结果，不新增 |
| T4.5 | POST /validation-results | body={} | 400 |
| T4.6 | GET /validation-results | 查询列表 | 200, 含 T4.3 记录 |
| T4.7 | GET /validation-results/{id} | 查询详情 | 200 |

**CreateValidationResultRequest 示例：**
```json
{
  "submission_id": "<submission_id>",
  "verdict": "approved",
  "score": 0.95,
  "idempotency_key": "val_001",
  "comment": "Good quality"
}
```

---

### Phase 5: 任务系统 (3 种任务类型)

#### 5.1 复核任务 (Repeat Crawl)

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T5.1.1 | POST /repeat-crawl-tasks | 创建复核任务 | 201 |
| T5.1.2 | POST /core-submissions/{id}/repeat-crawl-tasks | 从提交创建 | 201 |
| T5.1.3 | POST /repeat-crawl-tasks/claim | 领取任务 | 200, 返回 task_id |
| T5.1.4 | POST /repeat-crawl-tasks/{id}/report | 上报结果 | 200 |

#### 5.2 评估任务 (Evaluation)

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T5.2.1 | POST /evaluation-tasks | 创建评估任务 | 201 |
| T5.2.2 | POST /core-submissions/{id}/evaluation-tasks | 从提交创建 | 201 |
| T5.2.3 | POST /evaluation-tasks/claim | Validator 领取 | 200, 返回 task_id + assignment_id |
| T5.2.4 | POST /evaluation-tasks/{id}/report | 上报评估 | 200 |
| T5.2.5 | POST /evaluation-tasks/claim | 检查 golden 字段 | `golden=true/false` |

#### 5.3 刷新任务 (Refresh)

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T5.3.1 | POST /refresh-tasks | 创建刷新任务 | 201 |
| T5.3.2 | POST /refresh-tasks/claim | 领取任务 | 200 |
| T5.3.3 | POST /refresh-tasks/{id}/report | 上报结果 | 200 |

---

### Phase 6: Epoch 结算

| 测试 | 接口 | 步骤 | 预期 |
|------|------|------|------|
| T6.1 | GET /epochs | 查询 Epoch 列表 | 200 |
| T6.2 | GET /epochs/{epochID} | 查询 Epoch 详情 | 200 |
| T6.3 | GET /epochs/{id}/snapshot | 查看快照 | 200, 含 miners/validators 统计 |
| T6.4 | POST /epochs/{epochID}/settle | 触发结算 | 需有效 epoch_id |
| T6.5 | POST /epochs/invalid/settle | 无效 ID | 400, `code=invalid_epoch` |
| T6.6 | GET /epochs/{id}/settlement-results | 查看结算结果 | 200 |
| T6.7 | GET /submissions/{id} | 结算后查询 | `status` 变为 `confirmed/rejected` |

---

### Phase 7: 端到端集成 (E2E)

```
Admin: 创建数据集 (T1.1) → 激活数据集 (T1.6)
           ↓
Miner: 心跳上线 (T2.1) → preflight (T2.3) → PoW (T2.4)
           ↓
       检查 URL 占位 (T3.1) → 提交数据 (T3.2)
           ↓
Validator: 心跳 (T4.1) → ready (T4.2) → 提交验证结果 (T4.3)
           ↓
Admin: 从提交创建评估任务 (T5.2.2) / 复核任务 (T5.1.2)
           ↓
       Validator 领取+上报评估 (T5.2.3-4)
       Miner 领取+上报复核 (T5.1.3-4)
           ↓
Admin: 触发 Epoch 结算 (T6.4) → 查看结算结果 (T6.6)
           ↓
       验证 Submission 状态变更 (T6.7)
```

---

## 4. 协议差异验证项

| # | 验证点 | 接口 | 验证方法 | 优先级 |
|---|--------|------|---------|--------|
| D1 | `dedup_fields` | POST /datasets | 创建时传入，查询时检查保留 | **高** |
| D2 | `url_patterns` | POST /datasets | 创建时传入，提交不匹配 URL 观察拒绝 | **高** |
| D3 | Submission 状态流转 | T3.2 → T6.7 | pending → confirmed/rejected | **高** |
| D4 | PoW 一次性放行 | T2.4 → T2.7 | 答对后只允许一次提交 | **高** |
| D5 | 任务从提交创建 | M1/M2 | `/core-submissions/{id}/...` 正常工作 | **高** |
| D6 | Evaluation golden task | T5.2.5 | claim 返回 `golden` 字段区分 | **中** |
| D7 | Validator 准入 | T4.1 | `eligible=false` 时阻止后续操作 | **中** |
| D8 | 信用分机制 | T2.1/T4.1 | `credit` 字段变化逻辑 | **低** |

---

## 5. 测试执行脚本

```bash
BASE="http://101.47.73.95"
AUTH="Authorization: PLATFORM_SERVICE_JWT_SECRET_TEST"

# P1: 健康检查
curl -s "${BASE}/healthz" | jq .

# C1: 数据集列表
curl -s -H "${AUTH}" "${BASE}/api/core/v1/datasets" | jq .

# C2: 创建数据集
curl -s -X POST "${BASE}/api/core/v1/datasets" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ds_test_001",
    "name": "Test Dataset",
    "creator": "0xTest",
    "creation_fee": "10 $AWP",
    "source_domains": ["example.com"],
    "schema": {"title": {"type": "string", "required": true}},
    "refresh_interval": "24h"
  }' | jq .

# M8: Miner 心跳
curl -s -X POST "${BASE}/api/mining/v1/miners/heartbeat" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# M10: Preflight
curl -s -X POST "${BASE}/api/mining/v1/miners/preflight" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# M11: PoW Answer (替换 challenge_id)
curl -s -X POST "${BASE}/api/mining/v1/pow-challenges/{challenge_id}/answer" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{"answer": "generic-ready"}' | jq .

# C12: URL 占位检查
curl -s "${BASE}/api/core/v1/url-occupancies/check?url=https://example.com&dataset_id=ds_posts" | jq .

# C9: 创建提交
curl -s -X POST "${BASE}/api/core/v1/submissions" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "ds_posts",
    "entries": [{"url": "https://example.com/page1", "data": {"title": "Test"}}],
    "pow_challenge_id": "<challenge_id>"
  }' | jq .

# M18: Validator 心跳
curl -s -X POST "${BASE}/api/mining/v1/validators/heartbeat" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# M19: Validator Ready
curl -s -X POST "${BASE}/api/mining/v1/validators/ready" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# M6: 领取评估任务
curl -s -X POST "${BASE}/api/mining/v1/evaluation-tasks/claim" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

---

## 6. 测试结果记录模板

```markdown
### T1.1 创建数据集

**请求：**
POST /api/core/v1/datasets
Headers: Authorization: PLATFORM_SERVICE_JWT_SECRET_TEST
Body: { "id": "ds_test_001", ... }

**响应：**
Status: 201
Body: { "data": { "id": "ds_test_001", "status": "pending_review", ... }, "success": true }

**结论：** PASS / FAIL / BLOCKED
**备注：** (差异说明)
```

---

## 7. 已知风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| auth-disabled 模式 | 无法测试角色隔离 | 记录为 "auth-disabled 下通过"，启用鉴权后需重测 |
| Swagger 404 | 无法实时查看接口定义 | 使用浏览器缓存 + 本文档 |
| miner/validator ID 硬编码 | 多角色场景无法真实模拟 | 先验证单角色全流程 |
| Epoch 可能需要时间触发 | 可能无法手动 settle | 检查是否支持手动 settle |
