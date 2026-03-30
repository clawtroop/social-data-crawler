# URL 发现模块合并分析

## 1. 待合并代码概览

### 1.1 MediaUrl/linkedin_url (LinkedIn 图谱发现)

| 文件 | 功能 | 代码量 |
| --- | --- | --- |
| `bfs_expand.py` | BFS 图谱遍历主逻辑 | 283 行 |
| `profile_expand.py` | Profile 页面链接提取 | ~200 行 |
| `company_expand.py` | Company 页面链接提取 | ~250 行 |
| `post_expand.py` | Post 页面链接提取 | ~160 行 |
| `job_expand.py` | Job 页面链接提取 | ~40 行 |
| `normalize.py` | URL 标准化/归一 | ~200 行 |
| `models.py` | 数据模型 (LinkedInEntityType) | ~50 行 |
| `auth/` | Playwright session 管理 | ~400 行 |

**核心能力**：
- BFS/DFS 遍历 Profile → Company → Post → Job 四类实体
- 深度控制、运行时间控制
- 已访问节点去重
- 错误收集与统计

### 1.2 MediaUrl/wikipedia_url (Wikipedia API 发现)

| 文件 | 功能 | 代码量 |
| --- | --- | --- |
| `mw_client.py` | MediaWiki API 客户端 | 169 行 |
| `wiki_url.py` | URL 工具 | ~20 行 |
| `user_agent.py` | UA 管理 | ~50 行 |

**核心能力**：
- `query_random_titles()` - 随机页面发现
- `query_all_links()` - 页面链出链接（支持分页）
- `query_page_exists()` - 页面存在检查

### 1.3 Amazon/scripts (Amazon BFS 发现)

| 文件 | 功能 | 代码量 |
| --- | --- | --- |
| `amazon_url_discovery.py` | BFS 产品 URL 发现 | ~500 行 |
| `amazon_review_graph_crawler.py` | 评论图谱爬取 | ~900 行 |

**核心能力**：
- 从关键词搜索发现种子 ASIN
- BFS 递归扩展（从产品页面提取关联 ASIN）
- 断点续爬（checkpoint）
- ASIN 提取（URL、data-asin 属性）

---

## 2. 当前项目结构

```text
crawler/
├── discovery/
│   ├── __init__.py
│   └── url_builder.py          # 模板拼接（已有）
├── platforms/
│   ├── linkedin.py             # LinkedIn 适配器
│   ├── wikipedia.py            # Wikipedia 适配器
│   ├── amazon.py               # Amazon 适配器
│   └── ...
├── fetch/
│   ├── session_store.py        # Session 管理（可复用）
│   ├── playwright_backend.py   # 浏览器抓取（可复用）
│   └── ...
```

---

## 3. 合并策略

### 3.1 目标目录结构

```text
crawler/
├── discovery/
│   ├── __init__.py
│   ├── url_builder.py          # 已有：模板拼接
│   ├── base.py                 # 新增：发现器基类
│   ├── linkedin/               # 新增：LinkedIn 图谱发现
│   │   ├── __init__.py
│   │   ├── bfs_expand.py
│   │   ├── entity_expand.py    # 合并 profile/company/post/job expand
│   │   ├── normalize.py
│   │   └── models.py
│   ├── wikipedia/              # 新增：Wikipedia API 发现
│   │   ├── __init__.py
│   │   ├── mw_client.py
│   │   └── link_discovery.py
│   └── amazon/                 # 新增：Amazon BFS 发现
│       ├── __init__.py
│       ├── asin_utils.py
│       └── bfs_discovery.py
```

### 3.2 接口统一

建议定义统一的发现器接口：

```python
# crawler/discovery/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

@dataclass
class DiscoveryResult:
    urls: list[str]           # 发现的 URL 列表
    stats: dict               # 统计信息
    errors: list[str]         # 错误列表

class BaseDiscovery(ABC):
    @abstractmethod
    def discover(
        self,
        seed_urls: list[str],
        fetch_fn: Callable[[str], str],
        *,
        max_depth: int | None = None,
        max_urls: int | None = None,
        max_runtime_seconds: float | None = None,
    ) -> DiscoveryResult:
        """从种子 URL 发现更多 URL"""
        pass
```

### 3.3 复用现有基础设施

| urlDiscover 组件 | 复用 social-data-crawler 组件 |
| --- | --- |
| `auth/playwright_session.py` | `fetch/session_store.py` + `fetch/playwright_backend.py` |
| `auth/fetch.py` | `fetch/unified.py` |
| HTTP 请求 | `fetch/http_backend.py` |

---

## 4. 合并步骤

### Phase 1: 基础框架 (Day 1)

1. **创建 `discovery/base.py`**
   - 定义 `BaseDiscovery` 抽象类
   - 定义 `DiscoveryResult` 数据类

2. **创建目录结构**
   ```bash
   mkdir -p crawler/discovery/{linkedin,wikipedia,amazon}
   touch crawler/discovery/{linkedin,wikipedia,amazon}/__init__.py
   ```

### Phase 2: LinkedIn 发现 (Day 2)

1. **复制核心文件**
   ```bash
   cp urlDiscover/MediaUrl/linkedin_url/bfs_expand.py crawler/discovery/linkedin/
   cp urlDiscover/MediaUrl/linkedin_url/normalize.py crawler/discovery/linkedin/
   cp urlDiscover/MediaUrl/linkedin_url/models.py crawler/discovery/linkedin/
   ```

2. **重构导入**
   - 将 `from linkedin_url.xxx` 改为 `from crawler.discovery.linkedin.xxx`
   - 将 `fetch_html` 参数改为使用 `fetch/unified.py`

3. **合并扩展器**
   - 将 `profile_expand.py`, `company_expand.py`, `post_expand.py`, `job_expand.py` 合并为 `entity_expand.py`

4. **适配接口**
   - 实现 `LinkedInDiscovery(BaseDiscovery)`

### Phase 3: Wikipedia 发现 (Day 3)

1. **复制核心文件**
   ```bash
   cp urlDiscover/MediaUrl/wikipedia_url/mw_client.py crawler/discovery/wikipedia/
   ```

2. **创建 `link_discovery.py`**
   - 基于 `scripts/wikipedia_contents_dfs.py` 的 DFS 逻辑
   - 实现 `WikipediaDiscovery(BaseDiscovery)`

### Phase 4: Amazon 发现 (Day 4)

1. **提取核心逻辑**
   ```bash
   # 从 amazon_url_discovery.py 提取
   cp urlDiscover/Amazon/scripts/amazon_url_discovery.py crawler/discovery/amazon/bfs_discovery.py
   ```

2. **重构**
   - 提取 `AmazonURLUtils` 到 `asin_utils.py`
   - 移除独立的 HTTP 请求代码，改用 `fetch/http_backend.py`
   - 实现 `AmazonDiscovery(BaseDiscovery)`

### Phase 5: 集成测试 (Day 5)

1. **编写单元测试**
   ```bash
   touch crawler/tests/test_linkedin_discovery.py
   touch crawler/tests/test_wikipedia_discovery.py
   touch crawler/tests/test_amazon_discovery.py
   ```

2. **集成到 pipeline**
   - 在 `core/pipeline.py` 中添加发现阶段（可选）

---

## 5. 需要解决的问题

### 5.1 认证/Session

| 平台 | urlDiscover 方式 | social-data-crawler 方式 | 合并方案 |
| --- | --- | --- | --- |
| LinkedIn | 独立的 `auth/` 模块 | `fetch/session_store.py` | 复用 session_store |
| Wikipedia | User-Agent 文件 | 无 | 保留或移到配置 |
| Amazon | 无（公开页面） | 无 | 不变 |

### 5.2 HTML 抓取

urlDiscover 的 `fetch_html` 函数需要统一为：

```python
async def fetch_html(url: str) -> str:
    from crawler.fetch.unified import fetch
    result = await fetch(url, backend="playwright")
    return result.get("html", "")
```

### 5.3 去重与队列

urlDiscover 使用内存中的 `set()` 去重。如果需要跨会话持久化：
- 方案 A：使用 `output/.sessions/` 持久化已访问 URL
- 方案 B：通过后端 API `/url-occupancies/check` 去重（推荐）

---

## 6. 工作量估计

| 阶段 | 工作内容 | 预估时间 |
| --- | --- | --- |
| Phase 1 | 基础框架 | 2h |
| Phase 2 | LinkedIn 发现 | 4h |
| Phase 3 | Wikipedia 发现 | 2h |
| Phase 4 | Amazon 发现 | 3h |
| Phase 5 | 集成测试 | 3h |
| **合计** | | **14h (~2 天)** |

---

## 7. 风险与注意事项

1. **LinkedIn 限流** - urlDiscover 的 BFS 可能触发 429，需要复用 `rate_limits.json`
2. **代码风格** - urlDiscover 使用同步代码，social-data-crawler 部分使用 async
3. **依赖冲突** - urlDiscover 使用 `requests`，social-data-crawler 使用 `httpx`
4. **测试数据** - urlDiscover 的 `output/` 目录包含测试数据，不应合并

---

## 8. 建议的合并顺序

1. **先合并 Wikipedia** - 最简单，只是 API 调用
2. **再合并 Amazon** - 中等复杂度，无认证依赖
3. **最后合并 LinkedIn** - 最复杂，依赖 session 管理
