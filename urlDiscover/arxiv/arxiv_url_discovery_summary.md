# arXiv URL 发现系统：当前方法与发现总结

## 1. 文档目的

本文档总结当前 arXiv URL 发现系统的方法演进、关键设计选择、已发现的问题、修改后的实现思路，以及当前推荐采用的方案。

这里的目标不是构建一个“论文信息展示器”，而是构建一个**面向 URL 发现的递归扩展系统**：从一个 seed paper 出发，尽可能多地发现新的 arXiv 论文 URL，并保留必要的来源信息与扩展线索。

---

## 2. 任务目标的澄清

当前任务的核心目标是：

1. 从一个给定的 arXiv 论文 URL 或论文 ID 出发；
2. 尽可能发现更多有效的 arXiv 论文 URL；
3. 不仅依赖页面中直接出现的 arXiv ID，还利用论文页中的元信息构造新的搜索入口；
4. 通过递归扩展形成更大的论文 URL 集合。

因此，系统的目标函数不是：

```text
最大化单篇论文的信息提取完整度
```

而是：

```text
最大化可发现的唯一 arXiv URL 数量
```

但与此同时，论文页中的作者、分类、标题关键词等信息并不是冗余信息，因为它们可以进一步生成新的搜索入口。因此，本系统采用的是：

```text
信息提取 + 查询扩展（query expansion） + 递归发现
```

的混合路线。

---

## 3. 原始脚本的基本思路

原始脚本的基本设计是合理的，主要包括以下几部分：

### 3.1 URL 类型区分

系统将 URL 分为两类：

- **目标 URL（paper page）**：形如 `https://arxiv.org/abs/{id}` 的单篇论文页面；
- **中间 URL（intermediate page）**：如搜索页、分类列表页、GitHub 页面等。

这一划分的重要性在于：

- 论文页本身属于有效发现结果；
- 中间页本身不一定是目标，但可以作为跳板继续发现新的论文 URL。

### 3.2 BFS 风格扩展

原始脚本采用队列进行广度优先扩展：

1. 从 seed paper 开始；
2. 访问当前 URL；
3. 若是论文页，则提取页面信息并继续扩展；
4. 若是中间页，则从页面中提取 arXiv ID 并加入队列；
5. 持续迭代，直到达到数量、深度或时间限制。

### 3.3 从论文页中提取扩展线索

原始脚本尝试从论文页中提取：

- 页面中直接出现的相关 arXiv ID；
- 作者；
- 分类；
- 标题中的关键词。

再据此生成新的中间入口：

- 作者搜索页；
- 分类列表页；
- 关键词搜索页。

这个设计方向是对的，因为它已经体现了“**论文页信息是为了构造新搜索入口**”这一核心思想

---

## 4. 优化：BeautifulSoup 版本 + 更稳的 query expansion

第二次修改的核心目标有两个：

1. 用 **BeautifulSoup** 提升页面解析稳定性；
2. 用更稳的 query expansion 策略提升发现质量与控制力。

### 4.1 为什么要换成 BeautifulSoup

正则适合提取简单模式，但不适合承担完整 HTML 解析任务。使用 BeautifulSoup 的主要收益有：

- 可以基于页面结构定位元素，例如 `meta`、`div.authors`、`a[href]`；
- 对页面结构变化更不敏感；
- 更容易扩展为多种解析器；
- 代码语义更清晰。

### 4.2 论文页解析的改进

BeautifulSoup 版本中，论文页信息提取优先使用：

#### 标题

优先顺序：

1. `meta[name="citation_title"]`
2. `h1.title`
3. `title` 标签 fallback

#### 作者

优先顺序：

1. `meta[name="citation_author"]`
2. `div.authors a`

#### 分类

优先从：

- `.primary-subject`
- 指向 `/list/{code}/...` 的链接
- 页面文本中类似 `cs.AI`、`stat.ML` 的分类代码

中提取。

#### 相关论文 ID

从以下来源综合提取：

- `meta` 标签；
- 页面中的链接 `a[href]`；
- 页面全文本 fallback。

这样比单纯在 HTML 字符串中跑正则更稳。

### 4.3 Query Expansion 的稳健化

BeautifulSoup 版本中不再只做“单关键词搜索”，而是把扩展入口分层：

#### 1）直接 related IDs

这是最强信号。若论文页中直接出现其他 arXiv ID，则优先扩展到对应论文页。

#### 2）作者搜索

作者本身是高价值扩展源，通常能带来同一研究方向或同一作者团队的其他论文。

#### 3）分类列表页

若能够识别分类代码，例如 `cs.AI`、`cs.LG`，则可构造：

```text
https://arxiv.org/list/{category_code}/recent
```

这是一种高召回的批量入口。

#### 4）标题短语搜索（phrase search）

相比只搜索单个关键词，标题中连续的 2-gram / 3-gram 更接近真实主题短语，能降低噪声。

例如：

- 单关键词：`learning`
- 短语搜索：`"machine learning"`

后者通常更稳。

#### 5）标题关键词搜索

依然保留，但不再是唯一扩展方式。

#### 6）作者 + 关键词联合搜索

用于在召回与精度之间取得平衡。其特点是：

- 比纯作者搜索更聚焦；
- 比纯关键词搜索更少噪声。

### 4.4 引入优先级调度

相比普通 BFS，BeautifulSoup 版本引入优先级队列，使更可能产出新论文 URL 的入口优先被处理。

一个建议的优先级顺序如下：

1. seed paper
2. sample 中直接给出的 related paper IDs
3. 论文页直接提取出的 related paper IDs
4. 搜索页 / 列表页的分页 next
5. author search
6. category list
7. phrase search
8. keyword search
9. author + keyword search
10. concept search
11. GitHub 页面

这样做的原因是：不同扩展源的“单位处理成本 / 可能新增 URL 数量”并不相同。

### 4.5 引入分页跟进

搜索页和分类列表页不再只处理首页，而是尝试提取 next page 链接，但会设置分页深度或 offset 上限，防止无限翻页导致搜索空间爆炸。

这使得系统可以在可控范围内扩大检索范围。

### 4.6 URL 统一归一化

BeautifulSoup 版本中加入了统一 URL 规范化策略：

- `abs` / `pdf` / `html` 形式都统一归一到 `https://arxiv.org/abs/{id}`；
- 中间页去掉 fragment；
- query 参数排序。

这样可以提高去重质量，减少伪重复。

---

## 5. 当前推荐方案

目前最推荐使用的是：

```text
BeautifulSoup + 优先队列 + 稳健 query expansion + 分页受控跟进
```

这一版比原始版本的主要优势是：

1. 页面解析更稳；
2. 元信息抽取更完整；
3. query expansion 更符合发现任务；
4. 重复 URL 更少；
5. 中间页的价值被更合理地利用；
6. 搜索过程更容易调控。

---

## 6. 当前版本的整体流程

当前推荐流程可以概括为：

```text
seed paper
  -> 访问论文页
  -> 提取 related IDs / authors / category codes / title phrases / keywords
  -> 生成新入口（paper / author search / category list / phrase search / keyword search / author+keyword search）
  -> 优先队列调度
  -> 访问搜索页 / 列表页 / GitHub 页
  -> 提取更多 arXiv IDs + 适度跟进分页
  -> 继续扩展
```

这一路线兼顾了：

- 直接发现；
- 基于元信息的主动搜索；
- 对搜索空间的控制。

---

## 7. 当前建议的参数设置

先从小规模验证开始

### 7.1 小规模验证参数

```python
max_papers = 100
max_depth = 2
max_duration = 60
sleep_seconds = 0.2
max_authors_per_paper = 2
max_keywords_per_paper = 2
max_phrases_per_paper = 1
enable_author_keyword_search = True
```

适用于验证：

- 作者提取是否正常；
- phrase search 是否产出更多 URL；
- 分页机制是否工作；
- 队列是否可控。

### 7.2 中等规模参数

```python
max_papers = 1000
max_depth = 4
max_duration = 300
sleep_seconds = 0.3
max_authors_per_paper = 3
max_keywords_per_paper = 3
max_phrases_per_paper = 2
max_pagination_offset = 200
```

适用于实际扩展搜索。

---

## 8. 当前已形成的关键方法结论

基于目前的方法演进，可以得到以下结论：

### 8.1 论文页信息提取不是冗余，而是 query expansion 的基础

如果目标只是记录论文信息，那么作者、分类、标题关键词的作用有限；但如果目标是构造更多搜索入口，它们就是有价值的扩展特征。

### 8.2 “直接从页面提 ID” 和 “利用元信息做搜索扩展” 应同时保留

仅依赖页面中直接出现的 arXiv ID，发现范围有限；
仅依赖作者搜索 / 关键词搜索，噪声较高。

两者结合效果更好：

- direct IDs 负责高精度扩展；
- author/category/phrase/keyword search 负责提高召回。

### 8.3 Phrase search 通常比单关键词搜索更稳

单个关键词往往过于宽泛，而标题中提取的短语更能表达真实主题。

### 8.4 分类列表页是高召回入口，但要控制噪声

分类 recent 页一次能带来大量论文 URL，但也更容易引入与 seed paper 不直接相关的内容，因此应有限度使用。

### 8.5 优先级调度优于无差别 BFS

并不是所有入口都值得同等优先级。优先处理最有可能产出新论文 URL 的入口，通常能更有效利用时间与请求预算。

### 8.6 分页跟进有价值，但必须限流

搜索页和列表页的下一页能够显著提高发现数，但如果无限翻页，搜索空间会迅速失控。

---

## 9. 当前结论

综合来看，当前最合理的方案不是：

```text
只从页面里抓 arXiv ID
```

也不是：

```text
只依赖论文页元信息构造搜索
```

而是：

```text
直接 ID 提取 + 元信息驱动的 query expansion + 优先级调度 + 受控分页扩展
```

具体而言：

1. **论文页**既是目标 URL，也是高价值扩展源；
2. **搜索页 / 列表页 / GitHub 页**主要充当中间跳板；
3. **BeautifulSoup 版**比原始正则版更适合作为当前主实现；
4. **作者、分类、标题短语、关键词**都应保留，但应服务于“构造新入口”这一目的；
5. **优先队列 + 分页受控跟进**是当前版本中最值得保留的工程设计。

---

## 10. 一句话总结

当前系统的本质可以概括为：

> 以论文页为核心扩展节点，结合页面直接提取和基于元信息的查询扩展，在受控搜索空间内尽可能发现更多 arXiv 论文 URL。

