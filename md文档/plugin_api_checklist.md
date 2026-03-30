# Plugin 与后端 API 协同实现对比清单

> 本清单对比 `protocol_feature_checklist.md` 协议要求与 `openclaw-social-crawler-plugin` 实现情况。
>
> **图例**：✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 | ➖ 不适用

---

## 1. 后端 API 端点覆盖

### 已实现的 API 调用

| API 端点 | 方法 | Plugin 实现 | 实现位置 |
| --- | --- | --- | --- |
| `/api/mining/v1/miners/heartbeat` | POST | ✅ `send_miner_heartbeat()` | `agent_runtime.py:100-101` |
| `/api/mining/v1/repeat-crawl-tasks/claim` | POST | ✅ `claim_repeat_crawl_task()` | `agent_runtime.py:103-104` |
| `/api/mining/v1/refresh-tasks/claim` | POST | ✅ `claim_refresh_task()` | `agent_runtime.py:106-107` |
| `/api/mining/v1/repeat-crawl-tasks/{id}/report` | POST | ✅ `report_repeat_crawl_task_result()` | `agent_runtime.py:109-110` |
| `/api/mining/v1/refresh-tasks/{id}/report` | POST | ✅ `report_refresh_task_result()` | `agent_runtime.py:112-113` |
| `/api/core/v1/submissions` | POST | ✅ `submit_core_submissions()` | `agent_runtime.py:115-116` |
| `/api/core/v1/submissions/{id}` | GET | ✅ `fetch_core_submission()` | `agent_runtime.py:118-123` |
| `/api/core/v1/datasets/{id}` | GET | ✅ `fetch_dataset()` | `agent_runtime.py:125-130` |

### 未实现的 API 调用

| API 端点 | 方法 | 协议要求 | 状态 | 备注 |
| --- | --- | --- | --- | --- |
| `/api/mining/v1/miners/preflight` | POST | 提交前预检 | ❌ 未实现 | 应在提交前检查是否需要 PoW |
| `/api/core/v1/url-occupancies/check` | GET | URL 占用检查 | ❌ 未实现 | 应在提交前检查 URL 是否已被占用 |
| `/api/mining/v1/pow-challenges/{id}/answer` | POST | PoW 答题 | ❌ 未实现 | preflight 返回需要 PoW 时调用 |
| `/api/mining/v1/miners/online` | GET | 查询在线状态 | ❌ 未实现 | 可选 |
| `/api/mining/v1/evaluation-tasks/claim` | POST | 领取评估任务 | ➖ 不适用 | Validator 功能 |
| `/api/mining/v1/evaluation-tasks/{id}/report` | POST | 上报评估结果 | ➖ 不适用 | Validator 功能 |
| `/api/mining/v1/validators/*` | * | Validator 相关 | ➖ 不适用 | Validator 功能 |

---

## 2. Miner 场景验收对照

### 协议要求 vs 实现状态

| 场景 | 验收 API | 协议通过标准 | 实现状态 | 当前实现 |
| --- | --- | --- | --- | --- |
| 上线接单 | `POST /miners/heartbeat` | 返回 200，online=true | ✅ 已实现 | `send_miner_heartbeat()` |
| 提交前确认是否可提交 | `POST /miners/preflight` | 明确返回允许/需PoW/额度不足 | ❌ 未实现 | |
| 完成一次 PoW 放行 | `POST /pow-challenges/{id}/answer` | 错答不放行，答对只放行一次 | ❌ 未实现 | |
| 提交一条新数据 | `GET /url-occupancies/check` + `POST /submissions` | 未占用可提交，状态为 pending | ⚠️ 部分实现 | 有 submit，无 URL 检查 |
| 执行真实性复核任务 | `/repeat-crawl-tasks/claim` + `report` | 被分配 Miner 能领取并上报 | ✅ 已实现 | `run_once()` 流程 |
| 执行历史刷新任务 | `/refresh-tasks/claim` + `report` | 被分配 Miner 能领取并上报 | ✅ 已实现 | `run_once()` 流程 |

---

## 3. Plugin Tools 功能对照

### 已暴露的 OpenClaw Tools

| Tool 名称 | 描述 | 实现功能 |
| --- | --- | --- |
| `social_crawler_heartbeat` | 发送心跳 | 调用 heartbeat API |
| `social_crawler_run_once` | 执行一次完整任务 | heartbeat → claim → crawl → report → submit |
| `social_crawler_process_task_file` | 处理本地任务文件 | 跳过 claim，直接 crawl → report → submit |
| `social_crawler_export_core_submissions` | 导出提交 payload | 转换 records.jsonl → Core submission JSON |

### 缺失的 Tools

| 建议 Tool 名称 | 功能 | 关联 API |
| --- | --- | --- |
| `social_crawler_preflight` | 提交前预检 | `POST /miners/preflight` |
| `social_crawler_check_url` | URL 占用检查 | `GET /url-occupancies/check` |
| `social_crawler_answer_pow` | PoW 答题 | `POST /pow-challenges/{id}/answer` |

---

## 4. 工作流完整性分析

### 当前 `run_once()` 流程

```text
1. send_miner_heartbeat()           ✅
2. claim_repeat_crawl_task()        ✅
   └── 或 claim_refresh_task()      ✅
3. crawler_main(argv)               ✅ (调用 social-data-crawler)
4. build_report_payload()           ✅
5. report_*_task_result()           ✅
6. submit_core_submissions()        ✅
```

### 协议要求的完整流程（新数据提交）

```text
1. send_miner_heartbeat()           ✅ 已实现
2. preflight()                      ❌ 缺失 - 应检查是否需要 PoW
   └── 若需要 PoW:
       answer_pow_challenge()       ❌ 缺失
3. check_url_occupancy()            ❌ 缺失 - 应检查 URL 是否已占用
4. crawler 执行                     ✅ 已实现
5. submit_core_submissions()        ✅ 已实现
```

---

## 5. 代码质量观察

### 优点

1. **错误处理**：`_request()` 有重试机制（3 次），5xx 自动退避
2. **平台推断**：`_infer_platform_task()` 支持 5 个平台的 URL 解析
3. **数据转换**：`build_submission_request()` + schema 字段映射完善
4. **配置灵活**：支持 `platformToken`、`defaultBackend` 等可选配置

### 待改进项

| 问题 | 位置 | 建议 |
| --- | --- | --- |
| 无 preflight 检查 | `run_once()` | 在 submit 前调用 preflight API |
| 无 URL 占用检查 | `submit_core_submissions()` | 提交前先检查 URL 是否已存在 |
| 无 PoW 处理 | - | 添加 PoW challenge 应答逻辑 |
| 幂等性未处理 | `submit_core_submissions()` | 应传递 `idempotency_key` 防止重复提交 |
| 无评估任务支持 | - | 若 Miner 也需执行评估，需添加 |

---

## 6. 实现进度总结

| 模块 | 协议要求项 | 已实现 | 未实现 |
| --- | --- | --- | --- |
| Miner 心跳 | 1 | 1 | 0 |
| 任务领取与上报 | 4 | 4 | 0 |
| 数据提交 | 3 | 1 | 2 (preflight, URL check) |
| PoW 机制 | 1 | 0 | 1 |
| **合计** | **9** | **6 (67%)** | **3 (33%)** |

### 关键缺失

1. **`preflight` API 调用** - 无法判断是否需要 PoW 或额度是否充足
2. **`url-occupancies/check` API 调用** - 可能提交重复 URL
3. **PoW 答题流程** - 无法通过 PoW 放行

---

## 附录：配置示例

```jsonc
// openclaw.config.jsonc
{
  "plugins": {
    "entries": {
      "social-crawler-agent": {
        "path": "./openclaw-social-crawler-plugin",
        "config": {
          "crawlerRoot": "D:/kaifa/clawtroop/social-data-crawler",
          "platformBaseUrl": "http://101.47.73.95",
          "platformToken": "",  // 可选
          "minerId": "miner-001",
          "outputRoot": "./output/agent-runs",
          "defaultBackend": "playwright"  // 可选
        }
      }
    }
  }
}
```
