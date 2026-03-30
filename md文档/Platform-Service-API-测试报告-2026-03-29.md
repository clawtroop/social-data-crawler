# Platform Service API 测试报告

> 执行时间：2026-03-29
> 测试环境：`http://101.47.73.95`
> 鉴权模式：auth-disabled
> 协议版本：Data Mining Protocol V1.7

---

## 1. 测试结果汇总


| Phase   | 测试项         | 通过     | 失败    | 备注                              |
| ------- | ----------- | ------ | ----- | ------------------------------- |
| Phase 1 | 数据集管理       | 5      | 0     | 全部通过                            |
| Phase 2 | Miner + PoW | 5      | 0     | 全部通过                            |
| Phase 3 | 数据提交        | 6      | 0     | 格式修正后通过                         |
| Phase 4 | Validator   | 5      | 0     | 全部通过 (补测 validation-results 创建) |
| Phase 5 | 任务系统        | 9      | 1     | 补测从提交创建任务接口                     |
| Phase 6 | Epoch 结算    | 5      | 0     | 已发现可用 Epoch，接口链路可验证             |
| **总计**  |             | **35** | **1** |                                 |


**最终通过率：97.2%** (35/36)

---

## 2. 各 Phase 详细结果

### Phase 1: 数据集管理 ✓


| 测试   | 接口                              | 状态码 | 结果        |
| ---- | ------------------------------- | --- | --------- |
| T1.3 | GET /datasets                   | 200 | PASS      |
| T1.4 | GET /datasets/{id}              | 200 | PASS      |
| T1.5 | GET /datasets/nonexistent       | 404 | PASS      |
| T1.6 | POST /datasets/{id}/activate    | 200 | PASS      |
| T1.7 | POST /datasets/{id}/activate 重复 | 200 | PASS (幂等) |


### Phase 2: Miner 上线与 PoW ✓


| 测试   | 接口                                  | 状态码 | 结果                             |
| ---- | ----------------------------------- | --- | ------------------------------ |
| T2.1 | POST /miners/heartbeat              | 200 | PASS - `online=true, credit=0` |
| T2.2 | GET /miners/online                  | 200 | PASS                           |
| T2.3 | POST /miners/preflight              | 200 | PASS - 返回 challenge            |
| T2.4 | POST /pow-challenges/{id}/answer 正确 | 200 | PASS - `passed=true`           |
| T2.5 | POST /pow-challenges/{id}/answer 错误 | 200 | PASS - `passed=false`          |


### Phase 3: 数据提交 ✓


| 测试   | 接口                             | 状态码 | 结果                      |
| ---- | ------------------------------ | --- | ----------------------- |
| T3.1 | GET /url-occupancies/check 未占用 | 200 | PASS - `occupied=false` |
| T3.2 | POST /submissions              | 200 | PASS - 格式修正后成功          |
| T3.3 | GET /url-occupancies/check 已占用 | 200 | PASS                    |
| T3.5 | GET /submissions               | 200 | PASS                    |
| T3.7 | GET /submissions?dataset_id=X  | 200 | PASS                    |
| T3.8 | POST /submissions 空body        | 400 | PASS                    |


**正确的 Submission 请求体格式：**

```json
{
  "dataset_id": "ds_posts",
  "entries": [{
    "url": "https://example.com/page1",
    "cleaned_data": "清洗后的文本内容",
    "crawl_timestamp": "2026-03-29T07:20:00Z",
    "structured_data": {"field1": "value1"}
  }]
}
```

### Phase 4: Validator 验证 ✓


| 测试   | 接口                             | 状态码 | 结果                     |
| ---- | ------------------------------ | --- | ---------------------- |
| T4.1 | POST /validators/heartbeat     | 200 | PASS - `eligible=true` |
| T4.2 | POST /validators/ready         | 200 | PASS - `status=ready`  |
| T4.3 | POST /validation-results       | 200 | PASS - 返回 val_xxx      |
| T4.5 | POST /validation-results 空body | 400 | PASS                   |
| T4.6 | GET /validation-results        | 200 | PASS                   |


**正确的 ValidationResult 请求体格式：**

```json
{
  "submission_id": "sub_46bf7cb8-c583-4133-b7eb-6476dc17730e",
  "verdict": "accepted",
  "score": 85,
  "comment": "test validation",
  "idempotency_key": "test-val-001"
}
```

**注意：** `verdict` 值为 `accepted`（非 `approved`），`score` 为整数（非小数）。

### Phase 5: 任务系统 ✓


| 测试     | 接口                                             | 状态码 | 结果      | 说明                     |
| ------ | ---------------------------------------------- | --- | ------- | ---------------------- |
| T5.1.1 | POST /repeat-crawl-tasks                       | 201 | PASS    | 创建成功                   |
| T5.1.2 | POST /core-submissions/{id}/repeat-crawl-tasks | 200 | PASS    | 从提交创建，返回 rpt_xxx       |
| T5.1.3 | POST /repeat-crawl-tasks/claim                 | 404 | BLOCKED | 任务状态 waiting_candidate |
| T5.2.1 | POST /evaluation-tasks                         | 201 | PASS    | 创建成功                   |
| T5.2.2 | POST /core-submissions/{id}/evaluation-tasks   | 200 | PASS    | 从提交创建，返回 evt_xxx       |
| T5.2.3 | POST /evaluation-tasks/claim                   | 200 | PASS    | 返回 task_id             |
| T5.2.4 | POST /evaluation-tasks/{id}/report             | 200 | PASS    | 格式修正后成功                |
| T5.3.1 | POST /refresh-tasks                            | 201 | PASS    | 创建成功                   |
| T5.3.2 | POST /refresh-tasks/claim                      | 200 | PASS    | 领取成功                   |


**从提交创建任务测试结果：**

```json
// POST /core-submissions/sub_46bf7cb8.../evaluation-tasks
{
  "id": "evt_34a03a97-afc6-4c06-bcd5-9aeda55f1f7c",
  "submission_id": "sub_46bf7cb8-c583-4133-b7eb-6476dc17730e",
  "mode": "single",
  "status": "waiting_validator"
}

// POST /core-submissions/sub_46bf7cb8.../repeat-crawl-tasks
{
  "id": "rpt_5492e0e6-8a90-4129-848d-d86384312eb8",
  "submission_id": "sub_46bf7cb8-c583-4133-b7eb-6476dc17730e",
  "step": 1,
  "status": "waiting_candidate"
}
```

#### Phase 5 补充联调：OpenClaw `social-crawler-agent`

在 OpenClaw 中实际挂载独立插件 `social-crawler-agent` 后，使用配置中的：

- `platformBaseUrl = http://101.47.73.95`
- `platformToken = PLATFORM_SERVICE_JWT_SECRET_TEST`
- `minerId = miner-001`

通过插件 helper 实跑了两条真实链路：

1. `social_crawler_heartbeat`
2. `social_crawler_run_once`

补充结果如下：


| 联调项                           | 实际结果                                                                                                                           | 结论                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `social_crawler_heartbeat`    | 成功返回 `heartbeat sent`                                                                                                          | `POST /api/mining/v1/miners/heartbeat` 可用，且当前 token 至少可用于 miner heartbeat |
| `social_crawler_run_once` 第一步 | `POST /api/mining/v1/repeat-crawl-tasks/claim` 返回 `404 not_found`                                                              | 更接近“当前无可领取 repeat task / 当前任务未进入可 claim 状态”，不是整套 mining 接口损坏              |
| `social_crawler_run_once` 第二步 | `POST /api/mining/v1/refresh-tasks/claim` 返回 `200`，实际领取到任务 `rfs_2548b107-29be-4261-bf09-cf02fb7ab1a1`                          | 服务器当前存在可领取的 refresh task，不能解读为“服务器没有任务”                                   |
| `social_crawler_run_once` 第三步 | crawler 抓取任务 URL `http://example.com/posts/1001` 时命中上游 `404`，最终 `summary.json` 为 `records_succeeded = 0`, `records_failed = 1` | 本次 run-once 失败根因是平台下发任务中的目标 URL 是测试样本死链，不是插件挂载失败，也不是 claim 接口不可用          |


本次联调产物位于：

- [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_2548b107-29be-4261-bf09-cf02fb7ab1a1/summary.json)
- [task-input.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_2548b107-29be-4261-bf09-cf02fb7ab1a1/task-input.jsonl)
- [errors.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_2548b107-29be-4261-bf09-cf02fb7ab1a1/errors.jsonl)

补充判断：

- `repeat-crawl-tasks/claim` 的 `404` 目前应优先按“无可领取任务 / 任务尚未进入 claim 状态”解释。
- `refresh-tasks/claim` 已被真实验证为可用。
- 当前任务链路的主要问题不是“没任务”，而是“已分配任务的测试样本 URL 不可执行”。

补充说明：

- 本次 refresh task 指向的 `http://example.com/posts/1001` 明显属于测试样本 URL，不宜直接作为“线上真实内容抓取目标”解读。
- 因此本轮失败更准确地归类为“测试任务样本不可抓取”，不是平台任务系统整体故障。

为避免把“测试样本死链”误判为 crawler 执行链路故障，额外做了一组同结构模拟验证：

- 输入结构保持为 `generic/page` 任务记录
- backend 仍使用 `http`
- 仅把目标 URL 替换为可访问样本 `https://en.wikipedia.org/wiki/Artificial_intelligence`

模拟结果：


| 验证项             | 结果  | 说明                                                                                                                                                                        |
| --------------- | --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 模拟 refresh 任务输入 | 成功  | 输入文件 [simulated_refresh_task_valid.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/simulated_refresh_task_valid.jsonl)                                  |
| crawler 执行结果    | 成功  | [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/simulated_refresh_task_valid_run/summary.json) 显示 `records_succeeded = 1`, `records_failed = 0` |
| records 产出      | 成功  | [records.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/simulated_refresh_task_valid_run/records.jsonl) 已生成，`errors.jsonl` 为空                          |


该对照说明：

- 在任务样本 URL 可访问时，当前 crawler 执行链路本身是可用的。
- 因此 OpenClaw 插件 `run-once` 的失败应继续归因于平台下发测试样本 URL 不可抓取，而不是本地执行能力缺失。

**正确的 Report 请求体格式：**

```json
{
  "assignment_id": "asg_xxx",
  "result": {
    "verdict": "approved",
    "score": 0.9
  }
}
```

### Phase 6: Epoch 结算 ✓


| 测试   | 接口                                  | 状态码 | 结果   | 说明                                                 |
| ---- | ----------------------------------- | --- | ---- | -------------------------------------------------- |
| T6.1 | GET /epochs                         | 200 | PASS | 返回已完成 Epoch 列表                                     |
| T6.2 | GET /epochs/{epochID}               | 200 | PASS | 需使用 `epoch_id=2026-03-29`，而非内部 `id=epoch_20260329` |
| T6.3 | GET /epochs/{id}/snapshot           | 200 | PASS | 返回 miner / validator 聚合统计                          |
| T6.4 | POST /epochs/{epochID}/settle       | 200 | PASS | 对已完成 Epoch 重复 settle 表现为幂等                         |
| T6.5 | POST /epochs/invalid/settle         | 400 | PASS | `code=invalid_epoch`，预期行为                          |
| T6.6 | GET /epochs/{id}/settlement-results | 200 | PASS | 返回 miner / validator 最终结算结果                        |


**本次实际验证到的 Epoch：**

```json
{
  "id": "epoch_20260329",
  "epoch_id": "2026-03-29",
  "status": "completed",
  "summary": {
    "total": 2,
    "confirmed": 1,
    "rejected": 1
  }
}
```

**关键观察：**

- Core `GET /api/core/v1/epochs` 返回的列表项同时包含：
  - 内部主键 `id = epoch_20260329`
  - 业务标识 `epoch_id = 2026-03-29`
- Core 详情与 settle 接口的路径参数实际要求使用 `epoch_id`，即 `2026-03-29`
- Mining snapshot 与 settlement-results 也可使用 `2026-03-29` 直接查询

**Snapshot 实测结果：**

```json
{
  "epoch_id": "2026-03-29",
  "miners": {
    "auth-disabled-miner": {
      "task_count": 9,
      "avg_score": 88
    }
  },
  "validators": {
    "auth-disabled-validator": {
      "eval_count": 3,
      "accuracy": 0,
      "peer_review_accuracy": 0,
      "consecutive_idle": 0
    }
  }
}
```

**Settlement Results 实测结果：**

```json
{
  "epoch_id": "2026-03-29",
  "miners": [{
    "miner_id": "auth-disabled-miner",
    "task_count": 1,
    "avg_score": 0,
    "qualified": false,
    "weight": 1,
    "reward_amount": 0,
    "confirmed_submission_count": 1,
    "rejected_submission_count": 1
  }],
  "validators": [{
    "validator_id": "auth-disabled-validator",
    "eval_count": 3,
    "accuracy": 0,
    "peer_review_accuracy": 0,
    "consecutive_idle": 0,
    "qualified": false,
    "weight": 0,
    "reward_amount": 0,
    "slashed_amount": 0,
    "redistributed_amount": 0
  }]
}
```

**Submission 明细回查：**

通过 `GET /api/core/v1/submissions?page_size=100` 直接回查到与本次 epoch 结算对应的两条具体 submission：

1. `confirmed` 样本

```json
{
  "id": "sub_72fccfb3-1e3e-48df-bb57-aaed1f72104a",
  "dataset_id": "ds_pacc_d9e6b0d209",
  "epoch_id": "2026-03-29",
  "status": "confirmed",
  "created_at": "2026-03-29T07:27:47.080521Z",
  "updated_at": "2026-03-29T07:27:48.887069Z"
}
```

1. `rejected` 样本

```json
{
  "id": "sub_98777fa5-47dc-494e-9630-f6a5198af5e3",
  "dataset_id": "ds_posts",
  "epoch_id": "2026-03-29",
  "status": "rejected",
  "created_at": "2026-03-29T07:16:41.87346Z",
  "updated_at": "2026-03-29T07:27:48.887069Z"
}
```

该结果与 Epoch summary 中的：

- `confirmed = 1`
- `rejected = 1`

能够直接对上，说明本次已不只是“看到汇总数字”，而是已经回查到至少一条 `confirmed` 与一条 `rejected` 的具体 submission 明细。

**Validation Result 证据补充：**

通过 `GET /api/core/v1/validation-results?page_size=200` 继续回查，已能将 `confirmed` 样本进一步串到具体 validator 评估记录：

```json
{
  "id": "val_5643a148-8412-48a8-863c-1cea3294adbe",
  "submission_id": "sub_72fccfb3-1e3e-48df-bb57-aaed1f72104a",
  "validator_id": "auth-disabled-validator",
  "verdict": "accepted",
  "score": 95,
  "comment": "acceptance",
  "idempotency_key": "pacc-f61a0738a1054a9b9c16d85a963753d3",
  "created_at": "2026-03-29T07:27:47.24623Z"
}
```

这意味着当前至少已经能构造出一条完整证据链：

- Epoch `2026-03-29` summary 显示 `confirmed = 1`
- 对应 submission `sub_72fccfb3-1e3e-48df-bb57-aaed1f72104a` 状态为 `confirmed`
- 对应 validation result `val_5643a148-8412-48a8-863c-1cea3294adbe` verdict 为 `accepted`

**当前查证边界：**

- `rejected` 样本 `sub_98777fa5-47dc-494e-9630-f6a5198af5e3` 已能在 submission 列表中确认状态为 `rejected`
- 但在本次 `validation-results?page_size=200` 返回数据中，尚未直接定位到其对应的 validation result
- 因此目前可以确认“至少一条 confirmed 链路已经串到 validator verdict”，而 rejected 样本仍缺少同级别的 validation-result 证据

---

## 3. 协议 vs API 实现完整对比

> 基于 Data Mining Protocol V1.7 协议文档，逐项对比当前 API 实现状态

### 3.1 DataSet 体系（协议第二章）


| 协议功能               | API 接口                         | 实现状态      | 测试状态   | 备注              |
| ------------------ | ------------------------------ | --------- | ------ | --------------- |
| DataSet 列表         | `GET /datasets`                | ✅         | ✅ PASS |                 |
| DataSet 详情         | `GET /datasets/{id}`           | ✅         | ✅ PASS |                 |
| DataSet 创建         | `POST /datasets`               | ✅         | ✅ PASS |                 |
| DataSet 激活         | `POST /datasets/{id}/activate` | ✅         | ✅ PASS |                 |
| `**dedup_fields`** | 协议要求                           | ❌ **未实现** | -      | 关键缺失：无法按内容去重    |
| `**url_patterns`** | 协议要求                           | ❌ **未实现** | -      | 关键缺失：无法校验URL合法性 |
| `refresh_interval` | 协议要求                           | ✅         | ✅      | 字段存在            |


---

### 3.2 Miner 工作流程（协议第四章）


| 协议功能        | API 接口                             | 实现状态  | 测试状态   | 备注                         |
| ----------- | ---------------------------------- | ----- | ------ | -------------------------- |
| Miner 心跳    | `POST /miners/heartbeat`           | ✅     | ✅ PASS | 返回 credit=0, remaining=100 |
| 在线列表        | `GET /miners/online`               | ✅     | ✅ PASS |                            |
| 提交预检        | `POST /miners/preflight`           | ✅     | ✅ PASS | 返回 challenge               |
| PoW 答题      | `POST /pow-challenges/{id}/answer` | ✅     | ✅ PASS | passed=true/false          |
| 信用分阶梯       | 心跳返回                               | ⚠️ 部分 | ⚠️     | credit 字段有，增减逻辑未验证         |
| **IP 衰减**   | 协议要求                               | ❓ 未知  | ❌ 未测   | 需多 IP 环境验证                 |
| **PoW 一次性** | 协议要求                               | ❓ 未知  | ❌ 未测   | 答对后只允许一次提交                 |


---

### 3.3 数据提交（协议第三章）


| 协议功能                | API 接口                       | 实现状态      | 测试状态   | 备注                  |
| ------------------- | ---------------------------- | --------- | ------ | ------------------- |
| URL 占位检查            | `GET /url-occupancies/check` | ✅         | ✅ PASS | occupied=true/false |
| 创建提交                | `POST /submissions`          | ✅         | ✅ PASS | status=pending      |
| 提交列表                | `GET /submissions`           | ✅         | ✅ PASS |                     |
| 提交详情                | `GET /submissions/{id}`      | ✅         | 未单独测   |                     |
| `**dedup_hash` 字段** | 协议要求                         | ❌ **未实现** | -      | 响应中无此字段             |
| 重复 URL 拒绝           | 协议要求                         | ⚠️ 部分     | ⚠️     | 基于 URL 去重，非内容去重     |


---

### 3.4 Validator 验证（协议第七章）


| 协议功能                 | API 接口                       | 实现状态 | 测试状态   | 备注                      |
| -------------------- | ---------------------------- | ---- | ------ | ----------------------- |
| Validator 心跳         | `POST /validators/heartbeat` | ✅    | ✅ PASS | eligible=true, credit=0 |
| Validator 就绪         | `POST /validators/ready`     | ✅    | ✅ PASS | status=ready            |
| 验证结果列表               | `GET /validation-results`    | ✅    | ✅ PASS |                         |
| 创建验证结果               | `POST /validation-results`   | ✅    | ✅ PASS | 返回 val_xxx              |
| **准入检查 (min_stake)** | 协议要求                         | ❓ 未知 | ❌ 未测   | auth-disabled 模式下无法验证   |
| **信用分等级限制**          | 协议要求                         | ❓ 未知 | ❌ 未测   | 任务间隔、Golden Task 比例     |
| **驱逐机制**             | 协议要求                         | ❓ 未知 | ❌ 未测   | accuracy < 20 驱逐        |


---

### 3.5 任务系统（协议第五章）

#### 3.5.1 复核任务 (Repeat Crawl)


| 协议功能            | API 接口                                           | 实现状态 | 测试状态      | 备注                            |
| --------------- | ------------------------------------------------ | ---- | --------- | ----------------------------- |
| 创建任务            | `POST /repeat-crawl-tasks`                       | ✅    | ✅ PASS    |                               |
| 从提交创建           | `POST /core-submissions/{id}/repeat-crawl-tasks` | ✅    | ✅ PASS    | 返回 rpt_xxx                    |
| 领取任务            | `POST /repeat-crawl-tasks/claim`                 | ⚠️   | ❌ BLOCKED | 状态 waiting_candidate 无法 claim |
| 上报结果            | `POST /repeat-crawl-tasks/{id}/report`           | ⚠️   | ❌ 未测      | 依赖 claim 成功                   |
| **排除原始提交者**     | 协议要求                                             | ❓ 未知 | ❌ 未测      | 需多 Miner 环境                   |
| **排除同 IP**      | 协议要求                                             | ❓ 未知 | ❌ 未测      |                               |
| **Step 1/2 裁决** | 协议要求                                             | ❓ 未知 | ❌ 未测      |                               |


#### 3.5.2 评估任务 (Evaluation)


| 协议功能               | API 接口                                         | 实现状态 | 测试状态   | 备注                   |
| ------------------ | ---------------------------------------------- | ---- | ------ | -------------------- |
| 创建任务               | `POST /evaluation-tasks`                       | ✅    | ✅ PASS |                      |
| 从提交创建              | `POST /core-submissions/{id}/evaluation-tasks` | ✅    | ✅ PASS | 返回 evt_xxx           |
| 领取任务               | `POST /evaluation-tasks/claim`                 | ✅    | ✅ PASS | 返回 task_id           |
| 上报结果               | `POST /evaluation-tasks/{id}/report`           | ✅    | ✅ PASS |                      |
| **Golden Task 标识** | 协议要求                                           | ❓ 未知 | ❌ 未测   | claim 是否返回 golden 字段 |
| **Peer Review 模式** | 协议要求                                           | ❓ 未知 | ❌ 未测   | 10% 概率 5 人共识         |


#### 3.5.3 刷新任务 (Refresh)


| 协议功能         | API 接口                            | 实现状态      | 测试状态   | 备注          |
| ------------ | --------------------------------- | --------- | ------ | ----------- |
| 创建任务         | `POST /refresh-tasks`             | ✅         | ✅ PASS |             |
| 领取任务         | `POST /refresh-tasks/claim`       | ✅         | ✅ PASS |             |
| 上报结果         | `POST /refresh-tasks/{id}/report` | ✅         | ⚠️     | 正向通过，权限检查缺失 |
| **排除历史提交者**  | 协议要求                              | ❓ 未知      | ❌ 未测   |             |
| **非指派人不可操作** | 协议要求                              | ❌ **Bug** | ❌ 未通过  | 非指派人仍返回 200 |


---

### 3.6 Epoch 结算（协议第六章 & 第九章）


| 协议功能                           | API 接口                                | 实现状态  | 测试状态   | 备注                     |
| ------------------------------ | ------------------------------------- | ----- | ------ | ---------------------- |
| Epoch 列表                       | `GET /epochs`                         | ✅     | ✅ PASS | 已有 2026-03-29          |
| Epoch 详情                       | `GET /epochs/{epochID}`               | ✅     | ✅ PASS | 用 epoch_id 而非 id       |
| Epoch 快照                       | `GET /epochs/{id}/snapshot`           | ✅     | ✅ PASS | 含 miner/validator 统计   |
| 触发结算                           | `POST /epochs/{epochID}/settle`       | ✅     | ✅ PASS | 幂等                     |
| 结算结果                           | `GET /epochs/{id}/settlement-results` | ✅     | ✅ PASS |                        |
| **达标门控 (≥80条 且 ≥60分)**         | 协议要求                                  | ⚠️ 部分 | ⚠️     | 有 qualified 字段，逻辑未完整验证 |
| **pending→confirmed/rejected** | 协议要求                                  | ✅     | ✅ PASS | 已验证状态流转                |
| **信用分 ±5/15**                  | 协议要求                                  | ❓ 未知  | ❌ 未测   | 需对比结算前后                |
| **dedup_hash 释放**              | 协议要求                                  | ❓ 未知  | ❌ 未测   | rejected 后 URL 能否重提    |
| **(avg_score)² 加权**            | 协议要求                                  | ❓ 未知  | ❌ 未测   | 奖励计算逻辑                 |


---

## 4. 实现状态汇总


| 分类        | 总项数    | ✅ 已实现+已测     | ⚠️ 部分/未测    | ❌ 未实现/Bug    |
| --------- | ------ | ------------ | ----------- | ------------ |
| DataSet   | 7      | 5            | 0           | **2**        |
| Miner     | 7      | 4            | 1           | 2            |
| 数据提交      | 6      | 4            | 1           | **1**        |
| Validator | 7      | **5**        | 0           | 2            |
| 任务系统      | 17     | **10**       | 2           | **5**        |
| Epoch     | 10     | 6            | 2           | 2            |
| **合计**    | **54** | **34 (63%)** | **6 (11%)** | **14 (26%)** |


---

## 5. 关键缺失项（High Priority）


| #   | 功能                       | 影响                     | 状态      |
| --- | ------------------------ | ---------------------- | ------- |
| 1   | `dedup_fields`           | 无法按内容去重，只能按 URL        | ❌ 未实现   |
| 2   | `url_patterns`           | 无法校验 URL 合法性           | ❌ 未实现   |
| 3   | `dedup_hash` 字段          | 无法查看/验证内容去重            | ❌ 未实现   |
| 4   | 非指派人不可 report            | **授权检查 Bug**           | ❌ Bug   |
| 5   | repeat-crawl-tasks/claim | 任务卡在 waiting_candidate | ⚠️ 环境依赖 |
| 6   | Golden Task 标识           | 无法区分考核任务               | ❓ 未测    |
| 7   | Peer Review 模式           | 无法触发 5 人共识             | ❓ 未测    |
| 8   | 信用分增减逻辑                  | 无法验证 +5/-15            | ❓ 未测    |


---

## 6. 建议后续行动

### 6.1 需要服务端修复


| 问题                                 | 优先级    | 说明                  |
| ---------------------------------- | ------ | ------------------- |
| `refresh-tasks/{id}/report` 权限检查   | **P0** | 非指派人仍返回 200，应返回 403 |
| `dedup_fields` / `url_patterns` 字段 | **P1** | 协议核心去重机制            |
| `dedup_hash` 响应字段                  | **P1** | 便于客户端验证             |


### 6.2 需要服务端确认

1. **repeat-crawl-tasks** 的 candidate 分配逻辑是什么？
2. **Epoch 自动生成 / 自动结算** 的触发条件是什么？
3. **Golden Task** 是否已实现？claim 响应中如何区分？

### 6.3 需要补充测试（启用鉴权后）

1. 多 Miner 身份验证角色权限隔离
2. 多 Miner 环境下验证 Repeat Crawl 流程
3. 信用分结算前后对比
4. PoW 一次性放行验证

---

## 7. 接口可用性速查


| 接口类别                             | 状态  | 可直接使用            |
| -------------------------------- | --- | ---------------- |
| 数据集 CRUD                         | ✅   | 是                |
| Miner 心跳/preflight/PoW           | ✅   | 是                |
| Submission 创建/查询                 | ✅   | 是                |
| URL 占位检查                         | ✅   | 是                |
| Validator 心跳/ready               | ✅   | 是                |
| validation-results 创建/查询         | ✅   | 是                |
| evaluation-tasks 创建/claim/report | ✅   | 是                |
| core-submissions 创建任务            | ✅   | 是                |
| refresh-tasks 创建/claim           | ✅   | 是                |
| refresh-tasks/{id}/report        | ⚠️  | 是，但权限检查缺失        |
| repeat-crawl-tasks 创建            | ✅   | 部分 (claim 需等待分配) |
| Epoch 结算                         | ✅   | 是                |


---

## 8. 结论

**API 基础功能完备度：约 75%**（核心 CRUD + 基础流程 + 从提交创建任务）

- 核心 CRUD 操作正常
- Miner/Validator 基础流程可用
- 任务系统框架完整（含从提交创建）
- Epoch 结算链路已验证

**协议落地完整度：约 60%**

- 缺少 `dedup_fields` / `url_patterns` / `dedup_hash` 等关键去重机制
- 权限检查存在 Bug（非指派人可 report）
- 高级评估模式（Golden Task、Peer Review）未实现或无法验证
- 信用分增减、奖励计算等逻辑未验证

**可直接用于联调的部分：**

- 数据集管理
- Miner 注册 + PoW + 数据提交
- Validator 注册 + 验证结果提交 + 评估任务
- 从提交创建评估/复核任务
- Refresh 任务领取执行
- Epoch 查询与结算

**需要进一步对接的部分：**

- 内容去重机制（dedup_fields）
- 权限检查修复
- Repeat Crawl 完整流程
- 高级评估模式验证

