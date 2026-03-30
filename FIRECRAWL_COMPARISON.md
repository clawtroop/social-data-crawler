# Firecrawl vs Social-Data-Crawler 对比分析报告

> 生成日期：2026-03-29
> 研究团队：firecrawl-research (3 agents)

## 一、架构对比

| 维度 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| **执行模式** | 托管服务 + 自托管（微服务） | 本地 agent 原生 |
| **技术栈** | TypeScript/Node.js (Express.js) | Python/asyncio |
| **队列系统** | BullMQ + RabbitMQ 双队列 | 无（单进程顺序） |
| **存储** | Redis + PostgreSQL + GCS 三层 | JSONL 文件输出 |
| **扩展性** | 水平扩展（分布式 worker） | 单机限制 |
| **代码规模** | ~50,000+ LOC | ~8,500 LOC |

## 二、数据采集对比

### 2.1 后端引擎

| 引擎 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| **顶级** | Fire-Engine（云端专有） | API 优先（平台原生） |
| **次级** | Playwright (headless Chrome) | HTTP 直连 |
| **三级** | 基础 Fetch | Playwright |
| **四级** | - | Camoufox（反指纹） |

**分析**：
- Firecrawl 的 Fire-Engine 是云端专有的反爬利器，自托管版不可用
- Social-crawler 的 camoufox 提供更好的反指纹能力（自托管场景）
- Social-crawler 的 API 优先策略避免了大部分反爬问题

### 2.2 并发控制

**Firecrawl 多层并发：**
```
系统级：MAX_CPU=0.8, MAX_RAM=0.8
Worker级：NUM_WORKERS_PER_QUEUE=8
任务级：MAX_CONCURRENT_JOBS=5
爬取级：CRAWL_CONCURRENT_REQUESTS=10
团队级：ACUC 订阅等级限制
```

**Social-crawler 当前：**
```
仅 BrowserPool 层面控制（浏览器实例数）
```

### 2.3 分布式能力

**Firecrawl 核心设计：**
- Crawl 分解为 N 个独立 Scrape 任务
- 每个 Scrape 通过 `crawlId` 关联
- 任务在队列中独立调度
- 可跨多台机器并行执行

**Social-crawler：**
- 单进程顺序执行
- 无分布式支持

### 2.4 URL 发现

| 能力 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| Sitemap 解析 | ✅ 三种模式 | ❌ |
| 递归链接发现 | ✅ BFS + 深度控制 | 平台适配器定义 |
| /map 端点 | ✅ 专用发现 API | ❌ |
| robots.txt | ✅ 遵守 | 部分支持 |

### 2.5 反爬处理

| 能力 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| 代理池 | 云端内置/自托管手动 | 需手动配置 |
| 浏览器指纹 | Fire-Engine（云端） | Camoufox |
| User-Agent | FirecrawlAgent | 可配置 |
| Cookie 持久化 | ✅ | ✅ 更强（跨运行） |

## 三、数据清洗对比

### 3.1 内容提取

| 能力 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| 主内容检测 | 多引擎（Readability 等） | 选择器 + 密度启发式 |
| 噪音移除 | 自动 | CSS 选择器配置 |
| 表格处理 | ✅ | 基础支持 |
| 代码块 | ✅ | ✅ |

### 3.2 输出格式

**Firecrawl 支持：**
- Markdown（默认）
- HTML / Raw HTML
- JSON（结构化提取）
- Screenshot
- Summary
- Links / Images / Audio

**Social-crawler：**
- JSONL（主输出）
- artifacts/（调试产物）

### 3.3 LLM 优化

| 能力 | Firecrawl | Social-Data-Crawler |
|------|-----------|---------------------|
| 语义分块 | 无显式 | ✅ 512 token, 50 重叠 |
| Schema 提取 | ✅ 自然语言描述 | 固定规则 |
| 元数据 | section_path 等 | ✅ heading_level, offset |

## 四、可借鉴的设计

### 🔴 高优先级

#### 1. 任务分解 + 队列架构

**Firecrawl 做法：**
```
Client Request → API Controller → 创建 Job → 入队 (BullMQ/NuQ)
  → Worker 取任务 → 执行 scrape
  → 发现新 URL → 生成新 scrape job 入队
  → 结果写入存储 → 通知完成
```

**借鉴实现：**
```python
# crawler/queue/task_queue.py
from celery import Celery

app = Celery('crawler', broker='redis://localhost:6379/0')

@app.task
def scrape_task(url: str, crawl_id: str, options: dict):
    """独立的 scrape 任务，可分布式执行"""
    result = fetch_engine.fetch(url, options)

    # 发现新 URL 时生成新任务
    for link in result.discovered_links:
        scrape_task.delay(link, crawl_id, options)

    return result
```

#### 2. 资源感知调度

**Firecrawl 做法：**
- Worker 不是简单的最大并发
- 根据实时 CPU/RAM 决定是否接受新任务
- 超过阈值自动暂停

**借鉴实现：**
```python
# crawler/fetch/resource_monitor.py
import psutil

class ResourceMonitor:
    def __init__(self, max_cpu=0.8, max_ram=0.8):
        self.max_cpu = max_cpu
        self.max_ram = max_ram

    def can_accept_task(self) -> bool:
        cpu = psutil.cpu_percent() / 100
        ram = psutil.virtual_memory().percent / 100
        return cpu < self.max_cpu and ram < self.max_ram
```

#### 3. 多层并发限制

**借鉴实现：**
```python
# crawler/fetch/rate_limiter.py
from asyncio import Semaphore
from collections import defaultdict

class MultiLayerRateLimiter:
    def __init__(self, config):
        self.system_limit = config.get('max_concurrent_jobs', 10)
        self.platform_limits = defaultdict(lambda: Semaphore(5))
        self.global_semaphore = Semaphore(self.system_limit)

    async def acquire(self, platform: str):
        await self.global_semaphore.acquire()
        await self.platform_limits[platform].acquire()

    def release(self, platform: str):
        self.platform_limits[platform].release()
        self.global_semaphore.release()
```

### 🟡 中优先级

#### 4. Sitemap 自动发现

**借鉴实现：**
```python
# crawler/discovery/sitemap.py
import httpx
from xml.etree import ElementTree

class SitemapDiscoverer:
    async def discover(self, base_url: str, mode: str = "include") -> list[str]:
        """
        mode: "include" (sitemap + links), "only" (sitemap only), "skip"
        """
        if mode == "skip":
            return []

        sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
        ]

        urls = []
        for sitemap_url in sitemap_urls:
            try:
                resp = await httpx.get(sitemap_url)
                urls.extend(self._parse_sitemap(resp.text))
            except:
                continue

        return urls
```

#### 5. AI 驱动的结构化提取

**Firecrawl 做法：**
- 用户用自然语言描述想要的字段
- LLM 按 schema 输出 JSON

**借鉴实现：**
```python
# crawler/enrich/schema_extractor.py
class SchemaExtractor:
    async def extract(self, content: str, schema_description: str) -> dict:
        """
        schema_description: "提取文章的标题、作者、发布日期、主要观点"
        """
        prompt = f"""
        从以下内容中提取结构化数据。

        需要提取的字段：{schema_description}

        内容：
        {content[:4000]}

        以 JSON 格式输出。
        """
        return await self.llm.generate_json(prompt)
```

#### 6. 输出格式扩展

**借鉴实现：**
```python
# crawler/output/formatter.py
from abc import ABC, abstractmethod

class OutputFormatter(ABC):
    @abstractmethod
    def format(self, document: ExtractedDocument) -> str:
        pass

class MarkdownFormatter(OutputFormatter):
    def format(self, doc):
        return markdownify(doc.html_content)

class JSONFormatter(OutputFormatter):
    def format(self, doc):
        return doc.model_dump_json()

class ScreenshotFormatter(OutputFormatter):
    def format(self, doc):
        return doc.screenshot_path
```

### 🟢 低优先级

#### 7. 变更追踪
```python
# crawler/tracking/change_tracker.py
class ChangeTracker:
    def __init__(self, storage_path: str):
        self.storage = Path(storage_path)

    def has_changed(self, url: str, content_hash: str) -> bool:
        prev_hash = self._get_previous_hash(url)
        return prev_hash != content_hash

    def record(self, url: str, content_hash: str):
        self._save_hash(url, content_hash)
```

#### 8. /map 端点
```python
# 专用 URL 发现 API，预览可爬取范围
@router.get("/map")
async def map_urls(base_url: str, max_depth: int = 2):
    return await sitemap_discoverer.discover_all(base_url, max_depth)
```

## 五、Social-Data-Crawler 的优势（保持）

| 优势 | 说明 | 保持理由 |
|------|------|---------|
| **平台适配器** | 5 个预集成平台 | 开箱即用，无需配置 |
| **API 优先策略** | Wikipedia MediaWiki, arXiv Atom, Voyager | 更稳定、更快、成本更低 |
| **两层丰富策略** | 提取优先 + LLM 按需 | 成本可控 |
| **会话持久化** | Playwright storage_state | LinkedIn 等复杂认证 |
| **Agent 原生** | JSONL + artifacts | 易于 agent 消费 |
| **Camoufox 支持** | 反指纹浏览器 | 自托管反爬更强 |

## 六、实施路线图

### Phase 1：基础设施（1-2周）
```
├── 引入任务队列
│   ├── 选择：celery（成熟）或 dramatiq（轻量）
│   ├── 配置 Redis 作为 broker
│   └── 实现 scrape_task 异步任务
│
├── 添加资源监控
│   ├── ResourceMonitor 类
│   ├── psutil CPU/RAM 监控
│   └── 门限配置化
│
└── 多层并发限制
    ├── MultiLayerRateLimiter
    ├── 系统级 + 平台级
    └── 配置文件支持
```

### Phase 2：采集增强（2-3周）
```
├── Sitemap 自动发现
│   ├── SitemapDiscoverer 组件
│   ├── 三种模式支持
│   └── 与平台适配器集成
│
├── 递归链接发现（可选）
│   ├── BFS 遍历器
│   ├── 深度控制
│   └── 路径过滤
│
└── 分布式 worker 支持
    ├── 多 worker 进程
    ├── crawlId 关联
    └── 结果聚合
```

### Phase 3：清洗增强（2-3周）
```
├── AI schema 提取
│   ├── SchemaExtractor 组件
│   ├── 自然语言 schema 描述
│   └── LLM JSON 输出
│
├── 多格式输出
│   ├── OutputFormatter 接口
│   ├── Markdown / HTML / JSON
│   └── Screenshot 支持
│
└── 变更追踪（可选）
    ├── ChangeTracker 组件
    └── 内容哈希存储
```

## 七、总结

### Firecrawl 核心优势
1. **分布式架构** - crawl 分解为独立 scrape，水平扩展
2. **双队列系统** - BullMQ + RabbitMQ 高吞吐
3. **资源感知** - CPU/RAM 门限控制
4. **AI 原生** - 自然语言 schema 提取

### Social-Data-Crawler 核心优势
1. **平台专注** - 5 个预集成平台
2. **API 优先** - 稳定、快速、低成本
3. **两层丰富** - 成本可控的 LLM 策略
4. **Agent 原生** - JSONL 输出易于集成

### 借鉴优先级
```
高优先级：任务队列 + 资源监控 + 多层并发
中优先级：Sitemap 发现 + AI 提取 + 多格式输出
低优先级：变更追踪 + /map 端点
```

---

**研究来源：**
- [Firecrawl GitHub](https://github.com/mendableai/firecrawl)
- [Firecrawl 官方文档](https://docs.firecrawl.dev/)
- [Firecrawl 扩展博客](https://www.firecrawl.dev/blog/an-adventure-in-scaling)
- social-data-crawler 源码分析
