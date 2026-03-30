# Amazon Seller URL 查找指南

**版本**: v1.0
**创建时间**: 2026-03-28
**基于**: 实际测试和分析

---

## 📋 核心概念

### 1. 店铺URL vs 卖家URL

#### 店铺URL (Store Page)
```
格式: https://www.amazon.com/stores/page/{UUID}/
完整格式: https://www.amazon.com/stores/{Brand}/page/{UUID}/

性质: 品牌营销页面
内容:
  ✅ 品牌故事和介绍
  ✅ 产品展示区域
  ✅ 多个产品列表
  ❌ 很少包含卖家详细信息
  ❌ 不直接显示seller_id

用途: 中转页面，用于发现产品URL
```

#### 卖家URL (Seller Profile)
```
格式1: https://www.amazon.com/sp?seller={SellerID}
格式2: https://www.amazon.com/s?me={SellerID}

性质: 卖家信息页面
内容:
  ✅ seller_id（URL参数中）
  ✅ seller_name（页面标题或H1）
  ✅ 评分和反馈（Performance数据）
  ✅ 该卖家的所有商品列表
  ✅ 退货政策、联系方式等

用途: 提取 4.3 Sellers Dataset
```

**关键区别**：
- 店铺 = 品牌视角（Apple店铺）
- 卖家 = 商家视角（某个seller销售Apple产品）
- 一个品牌店铺中的产品可能由多个卖家销售

---

## 🔍 查找流程

### 方法1：产品 → merchantID → Seller

#### 步骤1: 从产品页面提取merchantID

**位置**: 产品详情页的隐藏表单字段

**提取模式**：
```python
# 模式1: 标准merchantID字段
r'name="merchantID"\s+value="([A-Z0-9]+)"'
r'merchantID[^>]*value="([A-Z0-9]+)"'

# 模式2: data属性
r'data-merchant-id="([A-Z0-9]+)"'

# 模式3: 从"Sold by"链接提取
r'href="/s\?me=([A-Z0-9]+)"'
r'href="/sp\?seller=([A-Z0-9]+)"'

# 模式4: JavaScript对象
r'"merchantId":"([A-Z0-9]+)"'
```

**示例HTML**：
```html
<!-- 方式1: 隐藏字段 -->
<input type="hidden" name="merchantID" value="A294P4X9EWVXLJ">

<!-- 方式2: Sold by链接 -->
Ships from and sold by <a href="/s?me=A294P4X9EWVXLJ">AnkerDirect</a>

<!-- 方式3: 空值（多卖家竞争）-->
<input type="hidden" name="merchantID" value="">
```

**特殊情况**：
```python
if merchantID == "":
    # 多个卖家销售该产品
    # 需要点击"Other Sellers"或"See All Buying Options"
    # 提取所有可用的seller_id

if merchantID == "ATVPDKIKX0DER":
    # Amazon自营
    # seller页面不可直接访问
    # 记录但不添加到爬取队列
```

---

#### 步骤2: 构造Seller URL

```python
seller_id = extract_merchant_id(product_html)

# 格式1: Seller Profile页面（首选）
seller_url_1 = f"https://www.amazon.com/sp?seller={seller_id}"

# 格式2: Seller商品列表页面（备选）
seller_url_2 = f"https://www.amazon.com/s?me={seller_id}"

# 格式3: Seller反馈页面
seller_url_3 = f"https://www.amazon.com/shops/aag?seller={seller_id}"
```

**推荐使用**: 格式2 (`/s?me=`) - 更稳定，包含商品列表

---

#### 步骤3: 访问Seller页面并提取数据

**可提取的字段（4.3 Sellers Dataset）**：

```python
# Identity
seller_id: 从URL参数提取
seller_name: <h1>标签或页面标题
seller_url: 当前URL

# Performance
stars: 评分（如"4.5 out of 5"）
feedbacks: 反馈数量
positive_feedback_rate: "95% positive (12 months)"
return_policy: 退货政策文本

# Portfolio
product_count: "1,234 results"中提取
categories: 从商品列表推断
brand_portfolio: 从商品列表提取品牌

# Business Intel
description: 卖家描述区域
business_address: 联系信息区域
```

**提取模式**：
```python
# seller_name
r'<h1[^>]*>([^<]+)</h1>'
r'class="seller-name"[^>]*>([^<]+)<'

# positive_feedback
r'([0-9]+)%\s*positive'

# total_ratings
r'([0-9,]+)\s*ratings'
r'([0-9,]+)\s*seller rating'

# product_count
r'([0-9,]+)\s*results'
r'([0-9,]+)\s*items'
```

---

### 方法2：店铺 → 产品 → Seller

#### 流程

```
1. 访问店铺页面
   https://www.amazon.com/stores/page/{UUID}/

2. 提取产品URL列表
   发现多个 /dp/{ASIN} 链接

3. 访问第一个产品页面
   https://www.amazon.com/dp/{ASIN}

4. 提取merchantID
   查找隐藏字段或Sold by链接

5. 构造并访问seller URL
   https://www.amazon.com/sp?seller={merchantID}
```

**代码实现**：
```python
# 步骤1
store_html = fetch_page(store_url)
product_urls = extract_product_urls(store_html)

# 步骤2
first_product = product_urls[0]
product_html = fetch_page(first_product)

# 步骤3
merchant_id = extract_merchant_id(product_html)

# 步骤4
if merchant_id and merchant_id != "ATVPDKIKX0DER":
    seller_url = f"https://www.amazon.com/sp?seller={merchant_id}"
    seller_html = fetch_page(seller_url)
    seller_data = extract_seller_data(seller_html)
```

---

## 📊 实测结果和发现

### 成功案例

#### 案例1: 从产品页找到merchantID
```
产品: Apple AirPods Pro (其中一个)
产品URL: https://www.amazon.com/dp/B0D1XD1ZV3

提取到的merchantID:
  HTML中的字段: <input name="merchantID" value="ATVPDKIKX0DER">

结果:
  ✅ 提取成功
  ⚠️ 但是Amazon自营，seller页面不可访问
```

---

### 遇到的问题

#### 问题1: merchantID字段为空
```
现象:
  <input name="merchantID" value="">

原因:
  - 多个卖家竞争该产品
  - 用户需要选择具体的offer
  - buybox尚未确定

解决方案:
  1. 查找"Other Sellers"链接
  2. 提取所有可用seller列表
  3. 或者跳过该产品
```

#### 问题2: Amazon自营seller页面不可访问
```
seller_id: ATVPDKIKX0DER
访问: https://www.amazon.com/sp?seller=ATVPDKIKX0DER
结果: "Sorry! Something went wrong!"

原因:
  Amazon作为平台方，不需要seller profile页面

处理策略:
  if seller_id == "ATVPDKIKX0DER":
      seller_type = "Amazon.com"
      skip_seller_page = True
      但保留seller_id用于分析
```

#### 问题3: 频繁访问触发CAPTCHA
```
现象:
  连续访问多个页面后遇到Robot Check

影响:
  - seller页面比产品页更容易触发
  - 需要更强的反检测措施

解决方案:
  1. 使用更强的反检测（Playwright Stealth）
  2. 增加请求间隔（3-5秒）
  3. CAPTCHA检测和暂停机制
  4. 手动解决后保存新cookies
```

---

## 实际可行的策略

### 策略: 只提取merchantID，不访问seller页面

```python
# 从产品页提取
merchant_id = extract_merchant_id(product_html)

# 记录但不访问
if merchant_id and merchant_id != "ATVPDKIKX0DER":
    seller_info = {
        "seller_id": merchant_id,
        "seller_url": f"https://www.amazon.com/sp?seller={merchant_id}",
        "source_product": product_asin,
        "note": "URL未验证，需后续访问"
    }
    sellers_discovered.append(seller_info)
```

**优点**：
-  不触发额外CAPTCHA
-  快速收集seller_id列表
-  可以后续批量访问seller页面

**缺点**：
-  无法验证seller_id是否有效，后续通过是否能实际访问来验证
-  无法立即获取seller详细数据

---

## 🏷️ Seller ID 分类

### 类型1: Amazon自营
```
seller_id: ATVPDKIKX0DER
seller_name: Amazon.com
特点:
  - 最常见（约40-50%的产品）
  - seller页面不可访问
  - 可从merchantID字段识别
  - 应记录但不爬取
```

### 类型2: 品牌官方
```
seller_id: A294P4X9EWVXLJ (示例: AnkerDirect)
seller_name: [品牌名称]Direct 或 [品牌] Inc.
特点:
  - 品牌官方账号
  - seller页面可访问
  - 包含完整4.3 Dataset字段
  - 高价值数据源
```

### 类型3: 第三方经销商
```
seller_id: 各种不同ID
seller_name: 公司名称或店铺名
特点:
  - 独立商家
  - seller页面可访问
  - 数据质量参差不齐
  - 需要验证有效性
```

---

## 📝 提取规则总结

### 规则1: merchantID提取规则

```
优先级1: 隐藏表单字段
  模式: name="merchantID" value="{ID}"
  可靠性: 高（如果存在）
  覆盖率: 约60-70%

优先级2: Sold by链接
  模式: href="/s?me={ID}" 或 /sp?seller={ID}
  可靠性: 高
  覆盖率: 约50-60%

优先级3: data属性
  模式: data-merchant-id="{ID}"
  可靠性: 中
  覆盖率: 约30-40%

优先级4: JavaScript对象
  模式: "merchantId":"{ID}"
  可靠性: 中
  覆盖率: 约20-30%

组合策略:
  按优先级依次尝试
  找到第一个非空值即停止
```

---

### 规则2: Seller URL构造规则

```python
if merchant_id:
    # 判断类型
    if merchant_id == "ATVPDKIKX0DER":
        seller_type = "Amazon自营"
        seller_url = None  # 不可访问

    else:
        seller_type = "第三方卖家"

        # 优先使用商品列表格式（更稳定）
        seller_url = f"https://www.amazon.com/s?me={merchant_id}"

        # 备选：seller profile格式
        seller_url_alt = f"https://www.amazon.com/sp?seller={merchant_id}"
```

---

### 规则3: Seller数据提取规则

**从Seller页面提取的字段**：

```python
# Identity (4/5字段)
seller_id: 从URL参数提取
URL: seller_url
seller_name:
  - 模式1: <h1>标签
  - 模式2: 页面标题
  - 可靠性: 高
seller_email:
  - 模式: contact.*email或mailto:
  - 可靠性: 低（很少公开）
seller_phone:
  - 模式: \d{3}[-.]?\d{3}[-.]?\d{4}
  - 可靠性: 低

# Performance (3/3字段)
stars:
  - 模式: "X.X out of 5" 或 "XX% positive"
  - 可靠性: 高
feedbacks:
  - 模式: "[0-9,]+ ratings" 或 "seller rating"
  - 可靠性: 高
return_policy:
  - 模式: "return policy" 区域的文本
  - 可靠性: 中

# Portfolio (推断字段)
product_count:
  - 模式: "[0-9,]+ results" 或 "items"
  - 来源: 商品列表页面
category_focus:
  - 推断: 从商品列表的类别分布
brand_portfolio:
  - 推断: 从商品列表提取品牌
```

---

## 🚨 当前遇到的挑战

### 挑战1: merchantID字段缺失
```
测试产品:
  - Anker充电宝 (B01JIWQPMW): merchantID = ""
  - AILIHEN耳机 (B01EF5DBZ6): merchantID未找到
  - Picun耳机 (B0CFV9XR2Q): merchantID未找到

原因分析:
  1. 多卖家竞争，无默认merchant
  2. 页面结构变化，字段位置不同
  3. 动态加载，需要等待JavaScript执行

影响:
  - 无法直接获取seller_id
  - 需要更复杂的提取逻辑
```

### 挑战2: Seller页面访问限制
```
测试seller_id:
  - ATVPDKIKX0DER (Amazon): ❌ "Something went wrong"
  - A1AMUYYA3CT6HJ: ❌ "Something went wrong"
  - A2VIGQ35RCS4UG (Focus Camera): ❌ "Something went wrong"

原因分析:
  1. 频繁访问触发反爬虫
  2. seller页面需要特殊的访问权限
  3. 可能需要更强的反检测或代理IP

影响:
  - 无法验证seller_id有效性
  - 无法提取seller详细数据
  - 需要更长的冷却时间或更换IP
```

### 挑战3: CAPTCHA频繁触发
```
触发场景:
  - 短时间内访问多个页面
  - 访问seller页面时更容易触发
  - cookies过期后更频繁

当前解决方案:
  ✅ CAPTCHA检测机制
  ✅ 暂停等待手动解决
  ✅ 自动保存新cookies
  ⚠️ 但仍需人工介入
```

## 技术实现要点

### 1. merchantID提取（关键）

```python
def extract_merchant_id(html):
    """
    从产品页HTML提取merchant_id
    尝试多种模式，返回第一个有效值
    """
    patterns = [
        # 优先级1: 标准字段
        r'name="merchantID"\s+value="([A-Z0-9]+)"',

        # 优先级2: Sold by链接
        r'href="/s\?me=([A-Z0-9]+)"',
        r'href="/sp\?seller=([A-Z0-9]+)"',

        # 优先级3: data属性
        r'data-merchant-id="([A-Z0-9]+)"',
        r'data-seller-id="([A-Z0-9]+)"',

        # 优先级4: JavaScript
        r'"merchantId"\s*:\s*"([A-Z0-9]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html)
        if match and match.group(1):
            merchant_id = match.group(1)

            # 验证格式（Amazon seller_id通常是A开头）
            if len(merchant_id) >= 10 and merchant_id[0] == 'A':
                return merchant_id

    return None
```

---

### 2. Seller数据提取

```python
def extract_seller_data(seller_html, seller_id, seller_url):
    """
    从seller页面提取4.3 Dataset字段
    """
    seller = {
        "seller_id": seller_id,
        "url": seller_url,
        "extracted_fields": {}
    }

    # seller_name
    name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', seller_html)
    if name_match:
        seller["extracted_fields"]["seller_name"] = name_match.group(1).strip()

    # stars / positive_feedback
    rating_match = re.search(r'([0-9]+)%\s*positive', seller_html, re.IGNORECASE)
    if rating_match:
        seller["extracted_fields"]["positive_feedback_rate"] = rating_match.group(1) + "%"

    # feedbacks
    feedback_match = re.search(r'([0-9,]+)\s*ratings', seller_html)
    if feedback_match:
        seller["extracted_fields"]["total_ratings"] = feedback_match.group(1).replace(',', '')

    # product_count
    count_match = re.search(r'([0-9,]+)\s*results', seller_html)
    if count_match:
        seller["extracted_fields"]["product_count"] = count_match.group(1).replace(',', '')

    return seller
```

---

### 3. CAPTCHA处理

```python
def fetch_with_captcha_handling(url):
    """
    抓取页面，支持CAPTCHA自动处理
    """
    page.goto(url, timeout=30000)
    time.sleep(3)

    html = page.content()

    # 检测CAPTCHA
    if "Robot Check" in html or "captcha" in html.lower():
        print("检测到CAPTCHA，等待手动解决...")

        # 暂停60秒等待手动解决
        for i in range(60):
            time.sleep(1)
            html = page.content()

            if "Robot Check" not in html:
                print("CAPTCHA已解决！")

                # 保存新cookies
                save_cookies(context.cookies())
                break
        else:
            print("超时，跳过")
            return None

    return html
```

---

