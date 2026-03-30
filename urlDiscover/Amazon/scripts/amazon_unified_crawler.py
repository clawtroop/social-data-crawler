# -*- coding: utf-8 -*-
"""
Amazon 统一图遍历爬虫
合并产品爬取和卖家发现，统一遍历

核心思路：
- Product 页面是核心节点
- 从 Product 页面可以：发现新产品 + 发现新卖家
- 从 Seller 页面可以：发现新产品
- 统一队列管理，优先级调度
"""

import sys
import io
import re
import time
import json
import random
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from heapq import heappush, heappop

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ============================================================
# 配置
# ============================================================

RUNTIME_MINUTES = 60
OUTPUT_DIR = Path("amazon_dataset_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# URL 规范化
# ============================================================

class URLNormalizer:
    TYPE_PRODUCT = "product"
    TYPE_SELLER = "seller"
    TYPE_STORE = "store"
    TYPE_CATEGORY = "category"
    TYPE_SEARCH = "search"
    TYPE_OTHER = "other"

    @staticmethod
    def normalize(url: str) -> tuple:
        if not url:
            return None, None

        if url.startswith('/'):
            url = f"https://www.amazon.com{url}"

        # Product
        asin_match = re.search(r'(?:/dp/|/gp/product/)([A-Z0-9]{10})', url)
        if asin_match:
            return f"https://www.amazon.com/dp/{asin_match.group(1)}/", URLNormalizer.TYPE_PRODUCT

        # Seller
        seller_match = re.search(r'[?&](?:seller|me)=([A-Z0-9]{10,})', url)
        if seller_match:
            return f"https://www.amazon.com/s?me={seller_match.group(1)}", URLNormalizer.TYPE_SELLER

        # Store
        store_match = re.search(r'/stores/(?:([^/]+)/)?page/([A-F0-9-]{36})', url, re.IGNORECASE)
        if store_match:
            brand = store_match.group(1) or ""
            uuid = store_match.group(2)
            if brand:
                return f"https://www.amazon.com/stores/{brand}/page/{uuid}", URLNormalizer.TYPE_STORE
            return f"https://www.amazon.com/stores/page/{uuid}", URLNormalizer.TYPE_STORE

        # Category
        if '/b?' in url or '/b/' in url:
            node_match = re.search(r'node=(\d+)', url)
            if node_match:
                return f"https://www.amazon.com/b?node={node_match.group(1)}", URLNormalizer.TYPE_CATEGORY

        # Search
        if '/s?' in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'k' in params:
                return f"https://www.amazon.com/s?k={params['k'][0]}", URLNormalizer.TYPE_SEARCH

        return None, URLNormalizer.TYPE_OTHER


class VisitedTracker:
    def __init__(self):
        self.visited = set()
        self.info = {}

    def is_visited(self, url: str) -> bool:
        normalized, _ = URLNormalizer.normalize(url)
        return normalized in self.visited if normalized else True

    def mark_visited(self, url: str, url_type: str = None):
        normalized, detected_type = URLNormalizer.normalize(url)
        if normalized:
            self.visited.add(normalized)
            self.info[normalized] = {
                "type": url_type or detected_type,
                "time": datetime.now().isoformat()
            }
        return normalized

    def __contains__(self, url):
        return self.is_visited(url)

    def __len__(self):
        return len(self.visited)


# ============================================================
# 数据提取
# ============================================================

def extract_product_data(html: str, url: str) -> dict:
    """提取产品数据"""
    normalized, _ = URLNormalizer.normalize(url)

    product = {
        "url": normalized,
        "timestamp": datetime.now().isoformat(),
        "extracted_fields": {}
    }

    # ASIN
    asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
    if asin_match:
        product["extracted_fields"]["asin"] = asin_match.group(1)

    # Title
    title_patterns = [
        r'<span id="productTitle"[^>]*>\s*([^<]+?)\s*</span>',
        r'"title"\s*:\s*"([^"]+)"',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            if title and len(title) > 5 and not title.startswith('<'):
                product["extracted_fields"]["title"] = title
                break

    # Brand
    brand_patterns = [
        (r'访问\s*([^\s]+)\s*品牌', 1),
        (r'Visit the ([^<]+) Store', 1),
        (r'"brand"\s*:\s*"([^"]+)"', 1),
    ]
    for pattern, group in brand_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            brand = match.group(group).strip()
            if brand and len(brand) > 1 and len(brand) < 50:
                product["extracted_fields"]["brand"] = brand
                break

    # Seller ID (merchantID)
    merchant_patterns = [
        r'name="merchantID"\s*value="([A-Z0-9]+)"',
        r'href="/s\?me=([A-Z0-9]{10,})"',
        r'href="/sp\?seller=([A-Z0-9]{10,})"',
        r'"merchantId"\s*:\s*"([A-Z0-9]+)"',
        r'"sellerId"\s*:\s*"([A-Z0-9]+)"',
    ]
    for pattern in merchant_patterns:
        match = re.search(pattern, html)
        if match and match.group(1) and len(match.group(1)) >= 10:
            product["extracted_fields"]["seller_id"] = match.group(1)
            break

    # Seller Name
    seller_patterns = [
        r'Sold by\s*</span>\s*<a[^>]*>\s*([^<]+?)\s*</a>',
        r'Sold by\s*<a[^>]*>\s*([^<]+?)\s*</a>',
    ]
    for pattern in seller_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            product["extracted_fields"]["seller_name"] = match.group(1).strip()
            break

    # Price
    price_match = re.search(r'<span class="a-price-whole">([0-9,]+)</span>', html)
    if price_match:
        product["extracted_fields"]["price"] = price_match.group(1).replace(',', '')

    # Rating
    rating_match = re.search(r'([0-9]\.[0-9])\s*out of 5', html)
    if rating_match:
        product["extracted_fields"]["rating"] = rating_match.group(1)

    # Reviews
    reviews_match = re.search(r'([0-9,]+)\s*(?:global\s*)?ratings', html, re.IGNORECASE)
    if reviews_match:
        product["extracted_fields"]["reviews_count"] = reviews_match.group(1).replace(',', '')

    # Breadcrumbs
    breadcrumbs = re.findall(r'<a[^>]*class="[^"]*a-color-tertiary[^"]*"[^>]*>\s*([^<]+?)\s*</a>', html)
    if breadcrumbs:
        product["extracted_fields"]["breadcrumbs"] = [b.strip() for b in breadcrumbs[:5] if b.strip()]

    # Images
    images = set(re.findall(r'"(?:hiRes|large)"\s*:\s*"(https://[^"]+)"', html))
    if images:
        product["extracted_fields"]["images"] = list(images)[:5]

    return product


def extract_seller_data(html: str, seller_id: str, url: str) -> dict:
    """提取卖家数据"""
    seller = {
        "seller_id": seller_id,
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "extracted_fields": {}
    }

    # Seller Name from title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        title = title_match.group(1)
        if "Amazon.com" not in title:
            seller["extracted_fields"]["seller_name"] = title.split(' - ')[0].strip()

    # Product count
    count_match = re.search(r'([0-9,]+)\s*results', html)
    if count_match:
        seller["extracted_fields"]["product_count"] = count_match.group(1).replace(',', '')

    # Positive feedback
    feedback_match = re.search(r'([0-9]+)%\s*positive', html, re.IGNORECASE)
    if feedback_match:
        seller["extracted_fields"]["positive_rate"] = feedback_match.group(1) + "%"

    return seller


def extract_product_urls(html: str, base_url: str) -> list:
    """从页面提取产品URLs"""
    urls = set()

    # href links
    for match in re.finditer(r'href="([^"]*?/dp/[A-Z0-9]{10}[^"]*)"', html):
        url = urljoin(base_url, match.group(1))
        normalized, url_type = URLNormalizer.normalize(url)
        if normalized and url_type == URLNormalizer.TYPE_PRODUCT:
            urls.add(normalized)

    # data-asin
    for asin in re.findall(r'data-asin="([A-Z0-9]{10})"', html):
        urls.add(f"https://www.amazon.com/dp/{asin}/")

    # JSON asin
    for asin in re.findall(r'"asin"\s*:\s*"([A-Z0-9]{10})"', html):
        urls.add(f"https://www.amazon.com/dp/{asin}/")

    return list(urls)


def extract_seller_urls(html: str) -> list:
    """从页面提取卖家URLs"""
    seller_ids = set()

    patterns = [
        r'seller=([A-Z0-9]{10,})',
        r'[?&]me=([A-Z0-9]{10,})',
        r'"sellerId"\s*:\s*"([A-Z0-9]{10,})"',
        r'"merchantId"\s*:\s*"([A-Z0-9]{10,})"',
    ]

    for pattern in patterns:
        for match in re.findall(pattern, html):
            if match and match != "ATVPDKIKX0DER":  # 排除Amazon自营
                seller_ids.add(match)

    return [f"https://www.amazon.com/s?me={sid}" for sid in seller_ids]


def extract_other_urls(html: str, base_url: str) -> list:
    """提取其他类型URLs (store, search等)"""
    urls = set()

    # Store
    for match in re.finditer(r'href="(/stores/[^"]+)"', html):
        url = urljoin(base_url, match.group(1))
        normalized, url_type = URLNormalizer.normalize(url)
        if normalized:
            urls.add(normalized)

    # Search
    for match in re.finditer(r'href="(/s\?k=[^"]+)"', html):
        url = urljoin(base_url, match.group(1))
        normalized, url_type = URLNormalizer.normalize(url)
        if normalized:
            urls.add(normalized)

    return list(urls)


def extract_search_keywords(product: dict) -> list:
    """从产品数据提取搜索关键词"""
    keywords = []
    fields = product.get("extracted_fields", {})

    # 品牌（最重要）
    if "brand" in fields:
        brand = fields["brand"]
        # 清理品牌名
        if brand and not brand.startswith("品牌"):
            keywords.append(brand)

    # 类别
    if "breadcrumbs" in fields and fields["breadcrumbs"]:
        keywords.extend(fields["breadcrumbs"][:2])

    # 去重并限制数量
    seen = set()
    unique = []
    for k in keywords:
        if k and k not in seen and len(k) > 1:
            seen.add(k)
            unique.append(k)

    return unique[:3]


def generate_search_urls(keywords: list) -> list:
    """根据关键词生成搜索URL"""
    urls = []
    for keyword in keywords:
        query = keyword.replace(' ', '+')
        url = f"https://www.amazon.com/s?k={query}"
        normalized, _ = URLNormalizer.normalize(url)
        if normalized:
            urls.append(normalized)
    return urls


# ============================================================
# 统一爬虫
# ============================================================

class UnifiedAmazonCrawler:
    """统一的 Amazon 图遍历爬虫"""

    # 优先级：Seller 最高（尽快验证），Product 次之
    PRIORITY_SELLER = 0  # 最高优先级 - 尽快验证
    PRIORITY_PRODUCT = 1
    PRIORITY_STORE = 2
    PRIORITY_SEARCH = 3

    def __init__(self, start_url: str, runtime_minutes: int = 5):
        self.start_url = start_url
        self.runtime_seconds = runtime_minutes * 60
        self.start_time = None

        # URL管理
        self.url_queue = []
        self.queue_counter = 0
        self.visited = VisitedTracker()

        # 数据存储
        self.products = []
        self.discovered_seller_ids = set()

        # Seller 验证结果
        self.seller_results = {
            "verified": [],    # 可访问的 seller URLs
            "failed": [],      # 不可访问的 seller URLs
        }

        # 统计
        self.stats = {
            "products_crawled": 0,
            "sellers_verified": 0,
            "sellers_failed": 0,
            "seller_ids_discovered": 0,
            "search_queries": 0,
            "urls_discovered": 0,
            "urls_visited": 0,
        }

        # Playwright
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _get_priority(self, url: str) -> int:
        _, url_type = URLNormalizer.normalize(url)
        return {
            URLNormalizer.TYPE_PRODUCT: self.PRIORITY_PRODUCT,
            URLNormalizer.TYPE_SELLER: self.PRIORITY_SELLER,
            URLNormalizer.TYPE_STORE: self.PRIORITY_STORE,
            URLNormalizer.TYPE_SEARCH: self.PRIORITY_SEARCH,
        }.get(url_type, self.PRIORITY_SEARCH)

    def _add_to_queue(self, url: str, priority: int = None):
        normalized, url_type = URLNormalizer.normalize(url)
        if not normalized or normalized in self.visited:
            return False

        # 检查是否已在队列
        if any(item[2] == normalized for item in self.url_queue):
            return False

        if priority is None:
            priority = self._get_priority(url)

        heappush(self.url_queue, (priority, self.queue_counter, normalized))
        self.queue_counter += 1
        self.stats["urls_discovered"] += 1
        return True

    def _pop_from_queue(self) -> tuple:
        if not self.url_queue:
            return None, None
        priority, _, url = heappop(self.url_queue)
        return url, priority

    def init_browser(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        # Load cookies
        cookies_file = Path("amazon_cookies.json")
        if cookies_file.exists():
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                self.context.add_cookies([{
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.amazon.com'),
                    'path': c.get('path', '/'),
                } for c in cookies])
            print("✓ Cookies 已加载")

        self.page = self.context.new_page()
        print("✓ 浏览器初始化完成")

    def fetch_page(self, url: str) -> str:
        try:
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            self.page.wait_for_timeout(random.randint(2000, 3500))
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
            self.page.wait_for_timeout(random.randint(500, 1000))

            html = self.page.content()

            # CAPTCHA检测
            if "Robot Check" in html or "captcha" in html.lower():
                print("  🚨 CAPTCHA! 等待60秒...")
                self.page.wait_for_timeout(60000)
                html = self.page.content()
                if "Robot Check" in html:
                    return None
                # 保存cookies
                cookies = self.context.cookies()
                with open('amazon_cookies.json', 'w') as f:
                    json.dump(cookies, f, indent=2)

            return html
        except Exception as e:
            print(f"  ❌ 抓取失败: {e}")
            return None

    def should_stop(self) -> bool:
        return time.time() - self.start_time >= self.runtime_seconds

    def _try_get_other_sellers(self, html: str) -> list:
        """尝试点击 Other Sellers 获取更多卖家"""
        other_sellers = []

        try:
            # 查找并点击按钮
            btn = self.page.locator('#aod-ingress-link').first
            if btn.is_visible(timeout=2000):
                btn.click()
                self.page.wait_for_timeout(3000)

                offers_html = self.page.content()
                seller_urls = extract_seller_urls(offers_html)
                other_sellers = seller_urls

                # 关闭弹窗
                try:
                    close_btn = self.page.locator('#aod-close').first
                    if close_btn.is_visible(timeout=1000):
                        close_btn.click()
                        self.page.wait_for_timeout(500)
                except:
                    pass
        except:
            pass

        return other_sellers

    def process_url(self, url: str, priority: int):
        """处理URL - 根据类型分发"""
        normalized, url_type = URLNormalizer.normalize(url)

        if not normalized or normalized in self.visited:
            return

        elapsed = int(time.time() - self.start_time)
        print(f"\n{'='*60}")
        print(f"🔍 [{self.stats['urls_visited']+1}] {normalized}")
        print(f"   类型: {url_type} | 优先级: {priority} | ⏱️ {elapsed}s/{self.runtime_seconds}s")

        self.visited.mark_visited(normalized, url_type)
        self.stats["urls_visited"] += 1

        html = self.fetch_page(normalized)
        if not html:
            return

        if url_type == URLNormalizer.TYPE_PRODUCT:
            self._process_product(html, normalized)
        elif url_type == URLNormalizer.TYPE_SELLER:
            self._process_seller(html, normalized)
        else:
            self._process_listing(html, normalized)

    def _process_product(self, html: str, url: str):
        """处理产品页面 - 核心节点"""
        print("  📦 产品页面")

        # 1. 提取产品数据
        product = extract_product_data(html, url)
        fields = product.get("extracted_fields", {})

        if "title" in fields:
            print(f"  📝 {fields['title'][:45]}...")
        if "brand" in fields:
            print(f"  🏷️ 品牌: {fields['brand']}")

        # 保存产品
        if "asin" in fields and "title" in fields:
            self.products.append(product)
            self.stats["products_crawled"] += 1

        # 2. 提取 seller_id 并构造 Seller URL
        seller_id = fields.get("seller_id")
        if seller_id and seller_id != "ATVPDKIKX0DER":
            if seller_id not in self.discovered_seller_ids:
                self.discovered_seller_ids.add(seller_id)
                self.stats["seller_ids_discovered"] += 1
                print(f"  🏪 发现卖家: {seller_id}")

                # 构造 Seller URL 并加入队列
                seller_url = f"https://www.amazon.com/s?me={seller_id}"
                if self._add_to_queue(seller_url, self.PRIORITY_SELLER):
                    print(f"  ➕ 添加 Seller URL 到队列")

        # 3. 尝试获取 Other Sellers
        other_seller_urls = self._try_get_other_sellers(html)
        new_sellers = 0
        for seller_url in other_seller_urls:
            normalized_seller, _ = URLNormalizer.normalize(seller_url)
            if normalized_seller:
                # 提取 seller_id
                sid_match = re.search(r'me=([A-Z0-9]+)', normalized_seller)
                if sid_match:
                    sid = sid_match.group(1)
                    if sid not in self.discovered_seller_ids and sid != "ATVPDKIKX0DER":
                        self.discovered_seller_ids.add(sid)
                        self.stats["seller_ids_discovered"] += 1
                        new_sellers += 1
                        self._add_to_queue(seller_url, self.PRIORITY_SELLER)

        if new_sellers > 0:
            print(f"  ✨ 从 Other Sellers 发现 {new_sellers} 个新卖家")

        # 4. 发现新产品 URLs
        product_urls = extract_product_urls(html, url)
        added = sum(1 for u in product_urls if self._add_to_queue(u, self.PRIORITY_PRODUCT))
        if added > 0:
            print(f"  ➕ 添加 {added} 个产品 URL")

        # 5. 从品牌/类别生成搜索 URL
        keywords = extract_search_keywords(product)
        if keywords:
            search_urls = generate_search_urls(keywords)
            search_added = sum(1 for u in search_urls if self._add_to_queue(u, self.PRIORITY_SEARCH))
            if search_added > 0:
                print(f"  🔎 搜索关键词: {', '.join(keywords[:2])} (+{search_added} URL)")
                self.stats["search_queries"] += search_added

    def _process_seller(self, html: str, url: str):
        """
        处理卖家页面 - 验证可访问性，并从列表页发散产品与卖家
        """
        print("  🏪 卖家页面 (验证 + 发散)")

        # 提取 seller_id
        sid_match = re.search(r'me=([A-Z0-9]+)', url)
        seller_id = sid_match.group(1) if sid_match else "unknown"

        # 检查页面是否可访问
        is_accessible = True
        error_indicators = [
            "Something went wrong",
            "Page Not Found",
            "Sorry, we couldn't find",
            "no longer available",
        ]

        for indicator in error_indicators:
            if indicator.lower() in html.lower():
                is_accessible = False
                break

        # 提取卖家基本信息
        seller_info = {
            "seller_id": seller_id,
            "seller_url": url,
            "accessible": is_accessible,
            "timestamp": datetime.now().isoformat(),
        }

        if is_accessible:
            # 提取更多信息
            seller_data = extract_seller_data(html, seller_id, url)
            seller_info.update(seller_data.get("extracted_fields", {}))

            self.seller_results["verified"].append(seller_info)
            self.stats["sellers_verified"] += 1

            seller_name = seller_info.get("seller_name", seller_id)
            product_count = seller_info.get("product_count", "?")
            print(f"  ✅ 可访问: {seller_name} ({product_count} 产品)")

            # 从卖家 storefront 列表发散产品（与 _process_listing 一致）
            product_urls = extract_product_urls(html, url)
            p_added = sum(1 for u in product_urls if self._add_to_queue(u, self.PRIORITY_PRODUCT))
            if p_added > 0:
                print(f"  ➕ 从卖家页添加 {p_added} 个产品 URL")

            # 页面内其它卖家链接
            new_sellers = 0
            for seller_url in extract_seller_urls(html):
                normalized_seller, _ = URLNormalizer.normalize(seller_url)
                if not normalized_seller:
                    continue
                sid_m = re.search(r'me=([A-Z0-9]+)', normalized_seller)
                if not sid_m:
                    continue
                sid = sid_m.group(1)
                if sid != "ATVPDKIKX0DER" and sid not in self.discovered_seller_ids:
                    self.discovered_seller_ids.add(sid)
                    self.stats["seller_ids_discovered"] += 1
                    new_sellers += 1
                    self._add_to_queue(seller_url, self.PRIORITY_SELLER)
            if new_sellers > 0:
                print(f"  ➕ 从卖家页发现 {new_sellers} 个新卖家")
        else:
            self.seller_results["failed"].append(seller_info)
            self.stats["sellers_failed"] += 1
            print(f"  ❌ 不可访问: {seller_id}")

    def _process_listing(self, html: str, url: str):
        """处理列表页面 (Store/Search等)"""
        _, url_type = URLNormalizer.normalize(url)
        print(f"  📋 列表页面 ({url_type})")

        # 发现产品 URLs
        product_urls = extract_product_urls(html, url)
        added = sum(1 for u in product_urls if self._add_to_queue(u, self.PRIORITY_PRODUCT))
        if added > 0:
            print(f"  ➕ 添加 {added} 个产品 URL")

    def run(self):
        """运行爬虫"""
        print("=" * 60)
        print("🚀 Amazon 统一图遍历爬虫")
        print("=" * 60)
        print(f"起始URL: {self.start_url}")
        print(f"运行时长: {self.runtime_seconds // 60} 分钟")
        print("=" * 60)

        self.init_browser()
        self.start_time = time.time()

        # 添加起始URL
        self._add_to_queue(self.start_url)

        try:
            while self.url_queue and not self.should_stop():
                url, priority = self._pop_from_queue()
                if url:
                    self.process_url(url, priority)
                    time.sleep(random.uniform(1.5, 2.5))

            # 完成
            elapsed = time.time() - self.start_time
            print("\n" + "=" * 60)
            print("✅ 爬虫完成")
            print("=" * 60)
            print(f"⏱️ 运行时间: {elapsed:.1f}秒")
            print(f"\n📊 统计:")
            print(f"  - 访问URL数: {self.stats['urls_visited']}")
            print(f"  - 爬取产品数: {self.stats['products_crawled']}")
            print(f"  - 发现卖家ID数: {self.stats['seller_ids_discovered']}")
            print(f"  - 验证卖家数: {self.stats['sellers_verified']} ✅ / {self.stats['sellers_failed']} ❌")
            print(f"  - 搜索查询数: {self.stats['search_queries']}")
            print(f"  - 发现URL总数: {self.stats['urls_discovered']}")
            print(f"  - 队列剩余: {len(self.url_queue)}")

            self.save_results()

        finally:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()

    def save_results(self):
        """保存结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 产品数据
        if self.products:
            file = OUTPUT_DIR / f"unified_products_{timestamp}.json"
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(self.products, f, indent=2, ensure_ascii=False)
            print(f"\n💾 产品数据: {file}")

        # Seller 验证结果（核心输出）
        verified_count = len(self.seller_results["verified"])
        failed_count = len(self.seller_results["failed"])

        if verified_count > 0 or failed_count > 0:
            file = OUTPUT_DIR / f"unified_seller_verification_{timestamp}.json"
            data = {
                "summary": {
                    "total_discovered": len(self.discovered_seller_ids),
                    "verified_accessible": verified_count,
                    "verified_failed": failed_count,
                    "pending": len(self.discovered_seller_ids) - verified_count - failed_count,
                },
                "verified_sellers": self.seller_results["verified"],
                "failed_sellers": self.seller_results["failed"],
                "pending_seller_urls": [
                    f"https://www.amazon.com/s?me={sid}"
                    for sid in self.discovered_seller_ids
                    if sid not in [s["seller_id"] for s in self.seller_results["verified"]]
                    and sid not in [s["seller_id"] for s in self.seller_results["failed"]]
                ],
            }
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Seller验证结果: {file}")

        # 统计
        file = OUTPUT_DIR / f"unified_stats_{timestamp}.json"
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"💾 统计: {file}")


# ============================================================
# 主程序
# ============================================================

def main():
    start_url = "https://www.amazon.com/dp/B0D1XD1ZV3/"  # AirPods Pro 2

    print("\n" + "=" * 60)
    print("🎯 Amazon 统一图遍历爬虫")
    print("=" * 60)
    print("\n特性:")
    print("  ✅ Product + Seller 统一遍历")
    print("  ✅ 自动从产品发现卖家")
    print("  ✅ 自动获取 Other Sellers")
    print("  ✅ 优先级队列调度")
    print("\n" + "=" * 60 + "\n")

    crawler = UnifiedAmazonCrawler(start_url, runtime_minutes=RUNTIME_MINUTES)
    crawler.run()


if __name__ == "__main__":
    main()
