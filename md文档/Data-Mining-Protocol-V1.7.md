# Data Mining Protocol V1.7

来源：<https://www.notion.so/Data-Mining-Protocol-V1-7-33213d54f564807196caca5046c75caa>

> 说明：由 Playwright 渲染 Notion 公开页后，按块结构转换为 Markdown（表格与代码块已结构化处理）。


# 第一章 协议概述

### 1.1 目标

DATA Mining Subnet 激励 AI Agent 爬取互联网网页，按 DataSet 定义的 Schema 将非结构化内容转换为高质量结构化数据（JSON），为下游 AI 训练和应用提供数据源。

### 1.2 代币

| 代币 | 类型 | 用途 |
| --- | --- | --- |
| $AWP | RootNet 原生代币 | Validator 注册质押（准入门槛）、DataSet 创建付费、AMM 兑换 |
| $ocDATA | 子网 Alpha Token (ERC-20)，由 SubnetContract 铸造 | Miner/Validator 奖励发放、PancakeSwap 上与 $AWP 自由交易 |

### 1.3 角色

| 角色 | 质押要求 | 职责 | 收益来源 |
| --- | --- | --- | --- |
| Miner | 无需质押 | 爬取网页、清洗数据、结构化数据、提交结果 | Epoch 排放的 41% |
| Validator | RootNet 质押 ≥ min_stake AWP | 数据真实性校验 + 结构化质量评估 | Epoch 排放的 41% |
| Subnet Owner | — | 运营子网、维护 Golden Task 库、升级 Skill、审核 DataSet | Epoch 排放的 18% |
| DataSet 创建者 | 付费 $AWP | 定义新 DataSet 的 Schema | 无直接收益 |

---

## 第二章 DataSet 体系

### 2.1 定义

DataSet 是子网的核心数据组织单元。每个 DataSet 代表一类结构化数据，拥有独立的 Schema。DataSet 数量无限，用户付费创建，经 Owner 审核后上线。

```
{
  "dataset_id":        "ds_x_posts",
  "name":              "X (Twitter) Posts",
  "creator":           "0xABC...",
  "creation_fee":      "50 $AWP",
  "status":            "pending_review",
  "source_domains":    ["x.com", "twitter.com"],
  "url_patterns":      ["x.com/*/status/*", "twitter.com/*/status/*"],
  "schema":            { "..." },
  "dedup_fields":      ["post_id"],
  "refresh_interval":  null,
  "created_at":        "2026-03-07",
  "total_entries":     0
}
```

dedup_fields
指定用于内容去重的字段名列表（AND 关系）。提交时 Coordinator 从 structured_data 中提取这些字段的值计算
dedup_hash
，同一 DataSet 内不允许存在 dedup_hash 相同的 pending 或未过期 confirmed 记录。

url_patterns
（可选）指定合法 URL 的模式列表。如果设置，Coordinator 在提交时校验 URL 是否匹配至少一个 pattern，不匹配则拒绝。防止 Miner 提交同一域名下不相关的页面（如 Amazon 搜索页 vs 产品页）。

> 为什么不用 URL 去重 ：同一内容可能对应多个 URL（如 x.com/status/123 和 twitter.com/status/123），URL 去重会导致重复数据入库。基于内容字段去重更准确。

### 2.2 Schema 与去重字段示例

X Posts
（dedup_fields:
["post_id"]
）:

```
{
  "post_id":        { "type": "string",   "required": true },
  "author_handle":  { "type": "string",   "required": true },
  "content":        { "type": "string",   "required": true },
  "timestamp":      { "type": "datetime", "required": true },
  "likes":          { "type": "integer",  "required": false },
  "retweets":       { "type": "integer",  "required": false },
  "replies":        { "type": "integer",  "required": false },
  "media_urls":     { "type": "string[]", "required": false },
  "language":       { "type": "string",   "required": true }
}
```

Amazon Products
（dedup_fields:
["asin"]
，url_patterns:
["amazon.com/dp/*", "amazon.com/gp/product/*"]
）:

```
{
  "asin":           { "type": "string",   "required": true },
  "title":          { "type": "string",   "required": true },
  "price":          { "type": "number",   "required": true },
  "currency":       { "type": "string",   "required": true },
  "rating":         { "type": "number",   "required": false },
  "review_count":   { "type": "integer",  "required": false },
  "availability":   { "type": "boolean",  "required": true },
  "categories":     { "type": "string[]", "required": true },
  "images":         { "type": "string[]", "required": false }
}
```

去重字段设计原则
：

- dedup_fields 必须是 Schema 中 required: true 的字段

- 多个字段时取 AND 关系：如 ["source_domain", "article_id"] 表示两者组合唯一

- dedup_hash = SHA256(dedup_fields[0] + "|" + dedup_fields[1] + ...)

- DataSet 创建时 Owner 审核 dedup_fields 的合理性

### 2.3 DataSet 创建

```
任何用户 → 支付 50 $AWP → 提交 Schema + 来源域名 + 描述
  → 自动校验（字段类型合法、至少 3 个 required 字段、dedup_fields 均为 required 字段、url_patterns 格式合法）
  → 通过自动校验 → 进入 pending_review 状态
  → Subnet Owner 人工审核：
      ✓ Schema 合理性（字段设计是否有实际价值）
      ✓ 来源域名合法性（不含敏感/非法站点）
      ✓ 与已有 DataSet 去重（是否与现有 DataSet 高度重复）
  → 审核通过 → DataSet 上线（active），Miner 可开始提交
  → 审核拒绝 → 退还 50 $AWP，附拒绝原因
```

创建费用（审核通过后）归入子网 Treasury。

### 2.4 DataSet 生命周期

```
Created → Pending Review → Active → (可选) Paused → Archived
                │
           Owner 拒绝 → Rejected（退费）
```

### 2.5 数据刷新机制

DataSet 可配置可选的
refresh_interval
，定义数据的刷新周期。

```
refresh_interval 设置：
  null          → 数据永不过期（默认）
  "7d"          → 7 天后需要刷新
  "30d"         → 30 天后需要刷新

过期处理：
  confirmed 数据超过 refresh_interval 后：
    → dedup_hash 重新开放（允许提交新版本）
    → 旧数据不删除、不改状态，保留为历史版本
    → Coordinator 从刷新队列中随机指派 Miner 重新爬取
    → 新版本提交后走正常 Phase A + Phase B 评估
    → 通过后成为该内容的最新 confirmed 记录

历史数据:
  同一 dedup_hash 的多次 confirmed 记录按 crawl_timestamp 排序
  消费者可查询最新版本或完整时间线
```

适用场景：

- 价格类数据（Amazon Products）：建议 refresh_interval: "7d"

- 内容类数据（Twitter Posts）：建议 refresh_interval: null （推文内容不变）

- 新闻类数据：建议 refresh_interval: "1d"

刷新任务由 Coordinator 随机指派
（而非开放自由提交）：

```
原因：如果允许原始 Miner 自由提交，Miner 可能缓存旧数据直接重复提交
    → Phase A 对比时页面变化可能不大，相似度仍 ≥ 75%，通过
    → 结果: "刷新"了但数据没变

指派流程：
  数据过期 → 进入刷新队列
  → Coordinator 随机选 1 个在线 Miner（排除该 URL 的历史提交者 + 同 IP）
  → 推送刷新任务: { url, dataset_id, schema }
  → Miner 实际爬取 → 清洗 → 结构化 → 提交
  → 正常 Phase A + Phase B 评估
  → 通过 → 新版本 confirmed
  → 失败 → 重新分配给其他 Miner

刷新任务计入 Miner 的 task_count
```

---

## 第三章 数据去重与入库规则

### 3.1 内容去重

去重基于 DataSet 定义的
dedup_fields
，而非 URL。
同一内容可能有多个 URL（如 x.com 和 twitter.com 指向同一推文），URL 去重无法覆盖这些情况。

```
去重流程:
  Miner 提交 (dataset_id, url, cleaned_data, structured_data):
    → 从 structured_data 中提取 dedup_fields 对应的值
    → dedup_hash = SHA256(field_value_1 + "|" + field_value_2 + ...)
    → 查询：该 dataset_id + dedup_hash 是否有 pending 或未过期的 confirmed？
      → 有 → 拒绝（内容重复）
      → 没有 → 接受，进入 pending 状态

示例:
  DataSet "X Posts", dedup_fields = ["post_id"]
  Miner A 提交 x.com/user/status/123 → post_id = "123" → dedup_hash = SHA256("123")
  Miner B 提交 twitter.com/user/status/123 → post_id = "123" → dedup_hash 相同 → 拒绝

  DataSet "新闻", dedup_fields = ["source_domain", "article_id"]
  → dedup_hash = SHA256("reuters.com|20260325-001")

刷新任务（Coordinator 指派）:
  → 数据过期（now() > crawl_timestamp + refresh_interval）
  → Coordinator 指派 Miner 重新爬取 → 进入 pending 状态
  → 旧 confirmed 记录不动（保留为历史版本）
```

### 3.2 数据的状态

Miner 在 Epoch 内的提交不会立即入库到 DataSet，而是处于
pending
状态，等 Epoch 结算后根据 Miner 表现决定是否正式入库。

```
提交状态流转：

  Miner 提交 → pending（暂存，占住 dedup_hash 位置，但不对外可见）
                  │
            Epoch 结算时
                  │
        ┌─────────┼─────────┐
        ▼                   ▼
    confirmed            rejected
   （正式入库，            （数据丢弃，
    对外可见）              dedup_hash 占位释放）

  配置了 refresh_interval 的 DataSet:
    confirmed 记录超过有效期后:
    → 该 dedup_hash 重新开放（允许新版本提交）
    → 旧记录保留（按 crawl_timestamp 区分版本）
    → 新版本 confirmed 后，同一内容有多条历史记录
```

| 状态 | 说明 |
| --- | --- |
| pending | Epoch 内的临时状态，dedup_hash 已被占住（其他 Miner 不能提交同一内容），但数据未正式入库 |
| confirmed | Epoch 结算后，Miner 达标，数据正式写入 DataSet，对外可见可查询 |
| rejected | Epoch 结算后，Miner 未达标，数据被丢弃， dedup_hash 占位被释放 （其他 Miner 可重新提交同一内容） |

> 注 ：没有 expired 状态。confirmed 记录永久保留，过期仅意味着 dedup_hash 重新开放允许提交新版本。同一 dedup_hash 的多条 confirmed 记录按 crawl_timestamp 构成时间线。

### 3.3 可见性

- Miner 可以 查询某个 dedup_hash 是否已被占用（含 pending 和 confirmed）

- Miner 无法 看到已提交的具体数据内容

- 外部数据消费者只能查到 confirmed 状态的数据

---

## 第四章 Miner 工作流程

### 4.1 注册

```
1. 安装 @ocdata/miner-skill（通过 Subnet Hub）
2. 注册 Hotkey 到子网
3. 无需质押，即可开始工作
4. 新 Miner 初始信用分 = 0，需通过 AI PoW 验证后提交
```

### 4.2 Miner 防 Sybil 三层机制

Miner 无需质押，创建身份成本为零。为防止 Sybil 攻击（大量注册新身份霸占提交配额），协议通过三层机制叠加防御：

```
Layer 1: 信用分阶梯 → 控制单个身份的行为上限
Layer 2: AI PoW     → 控制每次提交的计算成本
Layer 3: IP 衰减    → 控制同一来源的身份密度
```

### 4.2.1 信用分（Credit Score）

```
信用分计算：
  初始值 = 0
  每个达标 Epoch: credit += 5（上限 100）
  每个未达标 Epoch: credit -= 15（下限 0）
  连续 3 个 Epoch 未达标: credit = 0
```

| 信用分区间 | 等级 | 每 Epoch 最大提交数 | AI PoW 触发概率 | 达到所需 |
| --- | --- | --- | --- | --- |
| 0 - 19 | 新手 | 100 条 | 100% | 0（初始） |
| 20 - 39 | 受限 | 500 条 | 50% | 4 个达标 Epoch |
| 40 - 59 | 普通 | 2,000 条 | 20% | 8 个达标 Epoch |
| 60 - 79 | 良好 | 10,000 条 | 5% | 12 个达标 Epoch |
| 80 - 100 | 优秀 | 无上限 | 1% | 16 个达标 Epoch |

### 4.2.2 AI PoW（Proof of Work）

每次提交前，根据 Miner 信用分等级的概率，Coordinator 可能发起一道 AI 挑战题。Miner 必须用自己的 LLM 回答并通过验证，才能获得本次提交权。

```
提交流程:
  POST /submit
    → Coordinator 掷骰子: 是否触发 PoW？（概率见信用分表）
      → 触发 → 返回 AI 挑战题
        → Miner 用 LLM 回答 → 提交答案
        → Coordinator 验证:
          → 通过 → 接受提交
          → 失败 → 拒绝提交
      → 不触发 → 直接接受提交
```

AI 挑战题设计
：

```
题目类型（从题库随机抽取，与 DataSet 的 Schema 相关）:

  类型 1 — 结构化提取:
    给一段 cleaned_data 样本 → 要求按指定 Schema 提取结构化 JSON
    验证: Coordinator 用预存的正确答案对比

  类型 2 — 内容理解:
    给一段文本 → 问一个需要理解内容才能回答的问题
    验证: Coordinator 用预存的正确答案对比

  类型 3 — 格式转换:
    给一段非结构化文本 → 要求按特定格式输出
    验证: 格式校验 + 关键字段检查

设计原则:
  → 必须需要 LLM 推理能力（不能用正则/规则解决）
  → 验证是确定性的（Coordinator 能程序化判断对错）
  → 题目与实际工作相关（验证 Miner 是否有能力做好结构化）
  → 题库定期轮换，防止缓存答案
  → 一次 PoW 对应一次 /submit 调用（不是每条 entry 都做）
```

### 4.2.3 同 IP 衰减

同一 IP 下注册过多 Miner 时，自动压缩后续 Miner 的提交上限。
信用分良好（60+）及以上的 Miner 不受 IP 衰减影响。

```
同一 IP 下注册的 Miner 数量（仅统计信用分 < 60 的 Miner）:
  1-10 个:  正常（按信用分等级的上限）
  11-20 个: 每个上限降为原来的 50%
  21-50 个: 每个上限降为原来的 20%
  50+ 个:   每个上限降为 5 条/Epoch

信用分 ≥ 60（良好/优秀 tier）的 Miner:
  → 不受 IP 衰减影响，始终按信用分等级的正常上限
  → 已用 12+ 个达标 Epoch 证明了自己的价值

不拒绝注册，合法场景（同一公司/学校）仍可参与
但大规模 Sybil 的单个身份提交能力被压缩
```

Phase A 校验 Miner 选择时：排除与原始提交者同 IP 的 Miner，防止 Sybil 身份互相校验。

### 4.2.4 三层叠加的防御效果

```
攻击场景: 注册 100 个新 Miner（credit=0）
  Layer 1: 每个 100 条/Epoch → 总共 10,000 条/Epoch
  Layer 2: 每次提交 100% PoW → 100 个 Miner × ~10 次提交 = 1,000 次 LLM 调用仅用于 PoW
  Layer 3: 同 IP 50+（新 Miner credit < 60）→ 每个降为 5 条 → 总共 500 条/Epoch

  对比诚实 Miner（credit=80）:
    无上限，PoW 概率 1%，几乎无额外成本

攻击者的成本:
  → 1,000 次 PoW LLM 调用（仅证明能力，无任何产出）
  → 加上 10,000 次实际工作的 LLM 调用（爬取+清洗+结构化）
  → 全部 rejected 后: 信用分不增长，下个 Epoch 同样的成本
  → 用代理池绕过 IP: 额外 $5-10/天，但 Layer 1 + Layer 2 仍生效

诚实 Miner 的成本:
  → 16 天达标后: 无上限，1% PoW → 几乎零额外成本
  → 信用分是不可转让的"工作证明"
```

```
提交时完整检查:
  Miner 提交 → 查询本 Epoch 已提交数量
    → 已达到信用等级上限（含 IP 衰减）→ 拒绝，返回 "rate_limit_exceeded"
    → 未达到 → 触发 PoW？
      → 是 → 验证通过后继续
      → 否 → 继续
    → url_patterns 校验（如 DataSet 配置了 url_patterns）
      → URL 不匹配任何 pattern → 拒绝
    → dedup_hash 去重检查
      → 已存在 pending 或未过期 confirmed → 拒绝
    → 接受提交
```

### 4.3 数据处理三阶段

```
阶段 1 — 爬取 (Crawl)
  访问目标 URL → 获取原始 HTML

阶段 2 — 清洗 (Clean)
  去除广告、导航、脚本等无关内容
  → 产出：cleaned_data（纯文本或精简 HTML）

阶段 3 — 结构化 (Structure)
  根据 DataSet Schema 从 cleaned_data 中提取字段
  → 产出：structured_data（符合 Schema 的 JSON）
```

爬取 + 清洗 =
客观过程
，结果的核心内容应高度一致（动态内容造成的差异由相似度阈值吸收），用于 Repeat Crawl 真实性校验（Phase A）。
结构化 =
半主观过程
，存在合理差异，由 Validator 基于 M0 自己的 cleaned_data 评估提取质量（Phase B）。

### 4.4 日常工作循环

```
1. 从 Subnet Hub 获取活跃 DataSet 列表
2. 选择目标 DataSet
3. 发现新 URL → 爬取 → 清洗 → 结构化
4. 提交前 Coordinator 自动检查 dedup_hash 是否已被占用 → 接受/拒绝
5. 每 Epoch 完成 ≥ 80 条有效提交
6. Epoch 结算后：
   → 达标 → 所有 pending 数据转为 confirmed，获得奖励
   → 未达标 → 所有 pending 数据转为 rejected，无奖励
```

### 4.5 正常提交格式

```
{
  "dataset_id":     "ds_x_posts",
  "miner_address":  "0xABC...",
  "entries": [
    {
      "url":              "https://x.com/user/status/123",
      "cleaned_data":     "清洗后的文本/精简HTML",
      "structured_data":  { "post_id": "123", "content": "...", ... },
      "crawl_timestamp":  1709827200
    }
  ],
  "signature":      "0x..."
}
```

### 4.6 重复爬取提交格式

被选中做重复爬取的 Miner 只提交清洗数据（不做结构化）：

```
{
  "eval_task_id":   "eval_00542",
  "miner_address":  "0xDEF...",
  "url":            "https://x.com/user/status/123",
  "cleaned_data":   "清洗后的文本/精简HTML",
  "crawl_timestamp": 1709828100,
  "signature":      "0x..."
}
```

---

## 第五章 Miner 评估机制

### 5.1 设计原理

评估分为两层，
先验真、后评质
：

|  | Phase A: 真实性校验（先做） | Phase B: 质量评估（后做） |
| --- | --- | --- |
| 问题 | Miner 提交的 cleaned_data 是否来自真实网页？ | Miner 的 structured_data 提取质量是否达标？ |
| 方式 | 校验 Miner 独立爬取同一 URL，纯文本相似度对比 | Validator 基于 M0 自己的 cleaned_data（已验真）评估 structured_data |
| 覆盖 | 页面真实性 + 清洗正确性 | 结构化提取质量 |
| 成本 | 期望 1.15 次 crawl/样本 | 低（Validator 本地评估） |

核心思路
：Phase A 通过校验 Miner 独立爬取来验证 M0 的 cleaned_data 的真实性。Phase A 通过后，M0 的 cleaned_data 被确认为真实可信，Validator 在 Phase B 中直接基于它来评估 M0 的 structured_data 提取质量。M1 的 cleaned_data 仅用于 Phase A 的相似度对比（真/假判定），不参与 Phase B 的质量评估——因为 M1 和 M0 是竞争关系，M1 有经济动力通过微调 cleaned_data 来干扰评估。

为什么 Phase B 使用 M0 自己的 cleaned_data 而非校验 Miner 的
：

M1 和 M0 是竞争关系（共享 Miner 奖励池），M1 有经济动力压低 M0 的评分。如果 Phase B 使用 M1 的 cleaned_data 作为评估基准，M1 可以通过微调 cleaned_data（改几个数值，整体相似度仍 ≥ 75% 通过 Phase A）来干扰 Phase B 评估，导致诚实 M0 被误伤。使用 M0 自己的 cleaned_data 彻底消除了这个攻击面。

M0 同步篡改 cleaned_data 和 structured_data 的风险评估
：

理论上 M0 可以同步篡改两者使其完美自洽。但篡改不影响 miner_score（Phase B 评估的是自洽性），不增加收益，反而增加工作量。理性 Miner 不会做这件事。非经济动机的数据投毒通过协议外手段缓解：信用分限流（新 Miner 100 条/Epoch + AI PoW 100% 触发）、同 IP 衰减、Owner 定期 API 抽检、数据消费者举报机制。

为什么由 Validator 评估质量，而非让 M1 也做结构化后交叉对比
：

一个替代设计是让 M1 也做结构化（与 M0 完全相同的工作），然后 Validator 只做 M0.structured vs M1.structured 的字段级对比。这种方式更"客观"，但有一个致命缺陷：
M1 没有经济激励用好模型做结构化
。M1 的收益较低（repeat task 权重仅为 2，低于正常提交的 3），理性的 M1 会用最便宜的模型，导致 M1.structured 本身就是低质量的——两份烂数据对比显示"完美一致"，高分但低质。

当前设计借鉴了强化学习（RL）中的核心洞察：
评估（判断好坏）远比生成（产出结果）简单。
在 RLHF 中，Reward Model 通常比 Policy Model 小 1-2 个量级仍然有效——因为判断一篇文章好不好远比写一篇好文章容易。

映射到本协议：

```
RL 类比:
  Policy Model (生成者) = Miner（从 cleaned_data 中提取 15 个字段 → 困难）
  Reward Model (评估者) = Validator（看字段值是否与 cleaned_data 对得上 → 简单得多）

Miner 的任务: 理解页面结构、识别字段边界、处理各种异常格式 → 需要强模型
Validator 的任务: post_id="123"，cleaned 中有没有 "123"？→ 近似字符串匹配

Miner 可能需要 GPT-4 级别才能做好
Validator 可能用 GPT-3.5 甚至更轻的模型就能准确判断大部分字段
```

因此，当前设计的激励对齐是：

```
清洗（客观过程，好模型差模型结果差不多）→ M1 做，不需要强经济激励
评估（需要判断力但比生成简单）→ Validator 做，有质押 + 高收益保证模型质量
生成（最困难，需要强模型）→ Miner 做，以挖矿收益为生

每个角色做自己有能力且有激励做好的事：
  M1 只清洗 → 50% 工作量，无需 LLM
  Validator 评估 → 模型门槛低，但有 accuracy² 加权的强激励
  Miner 结构化 → 模型门槛高，但有 (avg_score)² 加权的强激励
```

### 5.2 评估流程总览

```
Miner 提交 (cleaned_data + structured_data)
     │
  抽样 30%
     │
  ┌──┴───────────────────────────────────────────────┐
  │ Phase A: 真实性校验（先做）                        │
  │   ├── Step 1: 抽 1 Miner (M1) 独立爬取+清洗      │
  │   ├── M0 vs M1 纯文本相似度 ≥ 75% → 通过           │
  │   ├── 不一致 → Step 2: 再抽 1 Miner (M2)         │
  │   └── 三者裁决                                    │
  │                                                   │
  │   通过 → M0 的 cleaned_data 被确认为真实           │
  │   失败 → miner_score = 0，结束                    │
  └──┬───────────────────────────────────────────────┘
     │
  ┌──┴───────────────────────────────────────────────┐
  │ Phase B: 质量评估（后做，使用 M0 自己的数据）      │
  │   Validator 收到:                                 │
  │     cleaned_data    = M0 的 cleaned_data（已验真） │
  │     structured_data = M0 的结构化 JSON（被评估）   │
  │     dataset_schema  = Schema                      │
  │   → 评估 structured_data 是否正确提取了 cleaned    │
  │   → 产出: miner_score                             │
  └──┬───────────────────────────────────────────────┘
     │
  最终评分 → miner_score
```

### 5.3 Phase A: 真实性校验（先做）

对每个评估样本，系统触发渐进式 Repeat Crawl。

对比方式 — 纯文本相似度
：

```
对比流程：
  1. 对两份 cleaned_data 直接计算文本相似度（余弦相似度或编辑距离归一化）
  2. 相似度 ≥ 75%（consistency_threshold）→ 判定为"一致"

不需要剥离数字或其他预处理。清洗步骤已经去除了广告、导航栏、推荐区、
脚本等无关内容，只留核心内容。动态内容（数字变化、时间描述变化、
个性化内容等）造成的相似度波动由阈值吸收：

  真实页面 vs 真实页面 → 核心内容一致，仅少量动态残留 → 相似度 ~85-95%
  真实页面 vs 伪造页面 → 核心内容完全不同 → 相似度 ~20-50%
  阈值 75% 在两者之间，足以区分
```

定义
：
M0
= 原始提交者的清洗数据。

```
Step 1 — 抽 1 个 Miner（排除原始提交者 + 同 IP Miner）独立爬取该 URL → 清洗 → M1

  M0 vs M1 一致（文本相似度 ≥ 75%）？
    → 一致 → 真实性校验通过 ✓
      → 进入 Phase B

Step 2 — 不一致 → 再抽 1 个 Miner（排除原始提交者、M1 和同 IP Miner）→ 清洗 → M2

  现在有 M0, M1, M2 三份数据，进行裁决：

  情况 A — 存在一致对:
    M0 ≈ M2 → M0 真实，M1 异常
      → 真实性校验通过 ✓

    M1 ≈ M2 → M0 造假
      → 真实性校验失败 ✗ → miner_score = 0

  情况 B — 三者两两均不一致:
    三对相似度中最高值 ≥ 50%（dynamic_data_threshold）:
      → 判定为动态数据变化，乐观认定 M0 为真
      → 真实性校验通过 ✓

    三对相似度最高值 < 50%:
      → 不可判定 → 该样本作为无效任务处理，不评分也不计入 avg_score
```

### 5.4 Phase B: 质量评估（后做）

前提
：Phase A 已通过，M0 的 cleaned_data 被确认为真实可信。

两种评估模式
：

```
每个评估任务，Coordinator 掷骰子决定模式:

  90% — 单 Validator 模式:
    从 ready_pool 选 1 个 Validator → 评估 → 产出 miner_score
    （可能被替换为 Golden Task，按该 Validator 信用分概率）

  10% — 多 Validator 共识模式（Peer Review）:
    从 ready_pool 选 5 个 Validator → 各自独立评估 → 5 个分数
    → 取中位数作为 consensus_score → 作为 miner_score
    → 同时记录每个 Validator 与共识的偏差 → 用于 Validator peer_review_accuracy
    → 5 个 Validator 互不可见对方评分（无锚定效应）
```

评估包（两种模式完全一致）
：

```
Validator 收到评估包:
  {
    cleaned_data:     M0 的清洗数据（Phase A 已验真）
    structured_data:  M0 的结构化 JSON（被评估对象）
    dataset_schema:   Schema 定义
  }

评估维度:
  字段完整性（30%）:
    required 字段是否存在于 structured_data 中

  值准确性（40%）:
    structured_data 的字段值是否与 cleaned_data 中的对应内容一致

  类型正确性（15%）:
    数据类型是否符合 Schema 定义

  信息充分性（15%）:
    cleaned_data 中的明显信息是否被 structured_data 遗漏

→ 产出: miner_score (0-100)
```

Peer Review 共识计算
：

```
5 个 Validator 评分: s1, s2, s3, s4, s5
consensus_score = median(s1, s2, s3, s4, s5)
miner_score = consensus_score

每个 Validator 的 peer review 偏差:
  deviation_i = |s_i - consensus_score|
  peer_review_accuracy_i = 1 - deviation_i / 100

设计意图:
  → Miner: 10% 的评估由 5 人共识，比 1 人评分更可靠
  → Validator: 在真实任务上与同行校准评分标准
  → Validator 无法区分自己收到的是单 Validator 模式还是共识模式
    （评估包格式完全一致，只是 Coordinator 侧决定如何使用结果）
```

### 5.5 最终评分

```
Phase A 通过:
  → 单 Validator 模式: miner_score = Validator 评分
  → 共识模式: miner_score = consensus_score（中位数）
Phase A 失败 → miner_score = 0（数据造假）
```

### 5.6 Phase A 造假升级校验

一旦某个 Miner 的任何一条提交 Phase A 失败（数据造假），该 Miner 本 Epoch 内的所有剩余提交立即触发 100% 校验。

```
正常流程: Miner 的提交被 30% 抽样评估
造假触发: Phase A 失败 → 该 Miner 标记为 suspect
  → 本 Epoch 内该 Miner 尚未评估的所有提交 → 全部进入评估队列
  → 100% 评估（每条都做 Phase A + Phase B）
  → 不再是抽样，而是全量校验

设计意图:
  → Phase A 失败 = 数据造假，不是质量低
  → 造假者可能只有部分提交是假的，但无法信任其任何提交
  → 100% 校验确保每条数据都经过验证
  → 对诚实 Miner 无影响（Phase A 不会失败）
  → 增加的校验成本由造假者的存在频率决定（正常情况下极少触发）
```

### 5.7 流程图

```
Epoch 内所有提交（5000 条）
        （Phase A 造假触发的 100% 校验不在此流程内）
                    │
               随机抽 30%
                    │
             1500 条评估样本
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    样本 #1      样本 #2  ...  样本 #500
        │           │           │
   Phase A       Phase A      Phase A
   Step1: 抽1人  Step1: 抽1人  Step1: 抽1人
   (纯文本       (纯文本       (纯文本
    相似度对比)   相似度对比)   相似度对比)
        │           │           │
    ┌───┴───┐   ┌───┴───┐   ┌───┴───┐
    ▼       ▼   ▼       ▼   ▼       ▼
  一致    不一致 一致   不一致 一致   不一致
    │    →Step2   │    →Step2   │    →Step2
    │    →裁决    │    →裁决    │    →裁决
    ▼       │     ▼       │     ▼       │
  Phase B   │   Phase B   │   Phase B   │
  Validator │   Validator │   Validator │
    │     通过/   │     通过/   │     通过/
    │     失败    │     失败    │     失败
    ▼       ▼     ▼       ▼     ▼       ▼
  miner   通过→   miner  通过→  miner  通过→
  _score  Phase B _score Phase B _score Phase B
          失败→0         失败→0        失败→0
```

### 5.8 成本分析

假设 Miner 诚实率 90%，网页稳定率 95%，每 Epoch 1500 个评估样本（5000 条 × 30%）：

| 场景 | 概率 | Repeat crawl 次数 |
| --- | --- | --- |
| Step 1 通过 | ~85% | 1 |
| 需要 Step 2 | ~15% | 2 |
| 期望值 |  | 1.15 次/样本 |

|  | 旧协议 (v1.3) | 新协议 (v1.6) |
| --- | --- | --- |
| Repeat crawl Miner 工作 | 500 × 4 = 2,000 次 | 1500 × 1.15 ≈ 1,725 次 |
| Validator 评估 | 500 次 | 2,100 次（Phase B: 1500 × (90%×1 + 10%×5)） |
| Miner 额外工作总计 | 2,000 | 1,725 （减少 14%） |

### 5.9 重复爬取 Miner 的激励

被选中做重复爬取的 Miner：

- 计入其 task_count

- 工作量约为正常提交的 50%（不调 LLM）

- 其 cleaned_data 用于 Phase A 真实性裁决（不参与 Phase B 质量评估）

### 5.10 Miner avg_score 计算

Miner 的 avg_score 综合两类任务的得分，
被抽样的正常提交得分权重为 3，重复爬取任务得分权重为 2
。

```
定义：
  sampled_scores[]  = Miner 本 Epoch 被抽样评估的正常提交的 miner_score 列表
  repeat_scores[]   = Miner 本 Epoch 完成的重复爬取任务的一致性得分列表

avg_score = (3 × Σ sampled_scores + 2 × Σ repeat_scores)
          / (3 × |sampled_scores| + 2 × |repeat_scores|)
```

重复爬取任务得分
：重复爬取 Miner 的得分 = 其清洗数据与 M0 的纯文本相似度（0-100）。如果参与了 Step 2 裁决且站在"正确"一方（一致对中），得分 = 该一致对的相似度。

示例：

| 任务类型 | 得分 | 权重 | 加权分 |
| --- | --- | --- | --- |
| 正常提交被抽样 #1 | 85 | ×3 | 255 |
| 正常提交被抽样 #2 | 90 | ×3 | 270 |
| 重复爬取 #1 | 92 | ×2 | 184 |
| 重复爬取 #2 | 88 | ×2 | 176 |
| 合计 |  | 3+3+2+2=10 | 885 |
| avg_score |  |  | 885 / 10 = 88.5 |

边界保护
：如果 Miner 被评估的条目总数（sampled + repeat）< 3，则 avg_score = max(实际计算值, 70)，给予"疑罪从无"保护。

### 5.11 协议参数

| 参数 | 初始值 | 说明 |
| --- | --- | --- |
| consistency_threshold | 75% | Phase A Step 1 一致性阈值 |
| dynamic_data_threshold | 50% | Phase A 情况 B 中判定"动态数据"的最低相似度 |

---

## 第六章 Epoch 质量门控

### 6.1 概述

Epoch 结算时，系统对每个 Miner 执行质量门控。
未达标的 Miner 不仅不获得奖励，其本 Epoch 的所有提交数据将被拒绝，不写入 DataSet。

这确保 DataSet 中只包含达标 Miner 的数据，维护数据集整体质量。

### 6.2 达标条件

Miner 必须
同时满足
以下两个条件才算达标：

| 条件 | 阈值 | 说明 |
| --- | --- | --- |
| 有效提交数 | ≥ 80 条 | 防止投机式少量提交（含正常提交 + 重复爬取任务） |
| 平均评分 | ≥ 60 分 | 保证基本数据质量（avg_score ≥ 60，计算方式见 5.9） |

### 6.3 Epoch 结算流程

```
Epoch 结束（UTC 00:00）
        │
        ▼
  对每个 Miner 检查：
        │
        ├── task_count < 80？
        │     → 未达标
        │
        ├── avg_score < 60？
        │     → 未达标
        │
        └── 两个条件都满足？
              → 达标
        │
        ▼
  ┌─────────────────────────────────────────────┐
  │              达标 Miner                      │
  │                                             │
  │  1. 所有 pending 数据 → confirmed            │
  │     → 正式写入 DataSet                       │
  │     → 对外可见可查询                          │
  │                                             │
  │  2. 信用分 += 5（上限 100）                   │
  │                                             │
  │  3. 计算奖励                                 │
  │     weight = (avg_score)² × task_count       │
  │     reward = miner_pool × weight / Σ weights │
  │                                             │
  │  4. 奖励可通过 claimReward() 领取            │
  └─────────────────────────────────────────────┘
        │
  ┌─────────────────────────────────────────────┐
  │             未达标 Miner                     │
  │                                             │
  │  1. 所有 pending 数据 → rejected             │
  │     → 从暂存区删除                           │
  │     → dedup_hash 占位被释放                  │
  │     → 这些内容可以被其他 Miner 重新提交      │
  │                                             │
  │  2. 信用分 -= 15（下限 0）                    │
  │                                             │
  │  3. 奖励 = 0                                │
  │                                             │
  │  4. 不额外惩罚                               │
  │     → Miner 可在下个 Epoch 继续参与           │
  │     → 改善数据质量后自然达标                  │
  └─────────────────────────────────────────────┘
```

### 6.4 去重释放与冷却机制

当未达标 Miner 的数据被 rejected 时：

```
Step 1 — 公布 rejected 数据的 URL 列表:
  → 被 rejected 的所有提交的 URL 公开发布（链下公告或 API 可查）
  → 目的: 透明，其他 Miner 知道哪些内容即将重新开放

Step 2 — 冷却期:
  → rejected 的 dedup_hash 不会立即释放
  → 冷却期 = 1 Epoch（1 天）
  → 冷却期内该 dedup_hash 不可被任何 Miner 提交
  → 防止同一 Miner（或同 IP Miner）立即用缓存数据重新提交

Step 3 — 冷却期结束后释放:
  → dedup_hash 重新变为"可提交"状态
  → 其他 Miner 可以提交相同内容

Step 4 — 这批 URL 触发 100% 校验:
  → 冷却期结束后，这批 dedup_hash 被标记为 "high_risk"
  → 后续提交这些 dedup_hash 的数据，不走 30% 抽样，而是 100% 校验
  → 每条都做 Phase A + Phase B
  → high_risk 标记持续 3 个 Epoch 后自动解除
```

设计意图：

- 冷却期阻止缓存数据重提

- 100% 校验确保接手这些内容的新 Miner 是真实爬取

- URL 公布让好 Miner 有准备时间，冷却期结束后高效接手

- 3 个 Epoch 后 high_risk 解除，避免永久标记的维护成本

### 6.5 边界情况处理

Q: 如果 Miner 提交了 100 条，但只有 3 条被评估，avg_score 样本太少怎么办？

avg_score 基于被评估的提交和完成的重复爬取任务计算（见 5.9 节）。两类任务合计评估条目 < 3 时，avg_score = max(实际计算值, 70)，给予"疑罪从无"保护。

- 30% 抽样率意味着提交 100 条约有 30 条被评估，加上重复爬取任务，样本通常足够

- 极端情况下的保护机制避免误伤

Q: Miner 正好有 80 条，avg_score 正好 59.5，被卡在门槛上？

阈值是硬性的。但 60 分是一个较低的门槛（满分 100），正常爬取且使用合格模型结构化的 Miner 通常能达到 75+。长期低于 60 说明数据质量确实有问题。

Q: Epoch 内前半段提交的数据已经被 pending 了，后半段 Miner 掉线没达到 80 条，前面的数据怎么办？

全部 rejected。这是"全有或全无"的设计——要么整个 Epoch 的数据都入库，要么都不入库。这避免了部分入库导致的复杂性，也给 Miner 一个明确的激励：确保每天都能完成足够的高质量提交。

### 6.6 质量门控的设计意图

```
不设门控的问题：
  → 低质量 Miner 的垃圾数据充斥 DataSet
  → 数据消费者对数据质量失去信任
  → DataSet 的价值被稀释

设门控的好处：
  → DataSet 中每条数据都来自达标 Miner → 整体质量有底线保障
  → 去重释放机制让好内容不会被低质量数据永久占用
  → "全有或全无"给 Miner 强激励：持续在线、持续高质量
  → 60 分阈值足够宽容，不会误伤正常 Miner
  → 信用分 + AI PoW + IP 衰减让 Sybil 攻击成本随时间增加

门控不解决的问题（由评估机制解决）：
  → 区分"及格"和"优秀"→ 由 (avg_score)² 加权奖励区分
  → 区分 Validator 质量 → 由 Golden Task 解决
```

---

## 第七章 Validator 管理

### 7.1 准入规则

容量上限
：Validator 数量 ≤ ceil(active_miner_count / 5)。

最低质押
：Validator 须在 RootNet 质押 ≥ min_stake 个 AWP（初始建议 1,000 AWP，Owner 可通过治理调整）。

```
注册流程：

新 Validator 申请加入:
  → 质押 < min_stake → 拒绝
  → 当前 Validator 数量 < 上限？
    → 是 → 直接加入，立即生效
    → 否（已满）→ 竞争替换:
      → 找当前所有不在保护期内的 Validator 中 AWP 质押最小的 V_min
      → 新 Validator 质押 > V_min 质押？
        → 否 → 拒绝
        → 是 → 替换 V_min（立即生效：V_min 被移除，新 Validator 加入）
      → 所有 Validator 都在保护期内 → 拒绝（等保护期结束后重试）
```

Miner 数量下降导致 Validator 超额
：

```
validator_count > ceil(miner_count / 5):
  → 不主动剔除任何 Validator（已有 Validator 继续工作和获得奖励）
  → 不接受新 Validator 加入（除非通过竞争替换）
  → 自然恢复: Miner 回升或低质押 Validator 被竞争替换
```

### 7.2 保护期

每个 Validator 加入时获得
1 个 Epoch 的保护期
。保护期内不会被竞争替换淘汰。

```
保护期规则:
  加入时: protected_until = current_epoch + 1
  保护期内: 不会被竞争替换

保护期失效条件（提前终止）:
  → Validator 主动减少 AWP 质押 → 保护期立即失效
  → 单 Epoch accuracy < 20（严重作恶）→ 无视保护期，立即驱逐
```

### 7.3 Validator 信用分与任务频率

Validator 引入信用分机制，根据历史表现动态调整
任务分配频率
和
Golden Task 混入比例
。与 Miner 信用分的设计对称：新 Validator（或被驱逐后换地址重来的）从零开始积累信任，历史信用不可转移。

```
信用分计算：
  初始值 = 0
  达标 Epoch（eval_count >= min_eval_count 且 accuracy >= 60）: credit += 5（上限 100）
  未达标: credit -= 15（下限 0）
  连续 3 Epoch 未达标: credit = 0
```

| Validator 信用分 | 等级 | 任务间隔 | 约每 Epoch | Golden Task 比例 | 达到所需 |
| --- | --- | --- | --- | --- | --- |
| 0 - 19 | 新手 | ≥ 10 分钟 | ~144 个 | 40% | 0（初始） |
| 20 - 39 | 受限 | ≥ 5 分钟 | ~288 个 | 30% | 4 达标 Epoch |
| 40 - 59 | 普通 | ≥ 2 分钟 | ~720 个 | 20% | 8 达标 Epoch |
| 60 - 79 | 良好 | ≥ 30 秒 | ~2,880 个 | 10% | 12 达标 Epoch |
| 80 - 100 | 优秀 | ≥ 10 秒 | ~8,640 个 | 5% | 16 达标 Epoch |

设计意图
：

```
频率限制（而非总量限制）:
  → 新手一天仍能做 ~144 个任务，参与感正常
  → 但无法在短时间内大量恶意评估
  → 优秀 Validator ≥ 10 秒间隔（一次评估至少需要 LLM 推理时间，低于 10 秒大概率是随机打分）
  → 10 秒下限是质量保障，不是限制

Golden Task 比例随信用分递减:
  → 新手 40%: 几乎一半任务是考试，偷懒立刻暴露
  → 优秀 5%: 极少干扰，但保持长期威慑
  → 与 Miner AI PoW 设计对称:
    Miner 新手 100% PoW → 优秀 1%（证明 AI 能力）
    Validator 新手 40% Golden → 优秀 5%（证明评估能力）

被驱逐后换地址重来:
  → credit = 0 → 新手 tier
  → 10 分钟间隔 + 40% Golden Task → 几乎无法作恶
  → 需要 16 个达标 Epoch 才能恢复优秀
  → 历史信用不可转移，攻击者的积累被清零
```

任务分配机制 — 等候池模式
：

Coordinator 不主动选 Validator 推送任务，而是维护一个
等候池（ready_pool）
，评估任务从等候池中随机选取 Validator。

```
Validator 入池流程:
  Validator 完成上一个任务（或首次上线）
    → 检查: 距上次任务完成 ≥ 信用分对应的任务间隔？
    → 满足 → 加入 ready_pool
    → 不满足 → 等待，直到间隔满足后自动入池

评估任务分配流程:
  1. 评估任务产生（Phase B 质量评估）
  2. 掷骰子: 单 Validator 模式（90%）还是 Peer Review 模式（10%）？
  3a. 单 Validator 模式:
      → 从 ready_pool 中随机选 1 个 Validator V
      → 根据 V 的信用分等级，掷骰子决定是否替换为 Golden Task
      → 推送任务给 V → V 从 ready_pool 移除
      → miner_score = V 的评分
  3b. Peer Review 模式:
      → 从 ready_pool 中随机选 5 个 Validator（不足 5 个则降级为单 Validator 模式）
      → 推送同一评估包给 5 个 Validator → 5 个均从 ready_pool 移除
      → 5 个 Validator 独立评分 → 取中位数作为 consensus_score
      → miner_score = consensus_score
      → 每个 Validator 的偏差记录为 peer review 得分（见 7.9 节）
  4. Validator 完成任务后 → 等待间隔 → 重新入池

ready_pool 为空时:
  → 任务进入等待队列
  → Validator 入池后自动消费队列

优势:
  → 分配逻辑极简：从池中随机选，O(1)
  → 天然满足间隔限制：不满足间隔的进不了池
  → 更公平：随机选择，Coordinator 无法偏袒特定 Validator
  → Validator 无法预测下一个任务是什么（防串通）
  → Golden Task 混入在选定 Validator 之后决定，无法被预测
  → Peer Review 让 Validator 在真实任务上互相校准评分标准
```

### 7.4 最低工作量

Validator 每 Epoch 须完成 ≥ min_eval_count 次评估，否则视为未达标。min_eval_count 根据信用分等级调整：

```
新手 tier（max ~144 个/Epoch）: min_eval_count = 3
其他 tier:                      min_eval_count = 10

Epoch 结算时:
  eval_count < min_eval_count:
    → 本 Epoch 奖励 = 0（未达标，不发奖励）
    → 不计入"作恶"标记（是"没干活"不是"干坏了"）
    → 信用分不变（不惩罚也不奖励）
    → consecutive_idle++
    → consecutive_idle >= 3 → 移除 Validator 资格（占位不干活）

  eval_count >= min_eval_count:
    → consecutive_idle = 0
    → 进入质量检查（Golden Task accuracy 判定）
```

### 7.5 Golden Task — 问题与方案

如果 Validator 之间用共识互评，所有 Validator 都有动力用小模型偷懒。导致劣币驱逐良币。

引入
Golden Task
— 系统预先知道正确答案的评估任务，秘密混入 Validator 的日常评估中，直接检验 Validator 的评分能力。
Validator 不知道哪些是 Golden Task。
混入比例根据 Validator 信用分等级动态调整（新手 40% → 优秀 5%）。

### 7.6 Golden Task 构造

一个 Golden Task 完整模拟真实评估任务，
其数据来源于历史真实爬取结果
，而非人工合成：

```
{
  "golden_task_id": "gt_00142",
  "dataset_id":     "ds_x_posts",

  "cleaned_data":      "Miner 的清洗数据",
  "structured_data":   { "post_id": "123", ... },

  "correct_scores": {
    "miner_score": 94
  }
}
```

构造原则
：

- cleaned_data 取自真实 Miner 的历史爬取数据（高评分样本）

- structured_data 取自真实 Miner 的历史提交

- correct_scores 由顶级模型 + 人工交叉标注确定

- 格式与真实 Phase B 评估包完全一致（cleaned_data + structured_data + schema），Validator 无法区分

Validator 收到 Golden Task 后执行与真实 Phase B 完全相同的质量评估流程。

### 7.7 Golden Task 评估流程

Golden Task 仅在单 Validator 模式（90%）下混入，Peer Review 模式（10%）不混入 Golden Task。

```
Step 1 — 评估任务产生，掷骰子: 90% 单 Validator / 10% Peer Review
Step 2 — 单 Validator 模式时: 从 ready_pool 中随机选 Validator V
Step 3 — 根据 V 的信用分等级掷骰子，决定是否替换为 Golden Task
        （新手 40%，受限 30%，普通 20%，良好 10%，优秀 5%）
Step 4 — 推送任务给 V（V 无法区分 Golden Task 和真实任务）
Step 5 — V 评估并返回 miner_score
Step 6 — 系统检查：如果是 Golden Task，对比 V 的评分与正确评分
Step 7 — V 从 ready_pool 移除，完成后等待间隔，重新入池

golden_accuracy = 1 - sqrt(avg((v_score - correct_score)²)) / 100
```

> 注 ：使用 RMSE（均方根误差）而非线性平均偏差，对大偏差施加更重惩罚。

### 7.8 Peer Review 评估流程

```
Step 1 — 评估任务产生，掷骰子命中 10% Peer Review 模式
Step 2 — 从 ready_pool 中随机选 5 个 Validator (V1-V5)
Step 3 — 同一评估包推送给 5 个 Validator（各自独立评估，互不可见）
Step 4 — 5 个 Validator 各自返回 miner_score
Step 5 — consensus_score = median(5 个分数)
Step 6 — miner_score = consensus_score
Step 7 — 记录每个 Validator 的偏差:
         peer_deviation_i = |score_i - consensus_score|

peer_review_accuracy = 1 - sqrt(avg(peer_deviation²)) / 100
```

> Peer Review 的双重价值 ： Miner 侧 ：共识得分比单人评分更可靠，减少单个 Validator 偏差对 Miner 的影响 Validator 侧 ：在真实任务上校准评分标准，Validator 无法区分单人模式和共识模式

### 7.9 Validator 综合 accuracy

Validator 的最终 accuracy 由 Golden Task 和 Peer Review 两个维度按 1:1 权重综合：

```
accuracy = (golden_accuracy + peer_review_accuracy) / 2

其中:
  golden_accuracy       = 1 - sqrt(avg((v_score - correct_score)²)) / 100
  peer_review_accuracy  = 1 - sqrt(avg(peer_deviation²)) / 100
  （两者均在 Epoch 结算时，取该 Validator 本 Epoch 所有对应任务的 RMSE）

示例:
  golden_accuracy = 92（与客观正确答案接近）
  peer_review_accuracy = 88（与同行共识接近）
  accuracy = (92 + 88) / 2 = 90

设计意图:
  Golden Task:    检验"Validator 是否有能力评估好"（与客观答案对齐）
  Peer Review:    检验"Validator 是否在真实任务上也认真评估"（与同行校准）
  1:1 权重:       两者同等重要，缺一不可

边界情况:
  Peer Review 参与次数 < 2（样本不足）:
    → accuracy = golden_accuracy（仅用 Golden Task，忽略 Peer Review）
  Golden Task 参与次数 < 2（样本不足）:
    → accuracy = peer_review_accuracy（仅用 Peer Review）
  两者参与次数都 < 2: 不参与 accuracy 判定，仅检查 eval_count 门控
```

### 7.10 评分示例

```
正确评分: miner_score = 94

Validator A（大模型）: 92 → 偏差² = 4   → RMSE = 2.0  → accuracy = 98.0
Validator B（小模型）: 78 → 偏差² = 256 → RMSE = 16.0 → accuracy = 84.0
Validator C（偷懒）:   60 → 偏差² = 1156 → RMSE = 34.0 → accuracy = 66.0

多个 Golden Task 时取所有偏差²的均值再开方
```

### 7.11 Golden Task 库管理

| 阶段 | 来源 | 数量 |
| --- | --- | --- |
| Phase 1 | 历史高共识真实数据 + Owner 顶级模型标注 + 人工审核 | 1,000 条 |
| Phase 2 | 持续从真实评估中筛选高共识样本自动扩展 | 10,000 条 |
| Phase 3 | 社区贡献 + 自动扩展 | 100,000+ 条 |

防泄露：库远大于每次使用量、每个 Validator 收到不同的 Golden Task、定期轮换、不公开。
防识别：所有 Golden Task 数据取自真实爬取历史，格式和分布与真实评估包无差异。

> 注 ：新手 Validator 40% 的任务是 Golden Task，对 Golden Task 库的消耗较大。库规模需要与活跃 Validator 数量和信用分分布匹配。

Golden Task 自动扩展（来自 Peer Review 高共识样本）
：

```
Peer Review 产生的高共识样本可以自动成为 Golden Task 候选：

筛选条件:
  → 5 个 Validator 评分标准差 < 3 分（高共识）
  → consensus_score 作为 correct_score
  → 自动加入 Golden Task 候选队列

审核流程:
  → Owner 定期审核候选队列
  → 通过 → 激活为正式 Golden Task
  → 拒绝 → 标记原因，不入库

正向循环:
  Peer Review 产出高共识样本
  → 扩展 Golden Task 库
  → 更精准地检验 Validator
  → 更好的 Validator 产出更可靠的 Peer Review
  → 库持续增长: 目标 1,000 → 10,000 → 100,000+
```

评估成本
：

```
每 Epoch 1500 个评估任务（5000 条 × 30% 抽样）:
  90% × 1 Validator = 1,350 次评估
  10% × 5 Validators = 750 次评估
  总计: 2,100 次评估

Peer Review 增加的代价换来:
  → Validator 评分标准对齐
  → 对真实任务（非 Golden Task）的二次校验
  → Peer Review accuracy 数据
```

### 7.12 惩罚与驱逐

核心原则
：Subnet 不 Slash AWP（无权操作 RootNet 质押），而是通过
罚没 Epoch 奖励 + 驱逐 + 信用分清零
惩罚 Validator。被驱逐后即使换地址重来，也必须从新手 tier（10 分钟间隔 + 40% Golden Task）重新开始。

Epoch 结算时，对每个 eval_count ≥ min_eval_count 的 Validator：

> 注 ：此处 accuracy 为综合 accuracy = (golden_accuracy + peer_review_accuracy) / 2（见 7.9 节）。

| accuracy 区间 | 判定 | 奖励 | 标记 |
| --- | --- | --- | --- |
| ≥ 60 | 正常 | 按 (accuracy)² × eval_count 加权分配 | flag_count = 0, credit += 5 |
| 40 - 60 | 低质量 | 正常发放（但因 accuracy² 权重已很低） | flag_count++, credit -= 15 |
| 20 - 40 | 作恶 | 本 Epoch 全部奖励罚没 | flag_count++, credit -= 15 |
| < 20 | 严重作恶 | 罚没 + 立即驱逐 + 30 天禁入 （无视保护期） | credit = 0 |

罚没奖励的去向
：被罚没的 ocDATA 份额重新分配给本 Epoch 其他合格 Validator。

累计惩罚与驱逐
：

| 条件 | 后果 |
| --- | --- |
| 连续 3 Epoch flag_count 增长（accuracy < 60） | 警告（链下通知） |
| 连续 5 Epoch flag_count 增长 | 移除 Validator 资格 + 7 天禁入, credit = 0 |
| 单次 accuracy < 20 | 立即移除 + 30 天禁入, credit = 0 |

被驱逐的 Validator
：

- AWP 质押正常退还（Subnet 不动 AWP）

- 本 Epoch 奖励罚没

- 禁入期内不可重新注册

- 空出的位置可被新 Validator 通过正常准入流程填补

- 即使换地址重新注册，信用分从 0 开始（新手 tier: 10 分钟间隔 + 40% Golden Task）

### 7.13 Validator 完整状态机

```
┌── 质押 >= min_stake AWP ──┐
                  ▼                            │
            [申请加入]                         │
                  │                            │
          ┌───────┴───────┐                   │
          ▼               ▼                   │
      有空位          已满                    │
          │               │                   │
          ▼           找不在保护期的           │
      立即加入        V_min                   │
          │               │                   │
          │         质押 > V_min?             │
          │          │     │                  │
          │         是     否→拒绝             │
          │          │                        │
          │        立即替换 V_min              │
          ▼              ▼                    │
    [保护期 1 Epoch]──►[活跃]                  │
     credit=0             │                   │
     10分钟间隔            │                   │
     40% Golden      Epoch 结算               │
                          │                   │
              ┌───────────┼───────────┐       │
              ▼           ▼           ▼       │
        eval < min    acc >= 60    acc 40-60   │
        奖励=0        正常发放     正常发放     │
        idle++        credit+=5   credit-=15   │
              │        flag=0     flag++        │
        idle>=3?      [继续]     flag>=5?      │
        是→驱逐                  是→驱逐7天    │
                                              │
              acc 20-40       acc < 20         │
              奖励罚没        奖励罚没          │
              credit-=15     立即驱逐30天       │
              flag++         credit=0          │
              flag>=5?                         │
              是→驱逐7天                       │
                                              │
                        驱逐后:                │
                        → AWP 质押正常退还 ────┘
                        → credit = 0
                        → 禁入期后可重新注册
                        → 从新手 tier 重新开始
```

### 7.14 协议参数

| 参数 | 初始值 | 可配置 | 说明 |
| --- | --- | --- | --- |
| min_stake | 1,000 AWP | Owner 可调 | 最低准入质押 |
| min_eval_count | 10 次/Epoch（新手 3 次） | Owner 可调 | 每天最低评估工作量 |
| validator_capacity_ratio | 1/5 | Owner 可调 | Validator 与 Miner 的数量比 |
| protection_period | 1 Epoch | 固定 | 新 Validator 保护期 |
| idle_eviction_threshold | 连续 3 Epoch | Owner 可调 | 未达标驱逐阈值 |
| flag_eviction_threshold | 连续 5 Epoch | Owner 可调 | 低质量驱逐阈值 |
| new_validator_interval | 10 分钟 | Owner 可调 | 新手 tier 任务间隔 |
| min_task_interval | 10 秒 | 固定 | 所有 Validator 的最低任务间隔（质量保障） |
| golden_ratio_new | 40% | Owner 可调 | 新手 tier Golden Task 比例 |
| golden_ratio_trusted | 5% | Owner 可调 | 优秀 tier Golden Task 比例 |
| peer_review_ratio | 10% | Owner 可调 | 评估任务触发 Peer Review 的概率 |
| peer_review_validators | 5 | Owner 可调 | Peer Review 每次选取的 Validator 数量 |

---

## 第八章 心跳机制

### 8.1 概述

Miner 和 Validator 每 60 秒向中心化 Subnet Coordinator 发送心跳。3 分钟无心跳标记为离线。

### 8.2 心跳消息

```
{
  "address":    "0xABC...",
  "role":       "miner",
  "subnet_id":  1,
  "timestamp":  1709827200,
  "datasets":   ["ds_x_posts", "ds_amazon"],
  "capacity":   10,
  "version":    "1.3.0",
  "signature":  "0x..."
}
```

### 8.3 心跳响应

```
{
  "status": "ok",
  "credit_score": 65,
  "credit_tier": "良好",
  "epoch_submit_count": 42,
  "epoch_submit_limit": 10000,
  "pow_probability": 0.05,
  "notifications": [
    { "type": "skill_update", "message": "请更新到 v1.3.0", "required": true }
  ],
  "pending_tasks": 3
}
```

### 8.4 在线列表用途

| 用途 | 说明 |
| --- | --- |
| Repeat Crawl 选人 | 从在线 Miner 中渐进式选人（排除原始提交者 + 同 IP Miner） |
| Validator 任务分配 | 等候池模式：满足间隔的 Validator 入池，任务产生时从池中随机选 |
| Skill 版本检查 | 版本过低不分配任务 |
| 容量调度 | capacity = 0 暂不分配 |
| 信用分限流 | 超过提交上限不接受新提交 |
| AI PoW | 根据信用分等级概率触发 AI 挑战 |
| IP 衰减 | 同 IP 过多 Miner 时压缩提交上限 |

---

## 第九章 Epoch 奖励计算

### 9.1 Epoch 周期

一个 Epoch = 1 天，每日 UTC 00:00 结算。

### 9.2 排放分配

```
每 Epoch 由 SubnetContract 根据排放表铸造 $ocDATA：
  排放量 = epochEmission(epoch_id)  // 内嵌衰减曲线
  ├── 41% → Miner Pool
  ├── 41% → Validator Pool
  └── 18% → Subnet Owner
```

> 注 ：$ocDATA 由 SubnetContract 直接铸造（SubnetContract 是 ocDATA 的 minter），不经过 RootNet。排放表（如每年减半）内嵌在合约中。

### 9.3 Epoch 结算完整流程

```
UTC 00:00 Epoch 结束
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 1: 计算每个 Miner 的 avg_score 和 task_count  │
  │    avg_score 计算方式见 5.9 节                       │
  │    task_count = 正常提交数 + 重复爬取任务数           │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 2: Miner 质量门控                              │
  │    对每个 Miner:                                     │
  │    → task_count ≥ 80 且 avg_score ≥ 60 → 达标        │
  │    → 否则 → 未达标                                   │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 3: 处理未达标 Miner                            │
  │    → 所有 pending 数据 → rejected                    │
  │    → dedup_hash 占位释放                             │
  │    → 奖励 = 0                                       │
  │    → 信用分 -= 15                                    │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 4: 处理达标 Miner                              │
  │    → 所有 pending 数据 → confirmed（入库 DataSet）    │
  │    → 信用分 += 5                                     │
  │    → 计算奖励:                                       │
  │      weight = (avg_score)² × task_count              │
  │      reward = miner_pool × weight / Σ weights        │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 5: Validator 门控与奖励                        │
  │    对每个 Validator:                                  │
  │                                                     │
  │    5a. 质押检查:                                     │
  │      质押 < min_stake（且不在保护期）→ 移除资格       │
  │                                                     │
  │    5b. 工作量检查:                                    │
  │      eval_count < min_eval_count → 奖励 = 0         │
  │      idle_count++，>= 3 → 移除                       │
  │                                                     │
  │    5c. 质量检查（需要 Golden Task + Peer Review）:       │
  │      accuracy = (golden_accuracy + peer_accuracy) / 2  │
  │      accuracy < 20 → 罚没 + 立即驱逐 + 30 天禁入       │
  │                      credit = 0                        │
  │      accuracy 20-40 → 罚没 + flag_count++              │
  │                       credit -= 15                     │
  │      accuracy 40-60 → 正常发放 + flag_count++          │
  │                       credit -= 15                     │
  │      accuracy >= 60 → 正常发放 + flag_count = 0        │
  │                       credit += 5                      │
  │      flag_count >= 5 → 驱逐 + 7 天禁入, credit = 0    │
  │                                                     │
  │    5d. 计算合格 Validator 奖励:                       │
  │      v_weight = (accuracy)² × eval_count             │
  │      reward = validator_pool × v_weight / Σ v_weights│
  │      罚没的份额重分配给合格 Validator                  │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 6: 本地持久化（先存 DB，再上链）                │
  │    → 将 Step 1-5 的完整计算结果写入 DB               │
  │      epochs.status = 'settling'                     │
  │      记录: 每个 Miner/Validator 的权重、奖励、状态变更│
  │    → 此时 DB 已有完整结算快照，可随时恢复             │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 7: 链上结算                                    │
  │    → 调用 SubnetContract.settleEpoch()               │
  │    → SubnetContract 铸造本 Epoch 的 $ocDATA          │
  │    → 按权重记录各参与者可领取额度                      │
  │    → 交易成功 → epochs.status = 'settled'            │
  │    → 交易失败 → 从 'settling' 状态恢复重试            │
  └─────┬──────────────────────────────────────────────┘
        │
  ┌─────▼──────────────────────────────────────────────┐
  │  Step 8: 异步后续                                    │
  │    → confirmed 数据上传 IPFS（异步，不阻塞结算）     │
  │    → rejected 数据的 dedup_hash 进入冷却队列         │
  │    → 参与者 claimReward(epoch) 领取                  │
  └────────────────────────────────────────────────────┘
```

结算原子性保障
：

```
Step 1-5 为纯计算，结果写入 DB（status = 'settling'）
Step 7 为链上操作，可能失败（gas 不足、网络问题等）
如果 Step 7 失败 → 从 'settling' 状态恢复 → 重新提交交易
IPFS 上传在 Step 8 异步进行，不阻塞结算流程
整个过程保证: DB 状态和链上状态最终一致
```

### 9.4 Miner 奖励（仅达标 Miner）

```
weight(miner) = (avg_score)² × task_count
reward(miner) = miner_pool × weight / Σ weight(all_qualified_miners)
```

> 设计意图 ：使用 avg_score 的平方使质量差异产生更大的收益差距。score=90 的 Miner 单条权重是 score=60 的 (90²/60²) = 2.25 倍，而非线性公式下的 1.5 倍。这强烈激励 Miner 追求更高质量。

示例（miner_pool = 10,000 $ocDATA）：

| Miner | avg_score | task_count | 达标？ | weight | 奖励 | 数据入库？ |
| --- | --- | --- | --- | --- | --- | --- |
| A | 92 | 100 | ​ | 846,400 | 4,184 | 100 条 confirmed |
| B | 85 | 50 | ​ | 361,250 | 1,785 | 50 条 confirmed |
| C | 70 | 200 | ​ | 980,000 | 4,844 | 200 条 confirmed |
| D | 55 | 80 | (分数<60) | 0 | 0 | 80 条 rejected |
| E | 75 | 60 | (数量<80) | 0 | 0 | 60 条 rejected |

Miner D 提交了 80 条但平均分只有 55 → 全部 rejected，80 个 dedup_hash 占位释放。
Miner E 质量不错但只提交了 60 条 → 全部 rejected，60 个 dedup_hash 占位释放。

### 9.5 Validator 奖励

```
前提: eval_count >= min_eval_count 且 accuracy >= 40（未被罚没）

accuracy = (golden_accuracy + peer_accuracy) / 2   （见 7.9 节）
v_weight(validator) = (accuracy)² × eval_count
reward(validator) = effective_pool × v_weight / Σ v_weights

其中:
  effective_pool = validator_pool + 被罚没 Validator 的份额
```

> accuracy < 40 的 Validator 本 Epoch 奖励归零，其份额重新分配给合格 Validator。 eval_count < min_eval_count 的 Validator 不参与分配。 如果 Epoch 内只有 Golden Task 数据或只有 Peer Review 数据，accuracy 取有数据的那一项。

### 9.6 奖励领取

```
参与者调用 subnetContract.claimReward(epoch)
  → 获得 $ocDATA (ERC-20)
  → PancakeSwap V4: $ocDATA ↔ $AWP
```

---

## 第十章 Subnet Coordinator

### 10.1 定位

中心化协调服务，负责任务调度、心跳管理、评估编排、Epoch 结算。不处理资金。

### 10.2 职责

```
1. 心跳管理 → 在线列表 + 通知推送 + 信用分查询
2. 数据提交 → dedup_hash 去重检查 + url_patterns 校验 + 信用分限流 + IP 衰减 + AI PoW 验证 + pending 状态管理 + IPFS 存储
3. Validator 管理 → 准入检查 + 竞争替换 + 保护期 + 质押监控
4. 评估编排:
   a. 30% 抽样
   b. Phase A: 渐进式 Repeat Crawl → 真实性校验
   c. Phase B: 维护 Validator 等候池（ready_pool），评估任务产生时从池中随机选 Validator，传入 M0 的 cleaned_data + structured_data + schema → 质量评估
   d. Golden Task: 选定 Validator 后，按其信用分比例决定是否替换为 Golden Task
5. Epoch 结算:
   a. Miner 门控 + confirmed/rejected + dedup_hash 释放 + 信用分更新
   b. Validator 门控 + 工作量检查 + accuracy 检查 + 奖励罚没/驱逐
   c. 权重计算 + SubnetContract.settleEpoch()
6. 数据刷新 → 定期扫描过期数据 → 加入刷新队列 → 随机指派 Miner（排除历史提交者 + 同 IP）
7. Golden Task → 从真实历史数据构造 + 存储 + 分发 + 轮换
8. DataSet 审核 → 接收创建申请 + 通知 Owner 审核 + 处理审核结果
```

### 10.3 完整数据流

```
Miner                 Coordinator              Validator
  │                        │                       │
  ├── heartbeat ──────────►│◄── heartbeat ─────────┤
  │  (返回信用分+限额)      │  (返回 eval_count 等) │
  │                        │                       │
  │                        │◄── registerValidator ──┤
  │                        │   准入检查/竞争替换     │
  │                        │                       │
  ├── submit ─────────────►│                       │
  │   (cleaned_data        │── 信用分限流 + IP 衰减  │
  │    + structured_data)  │── AI PoW 验证（按概率） │
  │                        │── dedup_hash 去重检查 │
  │                        │── url_patterns 校验   │
  │                        │── IPFS 存储            │
  │                        │── 状态 = pending       │
  │                        │                       │
  │                        │── 抽 30% 评估          │
  │                        │                       │
  │                        │── Phase A（先做）       │
  │◄── Repeat Crawl Step1 ─│                       │
  │    (排除原始提交者)      │                       │
  │    (只清洗)              │                       │
  ├── M1 cleaned_data ────►│                       │
  │                        │── M0 vs M1 一致？      │
  │                        │   一致 → Phase A 通过   │
  │                        │   不一致 ↓              │
  │◄── Repeat Crawl Step2 ─│                       │
  ├── M2 cleaned_data ────►│                       │
  │                        │── 三者裁决             │
  │                        │   → 通过/失败          │
  │                        │                       │
  │                        │── Phase B（后做）       │
  │                        │   从 ready_pool 随机     │
  │                        │   选 Validator V ────────►│
  │                        │   按 V 信用分决定         │
  │                        │   是否混入 Golden Task   │
  │                        │   评估包:               │
  │                        │   M0 的 cleaned_data   │
  │                        │   structured_data      │
  │                        │   schema               │
  │                        │◄── miner_score ────────┤
  │                        │   V 完成 → 等待间隔     │
  │                        │   → 重新入 ready_pool   │
  │                        │                       │
  │                        │── Epoch 结束           │
  │                        │── Miner 质量门控       │
  │                        │── Validator 门控:       │
  │                        │   质押/工作量/accuracy  │
  │                        │   罚没/驱逐             │
  │                        │── 刷新队列检查 + 指派    │
  │                        │── 信用分更新            │
  │                        │── 计算权重（平方公式）   │
  │                        │── SubnetContract       │
  │                        │   .settleEpoch() ─────►│链上
  │                        │   mint ocDATA          │
  │                        │   记录可领取额度        │
  │                        │                       │
  │── claimReward() ─────────────────────── 链上合约│
  │◄── $ocDATA ──────────────────────────── 链上合约│
```

### 10.4 去中心化路线图

Coordinator 当前为中心化服务（Phase 1），长期目标是逐步去中心化：

| 阶段 | 时间 | 去中心化内容 | 剩余中心化 |
| --- | --- | --- | --- |
| Phase 1 | 上线 | 无（全部中心化） | 全部职责 |
| Phase 2 | 6 个月后 | 评估编排去中心化：多个 Coordinator 节点运行，通过链上随机数确定抽样和分配 | 心跳管理、Golden Task 库、DataSet 审核 |
| Phase 3 | 12 个月后 | Epoch 结算去中心化：权重计算和 settleEpoch() 由多签 Coordinator 集体执行，引入链上 dispute 机制 | Golden Task 库管理 |
| Phase 4 | 18 个月后 | Golden Task 库管理引入 DAO 治理，社区投票决定新增/轮换 | 最小化信任假设 |

关键原则
：

- 资金安全从 Phase 1 开始就由链上合约保证，Coordinator 不处理资金

- 每阶段去中心化前进行充分测试，确保无降级

- 即使在 Phase 1，Coordinator 的所有操作均可通过链上事件和 IPFS 数据审计

---

## 第十一章 Skill 体系

### 11.1 Skill 结构

```
@openclaw/mining-core          ← 公共基础
@openclaw/subnet-hub           ← Hub
@ocdata/miner-skill            ← DATA Mining Miner
@ocdata/validator-skill        ← DATA Mining Validator
```

### 11.2 Miner Skill

```
name:"@ocdata/miner-skill"
version:"1.4.0"
subnet_id:1
role:"miner"

dependencies:
  -"@openclaw/mining-core@>=1.0.0"
  -"@openclaw/browser-tool@>=2.0.0"

triggers:
  -cron:"*/1 * * * *"
    action:"heartbeat"
  -cron:"*/5 * * * *"
    action:"check_and_submit"
  -event:"repeat_crawl_task"
    action:"execute_repeat_crawl"
  -event:"pow_challenge"
    action:"answer_pow_challenge"

permissions:
  -"network:outbound"
  -"filesystem:read_write"
  -"wallet:sign"
  -"ipfs:upload"
```

### 11.3 Validator Skill

```
name:"@ocdata/validator-skill"
version:"1.0.0"
subnet_id:1
role:"validator"

dependencies:
  -"@openclaw/mining-core@>=1.0.0"
  # 不需要 browser-tool（不拉 HTML、不渲染）

triggers:
  -cron:"*/1 * * * *"
    action:"heartbeat"
  -event:"evaluation_task"
    action:"execute_evaluation"

permissions:
  -"network:outbound"
  -"wallet:sign"
```

> v1.6 简化 ：Validator 不需要 browser-tool 和 ipfs:download。Phase A 的真实性校验由 Repeat Crawl Miner 完成，Phase B 的质量评估基于 Coordinator 传入的 M0 的 cleaned_data + structured_data，Validator 本地评估即可。阶段 1 和阶段 2 的 Validator Skill 完全一致，无 breaking change 升级。

---

## 第十二章 数据存储

### 12.1 存储分层

| 位置 | 存储内容 | 费用承担 |
| --- | --- | --- |
| 链上 | DataSet 注册、Epoch 权重、排放记录 | Gas 由操作发起者支付 |
| IPFS | confirmed 的清洗数据、结构化数据 | Subnet Owner 负责 pinning 和存储费用 （从 18% 排放收入中支出） |
| Coordinator | 数据索引（含 pending/confirmed/rejected 状态、dedup_hash）、刷新队列、在线列表、Golden Task 库、信用分 | Subnet Owner 运维 |

### 12.2 IPFS 目录结构

```
ipfs://<root_cid>/
  └── datasets/
      ├── ds_x_posts/
      │   ├── schema.json
      │   ├── epoch_001/
      │   │   ├── miner_0x1234/
      │   │   │   ├── cleaned.jsonl
      │   │   │   └── structured.jsonl
      │   │   └── index.json
      │   └── epoch_002/
      └── ds_amazon/
```

注意：只有 confirmed 的数据才会出现在 IPFS 上。rejected 的数据不存储。同一内容（dedup_hash）的多个历史版本均保留在 IPFS 上。

### 12.3 IPFS Pinning 策略

Subnet Owner 负责 IPFS 数据的持久化：

```
存储策略：
  confirmed 数据 → 立即 pin，长期保留
  历史版本（同一 dedup_hash 的旧 confirmed）→ 保留至少 90 天后可选 unpin

推荐 pinning 服务：Pinata / web3.storage / 自建 IPFS 集群
费用来源：Subnet Owner 18% 排放收入
```

---

## 第十三章 异常处理

### 13.1 Repeat Crawl 超时

```
Step 1 选中的 Miner 未在 15 分钟内提交：
  → 备用 Miner 补选（排除原始提交者和已选 Miner）
  → 如果补选后仍无法获得 M1，该样本跳过评估
  → 该样本不计入 miner_score（不影响 avg_score）

Step 2 选中的 Miner 未在 15 分钟内提交：
  → 备用 Miner 补选
  → 如果无法获得 M2，基于 M0 和 M1 的对比结果裁决：
    → M0 vs M1 不一致且无 M2 → 该样本不可判定，不计入 miner_score
```

### 13.2 Validator 评估超时

```
被选中的 Validator 未在 30 分钟内完成 Phase B 评估：
  → 任务回到待分配队列，从 ready_pool 重新选 Validator
  → 超时 Validator 不扣分，但不计入 eval_count
  → 超时 Validator 重新进入入池等待流程
```

### 13.3 大面积离线

```
Active Miner < 10 → 暂停评估抽样
Active Validator < 3 或 ready_pool 为空 → 评估任务排队，告警 Owner
```

### 13.4 网页不可访问

```
Repeat Crawl 时 URL 返回 404/403/超时：
  → M1 报告 unreachable:
    → 不做 Step 2
    → 该样本跳过评估（原始 Miner 不受影响）

  → M1 和 M2 都报告 unreachable:
    → 样本标记 "url_unavailable"
    → 该样本跳过评估（原始 Miner 不受影响）
```

---

## 第十四章 四层防线总览

### 14.1 架构

```
Layer 1: Phase A 真实性校验（每个样本，1-2 Miner）
  ├── 对比方式：纯文本相似度（≥ 75% 为一致）
  ├── Step 1: 1 Miner 独立爬取 → 一致即通过
  ├── Step 2: 不一致 → 再 1 Miner → 三者裁决 / 动态数据判定
  └── 通过后 M0 的 cleaned_data 被确认为真实可信
  防御：数据伪造、cleaned_data 捏造

Layer 2: Phase B 质量评估（90% 单 Validator，10% 五人 Peer Review）
  ├── 单 Validator: 基于 M0 已验真的 cleaned_data 评估 structured_data → miner_score
  └── Peer Review: 5 个 Validator 独立评分 → 中位数共识 → miner_score
  防御：低质量提取、schema 错误

Layer 3: Golden Task（混入单 Validator 模式，按信用分比例 5-40%）
  └── 检验 Validator 的绝对评估能力
  防御：Validator 偷懒 / 使用烂模型

Layer 4: Peer Review（10% 评估任务，5 个 Validator）
  └── 对齐 Validator 之间的评分标准，检验相对一致性
  防御：Validator 评分标准偏移 / 对真实任务（非 Golden Task）区别对待
```

> Phase A 先做、Phase B 后做 的顺序使两层形成依赖链：Phase A 验证 cleaned_data 真实性 → Phase B 基于已验真的 cleaned_data 评估结构化质量。Phase B 使用 M0 自己的 cleaned_data（而非校验 Miner 的），避免竞争者干扰评分。Golden Task 保证 Validator 的"绝对能力"，Peer Review 保证"相对一致性"，两者综合 accuracy = 1:1 权重。

### 14.2 对照表

|  | Layer 1: Phase A | Layer 2: Phase B | Layer 3: Golden Task | Layer 4: Peer Review |
| --- | --- | --- | --- | --- |
| 验证对象 | Miner cleaned_data 真实性 | Miner structured_data 质量 | Validator 绝对评估能力 | Validator 相对评分一致性 |
| 方法 | 渐进式 Repeat Crawl → 纯文本相似度 | Validator 评估 structured_data | 预标注评估包秘密混入 | 5 人独立评分 → 共识对比 |
| 对比粒度 | 文本级（≥ 75%） | 语义级（字段值与 cleaned_data 一致性） | 评分级（RMSE vs 正确答案） | 评分级（RMSE vs 共识） |
| 成本 | 中（1.15 crawl/样本） | 低（1 或 5 Validator 评估） | 低（复用 Phase B 流程） | 中（10% 任务 × 5 Validator） |
| 门控 | 失败 → miner_score = 0 | miner_score < 60 → 拉低 avg_score | accuracy < 60 → 标记/罚没/驱逐 | 偏离共识 → 拉低 peer_accuracy |

### 14.3 博弈分析

```
攻击者策略 1: 真实 cleaned_data + 低质量 structured_data
  → Phase A 通过（cleaned_data 真实）
  → Phase B 捕获（Validator 发现结构化质量低）
  → 结果：miner_score 低，拉低 avg_score

攻击者策略 2: 伪造 cleaned_data + 匹配的 structured_data
  → Phase A 捕获（M1 独立爬取得到不同内容）
  → 结果：miner_score = 0

攻击者策略 3: 同步篡改 cleaned_data 和 structured_data 中的 dynamic 字段值
  （如两者都写 likes=999999）
  → Phase A 可能通过（整体文本相似度仍高）
  → Phase B 不检测（评估的是自洽性，两者一致则通过）
  → 结果：miner_score 不受影响
  → 但 Miner 无经济动力（篡改不增加收益），仅非经济动机的投毒者会做
  → 通过协议外手段缓解（信用分限流、Owner API 抽检、消费者举报）

攻击者策略 4: 偷懒 Validator 总给中间分
  → Golden Task 捕获（RMSE 公式放大偏差）
  → 结果：accuracy 下降，奖励罚没，最终驱逐

攻击者策略 5: Sybil 攻击（大量注册新 Miner 霸占 dedup_hash）
  → 三层防御: 信用分阶梯（新手 100 条上限）+ AI PoW（100% 触发）+ IP 衰减
  → 每次提交需要通过 AI 挑战 → LLM 成本不可避免
  → 同 IP 50+ Miner → 每个降为 5 条
  → 全部 rejected 后信用分不增长，永远卡在新手 tier
  → 结果：攻击成本远高于收益

攻击者策略 6: Validator 对 Golden Task 认真，对真实任务偷懒
  → 前提: Validator 需要能区分 Golden Task 和真实任务
  → Golden Task 与真实任务格式完全一致，几乎无法区分
  → 即使侥幸区分，Peer Review 会捕获:
    → 10% 真实任务有 5 人共识，偷懒 Validator 偏离共识
    → peer_review_accuracy 下降 → 拉低综合 accuracy
  → 结果：Golden Task 防"没能力"，Peer Review 防"有能力但不认真"

诚实 Miner:
  → Phase A 通过（Step 1 即通过，~85% 概率）
  → Phase B 高分（structured_data 准确提取了 cleaned_data 中的信息）
  → 结果：高 miner_score → 高 avg_score → 高奖励
```

---

## 第十五章 经济模型总览

```
┌───────────────────────────────────────────────────────────┐
│                        资金流                              │
│                                                           │
│  SubnetContract（ocDATA 的 minter）                       │
│    │ 每 Epoch 根据排放表铸造 $ocDATA                       │
│    ▼                                                      │
│  排放分配                                                  │
│    ├── 41% → Miner Pool                                   │
│    │    └── 仅达标 Miner（≥80条 且 ≥60分）                 │
│    │        weight = (avg_score)² × task_count             │
│    ├── 41% → Validator Pool                               │
│    │    ├── 门控: eval_count >= min_eval_count             │
│    │    ├── accuracy < 40 → 罚没，份额重分配               │
│    │    └── v_weight = (accuracy)² × eval_count            │
│    └── 18% → Subnet Owner                                 │
│              └── 含 IPFS pinning 运维成本                  │
│                                                           │
│  评估流程（v1.6）:                                         │
│    Phase A（先做）: 渐进式 Repeat Crawl 验真实性            │
│      → 期望 1.15 次 crawl/样本                            │
│    Phase B（后做）: Validator 用 M0 已验真的 cleaned_data   │
│      评估 structured_data 提取质量                          │
│                                                           │
│  Validator 准入:                                           │
│    RootNet 质押 ≥ min_stake AWP（准入门槛，Subnet 不可动） │
│    容量上限 = ceil(miner_count / 5)                        │
│    竞争替换 + 1 Epoch 保护期 + 立即生效                    │
│                                                           │
│  Validator 信用分（新手 → 优秀）:                          │
│    任务间隔: 10 分钟 → 10 秒                               │
│    Golden Task 比例: 40% → 5%                             │
│    被驱逐后换地址: 从新手 tier 重新开始                     │
│                                                           │
│  Validator accuracy = (golden + peer_review) / 2:          │
│    Golden Task: 对标客观正确答案（绝对能力）                │
│    Peer Review: 10% 任务 × 5 人共识（相对一致性）          │
│    v_weight = (accuracy)² × eval_count                    │
│                                                           │
│  Validator 惩罚（不 Slash AWP）:                           │
│    accuracy < 40 → 罚没本 Epoch 奖励                       │
│    accuracy < 20 → 罚没 + 立即驱逐 + 30天禁入              │
│    连续 5 Epoch accuracy < 60 → 驱逐 + 7天禁入            │
│    连续 3 Epoch eval_count < min → 驱逐（占位不干活）       │
│                                                           │
│  Miner 防 Sybil（三层机制）:                               │
│    Layer 1: 信用分阶梯（新手 100 条，优秀无上限）           │
│    Layer 2: AI PoW（新手 100% 触发，优秀 1%）              │
│    Layer 3: 同 IP 衰减（50+ Miner → 5 条/Epoch）          │
│                                                           │
│  达标 Miner → 数据 confirmed → 入库 DataSet               │
│  未达标 Miner → 数据 rejected → dedup_hash 释放 → 信用分 -15│
│  过期数据 → dedup_hash 重新开放 → Coordinator 指派刷新       │
│                                                           │
│  $ocDATA ↔ $AWP (PancakeSwap V4)                         │
│                                                           │
│  其他收入:                                                 │
│    DataSet 创建费（审核通过后）→ Treasury                   │
│    Validator 罚没奖励 → 重分配给合格 Validator              │
└───────────────────────────────────────────────────────────┘
```
