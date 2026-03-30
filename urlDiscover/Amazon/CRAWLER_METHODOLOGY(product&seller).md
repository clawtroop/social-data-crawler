# Amazon 爬虫方法论文档

**版本**: v3.0（以代码为准）  
**更新时间**: 2026-03-29  
**规范来源**: `amazon_unified_crawler.py`（`UnifiedAmazonCrawler`、`URLNormalizer` 及同文件内提取函数）

历史版本中的伪代码、优先级与输出文件名若与本文不一致，**以本文与仓库内上述脚本为准**。

---

## 目录

1. [概述](#1-概述)
2. [URL 类型与规范化（实现）](#2-url-类型与规范化实现)
3. [统一图遍历（当前实现）](#3-统一图遍历当前实现)
4. [数据提取（与代码一致）](#4-数据提取与代码一致)
5. [观察到的现象（经验记录）](#5-观察到的现象经验记录)
6. [配置与输出](#6-配置与输出)
7. [脚本清单](#7-脚本清单)

---

## 1. 概述

### 1.1 项目目标

从 Amazon 网站爬取两类数据：

- **Products Dataset (4.1)**: 产品详情数据  
- **Sellers Dataset (4.3)**: 卖家信息数据（当前主流程侧重 **发现 seller_id + 验证卖家页可访问性**）

### 1.2 当前主实现：统一队列图遍历

主脚本 `amazon_unified_crawler.py` 使用 **单一优先级队列**（`heapq`），从起始 URL 出发不断弹出 URL、抓取、再入队新发现的规范化 URL。

- **Product** 是主要**发散节点**：新产品链接、新卖家、`#aod-ingress-link` 打开的 Other Sellers、由品牌/面包屑生成的搜索 URL。  
- **Seller** 页当前策略：**仅验证**（可访问性 + 基础字段），**不再从卖家列表页继续爬产品或卖家**（与早期「卖家图深度遍历」实验脚本不同）。  
- **Store / Search / Category** 等列表类 URL 走 `_process_listing`：**只从 HTML 中提取产品 URL 入队**，不调用 `extract_other_urls`（该函数在文件中存在但**未接入**主循环）。

### 1.3 图示（逻辑关系）

```
                    ┌─────────────┐
  入队 (高优先级)   │  Seller URL │  出队后：验证
                    └─────────────┘
                           ▲
                           │ merchant / Other Sellers
                    ┌─────────────┐
  核心发散节点      │   Product   │──► 更多 Product、Search URL
                    └─────────────┘
                           ▲
                    ┌─────────────┐
                    │ Store/Search│  仅提取页内 Product 链接
                    │ /Category   │
                    └─────────────┘
```

---

## 2. URL 类型与规范化（实现）

`URLNormalizer.normalize(url) -> (normalized: str | None, type: str)`。

### 2.1 类型常量

| 常量 | 含义 |
|------|------|
| `TYPE_PRODUCT` | 产品详情页 |
| `TYPE_SELLER` | 卖家 storefront 列表（规范为 `s?me=`） |
| `TYPE_STORE` | 品牌店铺页 `/stores/.../page/{uuid}` |
| `TYPE_CATEGORY` | `b?node=` |
| `TYPE_SEARCH` | `s?k=`（**仅当查询串含参数 `k`**） |
| `TYPE_OTHER` | 未匹配上述规则；`normalized` 多为 `None`，**不会入队** |

### 2.2 规范化规则（与源码一致）

1. **相对路径** `url.startswith('/')` → 补全为 `https://www.amazon.com` + 路径。  
2. **Product**：正则 `(?:/dp/|/gp/product/)([A-Z0-9]{10})` → `https://www.amazon.com/dp/{ASIN}/`。  
3. **Seller**：`[?&](?:seller|me)=([A-Z0-9]{10,})` → `https://www.amazon.com/s?me={id}`。  
4. **Store**：`/stores/(?:brand/)?page/{UUID}`，UUID 为 36 位十六进制连字符形式（`re.IGNORECASE`）。  
5. **Category**：URL 中含 `/b?` 或 `/b/`，且能匹配 `node=(\d+)` → `https://www.amazon.com/b?node={id}`。  
6. **Search**：路径含 `/s?`，且 `parse_qs` 后存在键 `k` → `https://www.amazon.com/s?k={k 的第一个值}`（**不保留 `rh` 等其它参数**）。  
7. **其它**（如部分 `/s?` 无 `k`、Bestseller、Deal 等）：返回 `(None, TYPE_OTHER)`。

### 2.3 队列优先级（数值越小越先执行）

| 优先级值 | 类型 | 说明 |
|---------|------|------|
| 0 | Seller | 尽快验证卖家页 |
| 1 | Product | 主数据与发散 |
| 2 | Store | 列表类，默认优先级 |
| 3 | Search | 列表类；未知类型也按 3 处理 |

---

## 3. 统一图遍历（当前实现）

### 3.1 访问与失败语义

- 在 `process_url` 中：**先入队标记已访问**（`VisitedTracker.mark_visited`），再 `fetch_page`。  
- 若抓取失败或 CAPTCHA 仍失败：**该规范化 URL 不会再次入队**（不重试）。

### 3.2 Product 页（`_process_product`）

1. `extract_product_data` → 有 `asin` 且 `title` 则写入 `products` 并计入 `products_crawled`。  
2. `seller_id` 非空且非 `ATVPDKIKX0DER` → 记入 `discovered_seller_ids`，并将 `s?me=` URL 以 **优先级 0** 入队。  
3. `_try_get_other_sellers`：可见则点击 `#aod-ingress-link`，等待后对页面 HTML 做 `extract_seller_urls`，新 seller 入队；尝试 `#aod-close` 关闭。  
4. `extract_product_urls` → 新产品 URL，**优先级 1** 入队。  
5. `extract_search_keywords`（品牌 + 面包屑前 2 段，去重最多 3 个）→ `generate_search_urls` → **优先级 3** 入队；`stats["search_queries"]` 增加的是**本次新入队的搜索 URL 数**。

### 3.3 Seller 页（`_process_seller`）

- 根据 HTML 是否包含错误文案判断 `accessible`。  
- 可访问则合并 `extract_seller_data` 字段，写入 `seller_results["verified"]`；否则 `failed`。  
- **不从卖家页提取产品 URL 或继续发现卖家**。

### 3.4 列表页（`_process_listing`）

- 适用于 Store / Search / Category 等（凡非 Product、Seller 的已规范化 URL）。  
- 仅 `extract_product_urls` → 产品 URL **优先级 1** 入队。

### 3.5 页面抓取（`fetch_page`）

- `goto(..., wait_until='domcontentloaded', timeout=30000)`。  
- 随机等待约 **2000–3500 ms**，滚动到约 **1/3** 页高，再 **500–1000 ms**。  
- 若内容含 `Robot Check` 或 `captcha`（大小写不敏感）：等待 **60s** 再取 HTML；若仍有 `Robot Check` 则返回 `None`；否则写回 `amazon_cookies.json`。

### 3.6 请求节奏

- 每次 `process_url` 结束后 `time.sleep(random.uniform(1.5, 2.5))`。

### 3.7 URL 发现正则（代码中实际使用）

产品链接、data-asin、JSON asin、卖家 ID 等见 `amazon_unified_crawler.py` 中 `extract_product_urls`、`extract_seller_urls`。  
`extract_other_urls`（店铺 `/stores/`、搜索 `/s?k=`）**当前未在爬虫主流程中调用**；若需从列表页跟店铺/搜索，需在 `_process_listing` 中显式接入。

---

## 4. 数据提取（与代码一致）

### 4.1 产品字段（`extract_product_data`）

| 字段 | 实现要点 |
|------|----------|
| asin | 从当前 URL 匹配 `/dp/([A-Z0-9]{10})` |
| title | `productTitle` span 或 JSON `"title"` |
| brand | 中文「访问 … 品牌」、`Visit the … Store`、`"brand"` |
| seller_id | `merchantID` 表单、`/s?me=`、`/sp?seller=`、`merchantId`/`sellerId` JSON；**且长度 ≥ 10** 才采纳 |
| seller_name | `Sold by` 相关 `<a>` 文本 |
| price | `a-price-whole` |
| rating | `([0-9]\.[0-9])\s*out of 5` |
| reviews_count | `ratings` 文案 |
| breadcrumbs | `a-color-tertiary` 链接文本，最多 5 条 |
| images | `hiRes`/`large` URL，最多 5 条 |

### 4.2 卖家页字段（`extract_seller_data` + 验证逻辑）

- `seller_name`：`<title>` 中片段（含 `Amazon.com` 则跳过写入名）  
- `product_count`：`N results`  
- `positive_rate`：`N% positive`

---

## 5. 观察到的现象（经验记录）

以下来自历史实测与页面观察，**不保证与当前 Amazon 页面完全一致**，但仍是排错与改进的参考。

### 5.1 merchantID 为空 / 多卖家

- 多卖家、需选 offer 时，`merchantID` 可能为空；可依赖 Other Sellers 弹层或「See All Buying Options」类交互（当前主脚本已做 `#aod-ingress-link` 路径）。

### 5.2 自营 `ATVPDKIKX0DER`

- 代码中显式排除入队与部分卖家提取；卖家页常出现错误类文案，与「仅验证」策略一致。

### 5.3 中英文混排

- 品牌等字段需中英文多套正则（代码中已包含中文「访问 … 品牌」）。

### 5.4 动态内容与反爬

- 需浏览器自动化与等待；Seller 页、高频请求更易触发 CAPTCHA；可用 `amazon_cookies.json` 登录态缓解。

### 5.5 历史成功率示例（旧实验，非当前脚本承诺）

曾在约 33 个产品样本上统计过字段成功率（如 `seller_id` 偏低等），**仅作背景**，实际以每次运行输出 JSON 为准。

---

## 6. 配置与输出

### 6.1 代码内配置（`amazon_unified_crawler.py`）

| 项 | 说明 |
|----|------|
| `RUNTIME_MINUTES` | 运行时长上限（分钟），构造 `UnifiedAmazonCrawler(..., runtime_minutes=RUNTIME_MINUTES)` |
| `OUTPUT_DIR` | 默认 `amazon_dataset_output` |
| Playwright | `chromium.launch(headless=False)`；Cookie 文件 `amazon_cookies.json`（项目根相对路径） |

起始 URL、时长可在 `main()` 中修改。

### 6.2 输出文件（统一爬虫）

目录：`amazon_dataset_output/`

| 文件模式 | 内容 |
|----------|------|
| `unified_products_{timestamp}.json` | 有 asin+title 的产品记录列表 |
| `unified_seller_verification_{timestamp}.json` | `summary`、`verified_sellers`、`failed_sellers`、`pending_seller_urls` |
| `unified_stats_{timestamp}.json` | `stats` 字典（访问数、爬取产品数、卖家发现/验证/失败、搜索入队计数等） |

无产品或无卖家验证结果时，对应 JSON 可能不生成（统计文件仍会写入）。

### 6.3 运行命令

```bash
python amazon_unified_crawler.py
```

依赖：`playwright` 及已安装 Chromium；首次需按 Playwright 文档安装浏览器。

---

## 7. 脚本清单

### 7.1 主流程（规范）

| 脚本 | 功能 |
|------|------|
| **`amazon_unified_crawler.py`** | 统一队列、Product 发散 + Seller 验证、Other Sellers、当前方法论对应的**唯一主实现** |

### 7.2 其它 Amazon 相关脚本（实验 / 旧版 / 专项）

仍存在于仓库中，行为以各自文件为准，**不再在本方法论中逐条保证与统一爬虫一致**，例如：

- `amazon_recursive_crawler_v2.py`、`amazon_recursive_crawler.py`：偏产品递归/旧流程  
- `amazon_url_discovery.py`、`amazon_crawler_enhanced_discovery.py` 等：发现或增强实验  
- `test_seller_graph.py`、`test_product_to_seller.py`、`test_find_other_sellers.py` 等：单点测试  

需要「仅卖家图深度遍历」或「仅产品递归」时，可打开对应脚本阅读其 `main` 与注释。

---

## 附录

### A. Amazon Seller ID 类型（经验）

| 类型 | 示例/说明 |
|------|-----------|
| Amazon 自营 | `ATVPDKIKX0DER`（代码中排除） |
| 品牌/第三方 | 多种 `A` 开头 ID，长度常见 13–14 位（以实际页面为准） |

### B. Schema 字段清单（4.1 Products Dataset，目标级）

Identity、Pricing、Description、Category、Visual、Availability、Reviews、Variants 等字段为**数据集目标**；当前 `extract_product_data` 仅覆盖其中子集，扩展字段需在脚本中增量实现。

### C. 常见错误处理

| 情况 | 代码侧行为 |
|------|------------|
| CAPTCHA | 等待 60s；仍失败则本次返回空 HTML，URL 已标记访问 |
| 卖家页错误文案 | 归入 `failed_sellers` |
| 无法规范化的 URL | `normalize` 为 `None`，不入队 |

---

**文档结束**

_本文档 v3.0 与 `amazon_unified_crawler.py` 对齐；脚本变更时请同步更新本文相关小节。_
