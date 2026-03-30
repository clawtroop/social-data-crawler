# URL 发现机制重构设计
> 日期：2026-03-30  
> 状态：已批准
## 概述
用**统一发现框架**取代当前零散的发现实现，围绕**两种明确能力**构建：
1. **`Map`**：快速 URL 发现
2. **`Crawl`**：递归抓取 + 扩展
框架需同时支持：
- 面向平台的发现：`linkedin`、`amazon`、`wikipedia` 及后续平台
- **通用发现**：任意公开网页
本设计遵循仓库调研结论「**一套 skill + 平台适配器**」，并借鉴 Firecrawl 在「快速 URL 映射」与「递归爬取」之间的划分。
## 目标
- 在同一框架内支持多种发现模式：
  - 模板构造
  - API 驱动发现
  - 图遍历
  - 基于搜索的发现
  - 基于内容的发现
- 通过 `generic` 适配器支持任意 URL
- 队列、去重、检查点、重试逻辑保持**与平台无关**
- 会话 / Cookie 存储与发现状态**分离**
- 发现输出为**一等公民的结构化记录**，而非原始 URL 列表
- 允许日后替换当前临时爬虫流水线，**无需兼容层 hack**
## 非目标
- 保留当前 `crawler/platforms/*` 的实现形态
- 将 `use_legacy_pipeline` 作为长期架构锚点
- 在第一版解决所有平台级反爬问题
- 在本阶段设计分布式多节点调度器
## 架构
### 1. 核心分层
新运行时分为四层：
1. **`discovery core`（发现核心）**
   - 队列调度
   - 去重
   - 检查点
   - 重试 / 退避
   - 遍历策略
2. **`discovery adapters`（发现适配器）**
   - 平台或通用 URL 语义
   - 候选生成
   - 规范化
   - 资源分类
3. **`fetch/extract runtime`（抓取 / 抽取运行时）**
   - 后端路由
   - 鉴权 / 会话使用
   - 页面 / API 抓取
   - 抽取
4. **`output/state`（输出 / 状态）**
   - 记录 / 错误 / 摘要
   - 边界、已访问、检查点持久化
### 2. 模式划分
#### `Map`
用途：
- 快速发现候选 URL
- 默认避免重度内容持久化
- 适用于任意站点及搜索 / 结果页
典型输入：
- 种子 URL
- 带标识符的数据集记录
- 搜索查询种子
典型输出：
- 规范化后的候选
- 候选得分
- 发现溯源信息
#### `Crawl`
用途：
- 抓取候选
- 抽取内容或结构化载荷
- 可选地扩展为子候选
- 持久化最终爬取记录
典型输出：
- 已抓取载荷
- 已抽取内容
- 规范化记录
- 衍生出的候选
### 3. 适配器划分
存在两类适配器家族：
#### `GenericAdapter`（通用适配器）
在无平台专用适配器时，用于任意公开网页。
职责：
- 接受任意公开 URL
- 保守地规范化
- 从 sitemap 与 HTML 中发现链接
- 仅做粗粒度分类
- 赋予较低置信度分数
- 遵守严格的遍历边界
#### 平台适配器
用于 `linkedin`、`amazon`、`wikipedia` 及后续支持的平台。
职责：
- 确定性身份抽取
- 平台原生规范 URL
- 资源类型分类
- 在合适处使用 API 驱动发现
- 鉴权 / 会话需求
- 平台特定的评分与扩展规则
## 建议目录结构
```text
crawler/
├── discovery/
│   ├── __init__.py
│   ├── contracts.py
│   ├── map_engine.py
│   ├── crawl_engine.py
│   ├── scheduler.py
│   ├── runner.py
│   ├── url_builder.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── generic.py
│   │   ├── wikipedia.py
│   │   ├── amazon.py
│   │   └── linkedin.py
│   ├── state/
│   │   ├── job.py
│   │   ├── frontier.py
│   │   ├── visited.py
│   │   ├── checkpoint.py
│   │   ├── occupancy.py
│   │   └── edges.py
│   └── store/
│       ├── frontier_store.py
│       ├── visited_store.py
│       ├── checkpoint_store.py
│       └── occupancy_store.py
├── fetch/
├── extract/
├── enrich/
└── core/
    └── pipeline.py
```
## 核心契约
### DiscoveryCandidate（发现候选）
```python
@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    platform: str
    resource_type: str
    canonical_url: str | None
    seed_url: str | None
    fields: dict[str, str]
    discovery_mode: str
    score: float
    score_breakdown: dict[str, float]
    hop_depth: int
    parent_url: str | None
    metadata: dict[str, Any]
```
规则：
- `canonical_url` 在通用发现早期阶段可能缺失，但**必须在抓取前补全**
- `score` 面向队列排序
- `score_breakdown` **必填**，便于调试
- `parent_url` 与 `discovery_mode` 保留溯源
### DiscoveryRecord（发现记录）
`DiscoveryCandidate` 面向队列。写入下游阶段的最终发现输出应规范为稳定记录：
```python
@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    platform: str
    resource_type: str
    discovery_mode: str
    canonical_url: str
    identity: dict[str, str]
    source_seed: dict[str, Any] | None
    discovered_from: dict[str, Any] | None
    metadata: dict[str, Any]
```
### MapResult（Map 结果）
```python
@dataclass(frozen=True, slots=True)
class MapResult:
    accepted: list[DiscoveryCandidate]
    rejected: list[DiscoveryCandidate]
    exhausted: bool
    next_seeds: list[str]
```
### CrawlResult（Crawl 结果）
```python
@dataclass(frozen=True, slots=True)
class CrawlResult:
    candidate: DiscoveryCandidate
    fetched: dict[str, Any]
    extracted: dict[str, Any]
    normalized: dict[str, Any]
    spawned_candidates: list[DiscoveryCandidate]
```
## 适配器契约
```python
class BaseDiscoveryAdapter(ABC):
    platform: str
    supported_resource_types: tuple[str, ...]
    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        ...
    @abstractmethod
    def build_seed_records(self, input_record: dict[str, Any]) -> list[DiscoveryRecord]:
        ...
    @abstractmethod
    async def map(self, seed: DiscoveryRecord, context: dict[str, Any]) -> MapResult:
        ...
    @abstractmethod
    async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, Any]) -> CrawlResult:
        ...
    @abstractmethod
    def normalize_candidate(self, candidate: DiscoveryCandidate) -> DiscoveryCandidate:
        ...
    @abstractmethod
    def score_candidate(self, candidate: DiscoveryCandidate) -> float:
        ...
```
语义说明：
- `build_seed_records()`：处理模板构造与数据集字段映射
- `map()`：发现与候选生成
- `crawl()`：抓取 + 抽取 + 规范化 + 子节点扩展
- `normalize_candidate()` 与 `score_candidate()`：使调度器保持通用
## 发现模式（discovery_mode）
每个候选必须携带 `discovery_mode`。初始集合：
- `direct_input`
- `canonicalized_input`
- `template_construction`
- `api_lookup`
- `search_results`
- `graph_traversal`
- `page_links`
- `artifact_link`
- `pagination`
- `sitemap`
这些模式是**描述性**的，不是执行状态；用于说明候选是如何被发现的。
## 通用发现
`generic` 适配器作为任意网页的兜底。
### 通用 Map 行为
默认行为：
- 仅同域
- 默认不启用子域
- 默认不启用外链
- 默认启用 sitemap
- 浅层发现
- 默认启用查询参数规范化
来源：
- sitemap URL
- HTML 锚点链接
- canonical 标签
- 分页链接
- 文章 / 文档 / 博客容器内明显的内容链接
### 通用 Crawl 行为
默认行为：
- BFS 遍历
- 低并发
- 保守重试
- 基于路径的过滤
- 低置信度的子候选发射
通用适配器不得假装超出粗粒度类别之外的语义实体类型，例如：
- `page`
- `article`
- `listing`
- `document`
## 平台特定行为
### Wikipedia
- `build_seed_records()` 使用标题规范化与模板构造
- `map()` 可使用 MediaWiki API 的页面链接、分类链接、随机标题发现、存在性检查
- `crawl()` 仍以 API 为优先获取文章载荷，可选页面链接扩展
- 默认遍历应保持高置信度、范围窄
### Amazon
- `build_seed_records()` 处理 `asin`、`seller_id`、`query`
- `map()` 将搜索 / 分类 / 列表页视为发现面
- `crawl()` 将商品 / 卖家页视为持久实体记录
- 从 URL 与页面属性中抽取 ASIN 属于适配器职责
### LinkedIn
- `build_seed_records()` 处理确定性的档案 / 公司 / 动态 / 职位 / 搜索等输入
- `map()` 将搜索结果抽取与结果页扩展提升为一等候选
- `crawl()` 处理后端感知的、可鉴权的抓取与资源规范化
- 鉴权 / 会话处理仍在发现状态之外，位于 fetch / 会话运行时
## 状态模型
### JobSpec
不可变作业配置：
```python
@dataclass(frozen=True, slots=True)
class JobSpec:
    job_id: str
    mode: Literal["map", "crawl"]
    adapter: str
    seed_set: list[str]
    limits: dict[str, Any]
    session_ref: str | None
    created_at: str
```
### FrontierEntry
队列行：
```python
@dataclass(slots=True)
class FrontierEntry:
    frontier_id: str
    job_id: str
    url_key: str
    canonical_url: str | None
    adapter: str
    entity_type: str | None
    depth: int
    priority: float
    discovered_from: dict[str, Any] | None
    discovery_reason: str
    status: Literal["queued", "leased", "retry_wait", "done", "dead"]
    attempt: int
    not_before: str | None
    last_error: dict[str, Any] | None
```
### VisitRecord
去重行：
```python
@dataclass(slots=True)
class VisitRecord:
    url_key: str
    canonical_url: str
    scope_key: str
    first_seen_at: str
    last_seen_at: str
    best_depth: int
    map_state: str | None
    crawl_state: str | None
    fetch_fingerprint: str | None
    final_url: str | None
    http_status: int | None
    adapter_state: dict[str, Any]
```
重要规则：
- `map_state` 与 `crawl_state` **必须分离**
- URL 成功完成映射**不自动**视为已爬取
### Checkpoint
检查点仅表示**可恢复的进度**，不是真相来源。
### OccupancyLease
租约状态与已访问状态、会话**分离**，仅用于防止重复活跃任务，并在 worker 故障后恢复。
### DiscoveryEdge
可选的溯源边：
- 父 URL
- 子 URL
- 原因
- 观测时间戳
便于图调试与后续基于溯源的排序。
## 作业生命周期
状态迁移：
1. `created`
2. 种子记录规范化为 `queued` 边界行
3. `queued -> leased`
4. `leased -> discovering`
5. `map`：`discovering -> done`
6. `crawl`：`discovering -> fetched -> done`
7. 可重试失败进入 `retry_wait`
8. 终失败进入 `dead`
9. 过期租约将工作退回 `queued`
检查点在批次后执行，**不能**替代边界 / 已访问的真相。
## 与会话状态的分离
以下内容**不得**放入 `.sessions`：
- 边界队列行
- 已访问 / 去重行
- 检查点快照
- 租约
- 重试计数
- 溯源边
- 抓取指纹
发现作业配置中仅可出现 `session_ref`。实际 Cookie / storage-state 文件仍在 fetch 会话存储中。
## CLI 与流水线形态
### 新命令
增加面向发现的命令：
- `discover-map`
- `discover-crawl`
保留更高层：
- `crawl`
- `run`
- `enrich`
语义：
- `discover-map`：产出发现候选或记录，**不做**重度抽取
- `discover-crawl`：完整递归发现 + 抓取 / 抽取
- `crawl`：对显式输入抓取，**最少**发现
- `run`：端到端爬取 + 丰富化
### 建议配置扩展
在 `CrawlerConfig` 中增加：
```python
discovery_mode: Literal["direct", "map", "crawl"] = "direct"
seed_url: str | None = None
max_depth: int = 2
max_pages: int = 100
max_candidates: int = 500
sitemap_mode: Literal["include", "only", "skip"] = "include"
include_paths: tuple[str, ...] = ()
exclude_paths: tuple[str, ...] = ()
include_subdomains: bool = False
allow_external_links: bool = False
ignore_query_parameters: bool = True
max_concurrency: int = 4
delay_seconds: float = 0.0
```
### 流水线
目标形态：
```text
输入记录
-> 构建种子
-> map（可选）
-> crawl（可选）
-> fetch
-> extract
-> enrich
-> write
```
## 评分
评分为队列排序与调试所必需。每个候选存储：
- 最终 `score`
- `score_breakdown`
典型得分分量：
- URL 模式置信度
- 资源类型置信度
- 域名信任度
- 锚文本相关性
- 发现来源质量
- 深度惩罚
- 重复惩罚
## 迁移策略
### 阶段 1
- 引入新的发现契约与状态模型
- 增加 `generic` 适配器（保守的 map / crawl 行为）
- 保持当前 fetch / 抽取运行时可复用
### 阶段 2
- 将 `wikipedia`、`amazon`、`linkedin` 的发现逻辑迁入新发现适配器
- 将当前 LinkedIn 搜索结果抽取提升进 `map()`
- 将模板 URL 逻辑迁入 `build_seed_records()`
### 阶段 3
- 增加新 CLI 命令与新流水线入口
- 在发现专用存储下持久化边界 / 已访问 / 检查点
- 不再将当前 `crawler/platforms/*` 模块视为主要抽象
### 阶段 4
- 在通用 + 平台适配器覆盖所需场景后，移除临时兼容路径
## 测试策略
1. URL 规范化与 `url_key` 生成的单元测试
2. 通用 sitemap / 链接发现的单元测试
3. 适配器候选评分的单元测试
4. 边界 / 租约恢复的单元测试
5. 集成测试：
   - 通用 `discover-map`
   - 通用 `discover-crawl`
   - wikipedia 适配器
   - amazon 适配器
   - linkedin 适配器（模拟可鉴权抓取）
6. 使用持久化检查点的恢复 / 重启测试
## 风险
1. 若 `url_key` 规范化偏弱，跨适配器的 URL 身份漂移会破坏去重
2. 租约恢复缺陷可能导致重复抓取或边界项卡住
3. 将 `map` 与 `crawl` 混为单一「已访问」标记会导致错误去重与遗漏工作
## 本设计已拍板的开放问题
- 采用**一套**发现框架，而非每平台一套 skill
- 通过 `generic` 适配器支持任意网页
- **`Map` 与 `Crawl` 分离**
- 会话保持在发现状态之外
- 将搜索 / 列表页视为发现面，**不必**总是最终记录
- 语义逻辑归适配器，调度 / 状态逻辑归核心
