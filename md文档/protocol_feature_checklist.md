# 功能验收清单

## 管理员 / 协议运营方

| 场景 | 验收 API | 通过标准 |
| --- | --- | --- |
| 开通一个可接入的数据主题 | `POST /api/core/v1/datasets` | 返回 `201`，且 `data.status=pending_review`。 |
| 让数据主题正式开放接单 | `POST /api/core/v1/datasets/{id}/activate` | 返回 `200`，且状态变为 `active`。 |
| 把当期提交结算成正式结果 | `POST /api/core/v1/epochs/{epoch_id}/settle` | 结算成功后，Submission 状态更新为 `confirmed` 或 `rejected`。 |
| 发起一次真实性复核 | `POST /api/mining/v1/repeat-crawl-tasks` | 返回成功，且任务可被指定角色领取。 |
| 发起一次质量评估 | `POST /api/mining/v1/evaluation-tasks` | 返回成功，且任务可被 Validator 领取。 |
| 发起一次历史数据刷新 | `POST /api/mining/v1/refresh-tasks` | 返回成功，且任务可被 Miner 领取执行。 |
| 查看结算前统计和结算后结果 | `GET /api/mining/v1/epochs/{id}/snapshot` `GET /api/mining/v1/epochs/{id}/settlement-results` | 快照接口返回统计字段，结果接口返回最终结算字段。 |

## Miner 接入方

| 场景 | 验收 API | 通过标准 |
| --- | --- | --- |
| 上线接单 | `POST /api/mining/v1/miners/heartbeat` | 返回 `200`，且 `online=true`。 |
| 提交前确认是否可提交 | `POST /api/mining/v1/miners/preflight` | 明确返回允许提交、需要 PoW 或额度不足中的一种结果。 |
| 完成一次 PoW 放行 | `POST /api/mining/v1/miners/preflight` `POST /api/mining/v1/pow-challenges/{id}/answer` | 错答不放行，答对后只放行一次。 |
| 提交一条新数据 | `GET /api/core/v1/url-occupancies/check` `POST /api/core/v1/submissions` | 未占用 URL 可提交成功，提交后状态为 `pending`。 |
| 执行一次真实性复核任务 | `POST /api/mining/v1/repeat-crawl-tasks/claim` `POST /api/mining/v1/repeat-crawl-tasks/{id}/report` | 被分配 Miner 能领取并上报，非被分配 Miner 不能操作。 |
| 执行一次历史刷新任务 | `POST /api/mining/v1/refresh-tasks/claim` `POST /api/mining/v1/refresh-tasks/{id}/report` | 被分配 Miner 能领取并上报，非被分配 Miner 不能操作。 |

## Validator 接入方

| 场景 | 验收 API | 通过标准 |
| --- | --- | --- |
| 提交一条审核结果 | `POST /api/core/v1/validation-results` | 返回成功，且成功写入 verdict 和 score。 |
| 重复提交不会重复记账 | `POST /api/core/v1/validation-results` | 使用相同 `idempotency_key` 重复提交时返回已有结果，且不新增重复记录。 |
| 进入评估待命池 | `POST /api/mining/v1/validators/heartbeat` `POST /api/mining/v1/validators/ready` | 合格 Validator 可进入 ready pool，不合格会被拒绝。 |
| 完成一次质量评估任务 | `POST /api/mining/v1/evaluation-tasks/claim` `POST /api/mining/v1/evaluation-tasks/{id}/report` | Validator 能成功领取并上报，错误角色被拒绝。 |
| 查看自己的评估结果是否沉淀到统计 | `GET /api/mining/v1/epochs/{id}/snapshot` | 返回评估次数、准确率等统计字段。 |
