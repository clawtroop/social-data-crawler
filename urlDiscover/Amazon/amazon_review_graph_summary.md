# Amazon Reviews / Profile / Product 图遍历方案总结

## 1. 目标

从任意一个 Amazon `product URL` 出发，通过图遍历持续发现更多如下形式的评论链接：

```text
https://www.amazon.com/gp/customer-reviews/<REVIEW_ID>/
```

同时利用评论页、用户主页、商品页之间的关联关系，逐步扩展一个由 `product`、`review`、`profile` 三类节点构成的图，并输出去重后的 review URL 集合及对应图结构数据。

---

## 2. 当前观察（Observations）

### 2.1 已确认存在的两类关键页面

当前已确认至少有两类页面会包含 `review URL`：

#### （1）Product 页面

商品页面中存在与该商品相关的评论链接，可用于发现新的 review URL。

典型作用：

- 从一个商品页提取该商品相关的评论链接
- 进一步提取 reviewer 的 profile 链接
- 作为整个遍历图的起始入口

#### （2）用户 Profile 页面

用户主页页面中存在该用户发布过的其他评论，可继续发现更多 review URL。

典型作用：

- 从 profile URL 中直接提取用户标识
- 从页面中提取用户名
- 从该页面中继续提取该用户发表的其他 review URL
- 通过这些 review 再回到其他 product 页面，实现扩展

---

### 2.2 已确认的 URL 形式与可提取信息

#### Review URL

一般格式：

```text
https://www.amazon.com/gp/customer-reviews/R32J2FIH7GB82P/
```

可提取信息：

- `review_id`：可直接从 URL 中提取
- 页面正文中还可能包含：
  - review 标题
  - rating
  - review date
  - helpful votes
  - 作者 profile URL
  - 被评论商品 product URL

#### 用户 Profile URL

一般格式：

```text
https://www.amazon.com/gp/profile/amzn1.account.AE3IX2SYIJNO2D3AWYV47EYMXVJQ/
```

可提取信息：

- `profile_id`：可直接从 URL 中提取
- `username`：可从页面内容中提取
- 页面中可能包含：
  - 该用户发表的其他 review URL
  - 这些评论对应的 product URL

#### Product URL

一般格式：

```text
https://www.amazon.com/dp/<ASIN>/
```

可提取信息：

- `asin`：可直接从 URL 中提取
- 页面中可能包含：
  - 商品标题
  - 与该商品相关的 review URL
  - reviewer 的 profile URL

---

## 3. 图遍历建模（Graph Model）

### 3.1 节点类型

将遍历对象统一建模为三类节点：

- `product`
- `review`
- `profile`

### 3.2 主要边关系

根据页面间的可跳转关系，可构造如下边：

- `product -> review`
- `product -> profile`
- `profile -> review`
- `profile -> product`
- `review -> profile`
- `review -> product`

这意味着：

- 商品页可以发现评论与评论作者
- 用户主页可以发现该用户写过的评论以及评论对应商品
- 评论页可以反向连接评论作者与被评论商品

因此三类节点之间形成一个可扩展的闭环图，而不是只在某一类页面内做单点抓取。

---

## 4. 方法（Method）

## 4.1 总体思路

整体方法采用**统一队列 + URL 规范化 + 图遍历扩展**的方式。

核心过程如下：

1. 从任意一个 product URL 出发
2. 对 URL 做规范化并识别节点类型
3. 将待访问节点放入统一优先级队列
4. 抓取页面 HTML
5. 按页面类型调用相应解析逻辑
6. 从当前页面中提取更多 `product / review / profile` URL
7. 形成新的图边关系，并将未访问节点继续入队
8. 重复上述过程直到时间耗尽或队列为空

---

### 4.2 URL 规范化（Normalization）

为避免重复抓取和不同 URL 形式造成的数据冗余，需要首先对 URL 做规范化。

规范化策略包括：

- Product：
  - 识别 `/dp/<ASIN>` 或 `/gp/product/<ASIN>`
  - 统一规范成：
    ```text
    https://www.amazon.com/dp/<ASIN>/
    ```
- Review：
  - 识别 `/gp/customer-reviews/<REVIEW_ID>`
  - 统一规范成：
    ```text
    https://www.amazon.com/gp/customer-reviews/<REVIEW_ID>/
    ```
- Profile：
  - 识别 `/gp/profile/<PROFILE_ID>`
  - 统一规范成：
    ```text
    https://www.amazon.com/gp/profile/<PROFILE_ID>/
    ```

规范化后的 URL 可作为：

- 去重键
- 访问状态键
- 图节点唯一标识

---

### 4.3 遍历队列设计

采用统一优先级队列管理待访问 URL。

可用的优先级策略为：

- `product`：中优先级  
原因：product 页面通常是 review 与 profile 的主要发现源，也是起点
- `profile`：次优先级  
原因：profile 页面能继续扩展出同一用户更多 review
- `review`：高优先级  
原因：review 页面主要用于补足作者、商品、元数据和反向连接

这一策略的直觉是：优先确认已经发现的 review url 的合法性并输出，其次是抓取“扩展能力更强”。

---

### 4.4 三类页面的处理逻辑

#### （1）处理 Product 页面

主要任务：

- 提取商品基础信息：
  - `asin`
  - `title`
- 提取页面中的 `review URL`
- 提取页面中的 `profile URL`
- 建立边：
  - `product -> review`
  - `product -> profile`
- 将新发现的 review/profile 节点入队

#### （2）处理 Profile 页面

主要任务：

- 提取：
  - `profile_id`
  - `username`
- 提取该用户发表过的 review URL
- 提取这些 review 关联的商品 product URL
- 建立边：
  - `profile -> review`
  - `profile -> product`
- 将新发现的 review/product 节点入队

#### （3）处理 Review 页面

主要任务：

- 提取：
  - `review_id`
  - `review_title`
  - `rating`
  - `review_date`
  - `helpful_votes`
- 从评论页反向提取：
  - 作者 `profile URL`
  - 被评论商品 `product URL`
- 建立边：
  - `review -> profile`
  - `review -> product`
- 将新发现的 profile/product 节点入队

---

### 4.5 CAPTCHA 处理原则

参考已有代码中的处理机制，CAPTCHA 部分只做**检测、暂停、继续**，不做自动绕过。

具体原则：

1. 页面抓取后检测是否为 CAPTCHA 页面
2. 若命中 CAPTCHA：
  - 先等待一段时间
  - 再重新获取页面内容
3. 如果仍未解除：
  - 允许人工在浏览器中处理验证
  - 验证通过后继续执行
4. 验证通过后保存 cookies，供后续复用

该策略的作用是：

- 保留现有浏览器态与登录态
- 避免每次重启都重新验证
- 维持图遍历过程的连续性

需要注意的是，这种机制本质上是**人工辅助恢复流程**，不是自动化绕过。

---

### 4.6 访问状态管理

为避免原型爬虫中常见的“抓取失败但已标记访问”的问题，访问状态管理应满足：

- URL 只有在**成功获取 HTML 后**才标记为 visited
- 队列中额外维护 `queued_urls` 集合，用于快速去重
- `visited` 与 `queued` 分离管理

这样可以减少以下问题：

- 页面请求失败后永久丢失
- 队列重复扫描导致性能下降
- 同一 URL 被多次入队

---

## 5. 输出（Outputs）

该方法的典型输出包括三类：

### 5.1 图数据

保存为 JSON，包含：

- `products`
- `profiles`
- `reviews`
- `edges`
- `pending_urls`

可用于后续：

- 图分析
- review URL 覆盖率分析
- 节点关系统计
- 可视化

### 5.2 Review URL 列表

保存为去重后的文本文件，例如：

```text
review_urls_*.txt
```

用于：

- 后续定向抓取 review 页
- 构建评论数据集
- 做 URL 批量验证

### 5.3 统计信息

保存为统计 JSON，例如：

- 已抓取 product 数
- 已抓取 profile 数
- 已抓取 review 数
- 已发现 URL 总数
- CAPTCHA 命中次数
- 抓取失败次数

---

## 6. 当前方法的优点

### 6.1 从单个 product 种子即可扩展

不需要一开始就掌握大量 review URL，只要有一个 product URL 即可作为起点。

### 6.2 review 发现链路完整

不是只从 product 页面提取评论，而是通过：

- `product -> review`
- `review -> profile`
- `profile -> more reviews`

形成持续扩展的闭环。

### 6.3 三类节点统一管理

product、review、profile 都在统一框架下规范化、去重、排队、解析，便于维护。

### 6.4 适合增量构图

输出天然就是图结构，后续可扩展为：

- reviewer 行为图
- 商品-评论-用户三部图
- 评论传播/关联分析图

---

## 7. 当前局限（Limitations）

### 7.1 高度依赖页面 DOM 结构

review/profile/product 页的提取逻辑依赖页面 HTML 结构，Amazon 改版后正则可能失效。

### 7.2 当前主要抓“当前页面可见内容”

如果某些评论需要翻页、点击“See all reviews”、展开更多内容，当前版本可能无法完全覆盖。

### 7.3 CAPTCHA 仍然会中断流程

当前机制只是人工辅助恢复，不保证长时间无人值守运行。

### 7.4 数据提取仍以保守字段为主

目前重点是发现 review URL，而不是构建高完备度评论语义数据集。因此字段提取策略偏保守。

---

## 8. 后续可扩展方向

### 8.1 增加分页遍历

在 profile 页面和评论列表页面中支持：

- 下一页
- 展开更多评论
- “See all reviews” 跳转

### 8.2 增加更稳定的解析方式

将部分关键字段从简单正则提取升级为：

- DOM 定位
- JSON-LD / embedded JSON 提取
- Playwright selector 精准解析

### 8.3 引入断点恢复

保存：

- 已访问 URL
- 队列状态
- 节点与边增量结果

便于长时间运行后继续扩展。

### 8.4 加入图去重与关系校验

对边关系进一步做一致性检查，例如：

- 同一个 review 是否只对应一个 product
- 同一个 review 的 author 是否唯一
- profile 页面列出的 review 与单 review 页面信息是否一致

---

## 9. 总结

基于当前观察，可以将 Amazon 评论发现任务建模为一个由 `product`、`review`、`profile` 三类节点构成的统一图遍历问题。

其中：

- `product` 页面是入口与评论发现源
- `profile` 页面是同一用户多评论扩展源
- `review` 页面是作者与商品的连接节点

方法上，采用：

- URL 规范化
- 统一优先级队列
- 页面类型分发解析
- 图边持续扩展
- CAPTCHA 检测后人工恢复继续

可以从单个 product URL 出发，逐步发现更多 review URL，并同时保留节点与边的图结构信息，为后续评论数据集构建和图分析提供基础。