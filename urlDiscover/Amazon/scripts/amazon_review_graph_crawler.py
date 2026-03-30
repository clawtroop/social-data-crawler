# -*- coding: utf-8 -*-
"""
Amazon Review / Profile / Product 图遍历爬虫
------------------------------------------------
目标：
1. 从任意一个 product URL 出发
2. 在三类节点之间做统一图遍历：product / review / profile
3. 持续发现更多 review URL（/gp/customer-reviews/<review_id>/）
4. CAPTCHA 只做检测、暂停、人工处理后继续；不做自动绕过

节点关系（边）：
- product -> review   : 页面中出现该商品的 review 链接
- product -> profile  : 页面中出现 reviewer profile 链接
- product -> product  : 推荐/对比购/广告等区块中的其他商品链接（可间接发现更多 review）
- profile -> review   : 用户 profile 页面中出现的其他 review
- profile -> product  : 用户 profile 页面中出现的被评论商品
- review -> profile   : 单条 review 页指向作者 profile
- review -> product   : 单条 review 页指向被评论商品

环境：
    pip install playwright
    playwright install chromium

用法：
    python amazon_review_graph_crawler.py \
        --start-url "https://www.amazon.com/dp/B0D1XD1ZV3/" \
        --runtime-minutes 10
"""

import sys
import io
import re
import time
import json
import html as ihtml
import random
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from heapq import heappush, heappop

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ============================================================
# 配置
# ============================================================

random.seed(42)

OUTPUT_DIR = Path("amazon_review_graph_output")
OUTPUT_DIR.mkdir(exist_ok=True)

COOKIES_FILE = Path("amazon_cookies.json")
CAPTCHA_WAIT_SECONDS = 60
DEFAULT_RUNTIME_MINUTES = 5

# ============================================================
# URL 规范化
# ============================================================

class URLNormalizer:
    TYPE_PRODUCT = "product"
    TYPE_REVIEW = "review"
    TYPE_PROFILE = "profile"
    TYPE_OTHER = "other"

    AMAZON_HOST = "https://www.amazon.com"

    @staticmethod
    def normalize(url: str):
        if not url:
            return None, None

        url = ihtml.unescape(url.strip())

        if url.startswith("/"):
            url = URLNormalizer.AMAZON_HOST + url

        parsed = urlparse(url)
        if not parsed.scheme:
            return None, None

        # 仅保留 amazon.com 域名
        if parsed.netloc and "amazon.com" not in parsed.netloc:
            return None, None

        # Product
        asin_match = re.search(r'(?:/dp/|/gp/product/)([A-Z0-9]{10})', url, re.IGNORECASE)
        if asin_match:
            asin = asin_match.group(1).upper()
            return f"{URLNormalizer.AMAZON_HOST}/dp/{asin}/", URLNormalizer.TYPE_PRODUCT

        # Review
        review_match = re.search(r'/gp/customer-reviews/([A-Z0-9]{10,32})', url, re.IGNORECASE)
        if review_match:
            review_id = review_match.group(1).upper()
            return f"{URLNormalizer.AMAZON_HOST}/gp/customer-reviews/{review_id}/", URLNormalizer.TYPE_REVIEW

        # Profile
        profile_match = re.search(r'/gp/profile/([A-Za-z0-9._-]+)', url)
        if profile_match:
            profile_id = profile_match.group(1)
            return f"{URLNormalizer.AMAZON_HOST}/gp/profile/{profile_id}/", URLNormalizer.TYPE_PROFILE

        return None, URLNormalizer.TYPE_OTHER


class VisitedTracker:
    """visited 仅存规范化 URL，且仅在对应页面成功抓取并处理完成后写入。"""

    def __init__(self):
        self.visited = set()
        self.info = {}

    def is_visited(self, url: str) -> bool:
        canonical, _ = URLNormalizer.normalize(url)
        return canonical in self.visited if canonical else True

    def mark_visited(self, url: str, url_type: str = None):
        canonical, detected_type = URLNormalizer.normalize(url)
        if canonical:
            self.visited.add(canonical)
            self.info[canonical] = {
                "type": url_type or detected_type,
                "time": datetime.now().isoformat()
            }
        return canonical

    def __contains__(self, url):
        return self.is_visited(url)

    def __len__(self):
        return len(self.visited)


# ============================================================
# 通用提取辅助
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = ihtml.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_urls_by_regex(html: str, base_url: str, patterns):
    urls = set()
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            href = match.group(1)
            href = ihtml.unescape(href)
            url = urljoin(base_url, href)
            normalized, _ = URLNormalizer.normalize(url)
            if normalized:
                urls.add(normalized)
    return list(urls)


def extract_review_urls(html: str, base_url: str):
    patterns = [
        r'href="([^"]*/gp/customer-reviews/[A-Z0-9]{10,32}[^"]*)"',
        r"href='([^']*/gp/customer-reviews/[A-Z0-9]{10,32}[^']*)'",
        r'href="([^"]*//(?:www\.)?amazon\.com/gp/customer-reviews/[A-Z0-9]{10,32}[^"]*)"',
        r"href='([^']*//(?:www\.)?amazon\.com/gp/customer-reviews/[A-Z0-9]{10,32}[^']*)'",
        r'https://www\.amazon\.com/gp/customer-reviews/([A-Z0-9]{10,32})/?',
        r'//www\.amazon\.com/gp/customer-reviews/([A-Z0-9]{10,32})/?',
    ]
    urls = set()

    # href (double/single quoted + protocol-relative)
    urls.update(extract_urls_by_regex(html, base_url, patterns[:4]))

    # raw full URL / raw review id
    for rid in re.findall(patterns[4], html, re.IGNORECASE):
        normalized, _ = URLNormalizer.normalize(
            f"https://www.amazon.com/gp/customer-reviews/{rid}/"
        )
        if normalized:
            urls.add(normalized)
    for rid in re.findall(patterns[5], html, re.IGNORECASE):
        normalized, _ = URLNormalizer.normalize(
            f"https://www.amazon.com/gp/customer-reviews/{rid}/"
        )
        if normalized:
            urls.add(normalized)

    return list(urls)


def extract_profile_urls(html: str, base_url: str):
    patterns = [
        r'href="([^"]*/gp/profile/[A-Za-z0-9._-]+[^"]*)"',
        r"href='([^']*/gp/profile/[A-Za-z0-9._-]+[^']*)'",
        r'href="([^"]*//(?:www\.)?amazon\.com/gp/profile/[A-Za-z0-9._-]+[^"]*)"',
        r"href='([^']*//(?:www\.)?amazon\.com/gp/profile/[A-Za-z0-9._-]+[^']*)'",
        r'https://www\.amazon\.com/gp/profile/([A-Za-z0-9._-]+)/?',
        r'//www\.amazon\.com/gp/profile/([A-Za-z0-9._-]+)/?',
    ]
    urls = set()

    urls.update(extract_urls_by_regex(html, base_url, patterns[:4]))

    for pid in re.findall(patterns[4], html, re.IGNORECASE):
        normalized, _ = URLNormalizer.normalize(
            f"https://www.amazon.com/gp/profile/{pid}/"
        )
        if normalized:
            urls.add(normalized)
    for pid in re.findall(patterns[5], html, re.IGNORECASE):
        normalized, _ = URLNormalizer.normalize(
            f"https://www.amazon.com/gp/profile/{pid}/"
        )
        if normalized:
            urls.add(normalized)

    return list(urls)


def extract_product_urls(html: str, base_url: str):
    urls = set()

    # href links
    for match in re.finditer(r'href="([^"]*?(?:/dp/|/gp/product/)[A-Z0-9]{10}[^"]*)"', html, re.IGNORECASE):
        url = urljoin(base_url, ihtml.unescape(match.group(1)))
        normalized, url_type = URLNormalizer.normalize(url)
        if normalized and url_type == URLNormalizer.TYPE_PRODUCT:
            urls.add(normalized)

    # data-asin / JSON asin
    for asin in re.findall(r'data-asin="([A-Z0-9]{10})"', html, re.IGNORECASE):
        urls.add(f"https://www.amazon.com/dp/{asin.upper()}/")

    for asin in re.findall(r'"asin"\s*:\s*"([A-Z0-9]{10})"', html, re.IGNORECASE):
        urls.add(f"https://www.amazon.com/dp/{asin.upper()}/")

    return list(urls)


# ============================================================
# 数据提取
# ============================================================

def extract_product_data(html: str, url: str):
    normalized, _ = URLNormalizer.normalize(url)
    data = {
        "url": normalized,
        "timestamp": datetime.now().isoformat(),
        "extracted_fields": {}
    }

    asin_match = re.search(r'/dp/([A-Z0-9]{10})', normalized or "", re.IGNORECASE)
    if asin_match:
        data["extracted_fields"]["asin"] = asin_match.group(1).upper()

    title_patterns = [
        r'<span id="productTitle"[^>]*>\s*(.*?)\s*</span>',
        r'<title>\s*(.*?)\s*</title>',
        r'"title"\s*:\s*"([^"]+)"',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            title = clean_text(match.group(1))
            if title and len(title) > 3:
                data["extracted_fields"]["title"] = title
                break

    return data


def extract_profile_data(html: str, url: str):
    normalized, _ = URLNormalizer.normalize(url)
    data = {
        "url": normalized,
        "timestamp": datetime.now().isoformat(),
        "extracted_fields": {}
    }

    pid_match = re.search(r'/gp/profile/([A-Za-z0-9._-]+)', normalized or "")
    if pid_match:
        data["extracted_fields"]["profile_id"] = pid_match.group(1)

    name_patterns = [
        r'<title>\s*Amazon\.com:\s*Profile for\s*(.*?)\s*</title>',
        r'<title>\s*Profile for\s*(.*?)\s*</title>',
        r'profile-name[^>]*>\s*(.*?)\s*<',
        r'public-name[^>]*>\s*(.*?)\s*<',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            username = clean_text(match.group(1))
            if username and len(username) <= 100:
                data["extracted_fields"]["username"] = username
                break

    # 粗粒度统计，存在就记
    review_count_match = re.search(r'([0-9,]+)\s+reviews?', html, re.IGNORECASE)
    if review_count_match:
        data["extracted_fields"]["review_count_text"] = review_count_match.group(1).replace(",", "")

    return data


def extract_review_data(html: str, url: str):
    normalized, _ = URLNormalizer.normalize(url)
    data = {
        "url": normalized,
        "timestamp": datetime.now().isoformat(),
        "extracted_fields": {}
    }

    rid_match = re.search(r'/gp/customer-reviews/([A-Z0-9]{10,32})', normalized or "", re.IGNORECASE)
    if rid_match:
        data["extracted_fields"]["review_id"] = rid_match.group(1).upper()

    title_patterns = [
        r'data-hook="review-title"[^>]*>\s*(.*?)\s*</',
        r'<title>\s*(.*?)\s*</title>',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            title = clean_text(match.group(1))
            if title and len(title) > 1:
                data["extracted_fields"]["review_title"] = title
                break

    rating_patterns = [
        r'([1-5](?:\.[0-9])?)\s*out of 5 stars',
        r'([1-5](?:\.[0-9])?)\s*stars',
    ]
    for pattern in rating_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            data["extracted_fields"]["rating"] = match.group(1)
            break

    date_match = re.search(r'Reviewed in .*? on ([A-Za-z]+ \d{1,2}, \d{4})', html, re.IGNORECASE)
    if date_match:
        data["extracted_fields"]["review_date"] = date_match.group(1)

    helpful_patterns = [
        r'([0-9,]+)\s+people found this helpful',
        r'One person found this helpful',
    ]
    for pattern in helpful_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            if "One person" in match.group(0):
                data["extracted_fields"]["helpful_votes"] = "1"
            else:
                data["extracted_fields"]["helpful_votes"] = match.group(1).replace(",", "")
            break

    # 从 review 页反推 profile / product
    profile_urls = extract_profile_urls(html, normalized or url)
    if profile_urls:
        profile_url = profile_urls[0]
        data["extracted_fields"]["profile_url"] = profile_url
        pid_match = re.search(r'/gp/profile/([A-Za-z0-9._-]+)', profile_url)
        if pid_match:
            data["extracted_fields"]["profile_id"] = pid_match.group(1)

    product_urls = extract_product_urls(html, normalized or url)
    if product_urls:
        product_url = product_urls[0]
        data["extracted_fields"]["product_url"] = product_url
        asin_match = re.search(r'/dp/([A-Z0-9]{10})', product_url, re.IGNORECASE)
        if asin_match:
            data["extracted_fields"]["asin"] = asin_match.group(1).upper()

    return data


# ============================================================
# 统一爬虫
# ============================================================

class AmazonReviewGraphCrawler:
    PRIORITY_PRODUCT = 1
    PRIORITY_PROFILE = 2
    PRIORITY_REVIEW = 0

    def __init__(self, start_url: str, runtime_minutes: int = DEFAULT_RUNTIME_MINUTES):
        self.start_url = start_url
        self.runtime_seconds = runtime_minutes * 60
        self.start_time = None

        # 队列：堆中存原始 URL；queued_canonical 仅存规范化键，用于与 visited 去重（未处理前不入 visited）
        self.url_queue = []
        self.queued_canonical = set()
        self.queue_counter = 0
        self.visited = VisitedTracker()

        # 数据
        self.products = {}
        self.profiles = {}
        self.reviews = {}
        self.edges = []
        self.edge_keys = set()

        # 统计
        self.stats = {
            "products_crawled": 0,
            "profiles_crawled": 0,
            "reviews_crawled": 0,
            "urls_discovered": 0,
            "urls_visited": 0,
            "captcha_hits": 0,
            "fetch_failures": 0,
        }

        # Playwright
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    # ---------------- URL & Queue ----------------

    def _get_priority(self, url: str) -> int:
        _, url_type = URLNormalizer.normalize(url)
        return {
            URLNormalizer.TYPE_PRODUCT: self.PRIORITY_PRODUCT,
            URLNormalizer.TYPE_PROFILE: self.PRIORITY_PROFILE,
            URLNormalizer.TYPE_REVIEW: self.PRIORITY_REVIEW,
        }.get(url_type, self.PRIORITY_REVIEW)

    def _add_to_queue(self, url: str, priority: int = None) -> bool:
        """入队 url 保持调用方传入的原始字符串；仅用规范化键与 visited / 已在队列比较。"""
        canonical, url_type = URLNormalizer.normalize(url)
        if not canonical:
            return False
        if canonical in self.visited:
            return False
        if canonical in self.queued_canonical:
            return False

        if priority is None:
            priority = self._get_priority(url)

        heappush(self.url_queue, (priority, self.queue_counter, url))
        self.queue_counter += 1
        self.queued_canonical.add(canonical)
        self.stats["urls_discovered"] += 1
        return True

    def _pop_from_queue(self):
        if not self.url_queue:
            return None, None
        priority, _, url = heappop(self.url_queue)
        canonical, _ = URLNormalizer.normalize(url)
        if canonical:
            self.queued_canonical.discard(canonical)
        return url, priority

    def _add_edge(self, src: str, src_type: str, dst: str, dst_type: str, relation: str):
        key = (src, src_type, dst, dst_type, relation)
        if key in self.edge_keys:
            return
        self.edge_keys.add(key)
        self.edges.append({
            "src": src,
            "src_type": src_type,
            "dst": dst,
            "dst_type": dst_type,
            "relation": relation,
            "timestamp": datetime.now().isoformat(),
        })

    # ---------------- Browser ----------------

    def init_browser(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()

        # 给爬虫单独一个本地浏览器目录，不要复用你日常 Chrome 的默认目录
        user_data_dir = str(Path("amazon_playwright_profile").resolve())
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        # 持久化上下文：cookies / localStorage / 登录态都会自动保留
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1400, "height": 900},
        )

        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = self.context.new_page()

        print(f"✓ 持久化浏览器初始化完成: {user_data_dir}")

    def _save_cookies(self):
        try:
            cookies = self.context.cookies()
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            print("✓ cookies 已保存")
        except Exception as e:
            print(f"⚠️ cookies 保存失败: {e}")

    @staticmethod
    def _is_captcha_page(html: str) -> bool:
        lower = (html or "").lower()
        indicators = [
            "robot check",
            "enter the characters you see below",
            "captcha",
        ]
        return any(indicator in lower for indicator in indicators)

    @staticmethod
    def _asin_from_product_url(url: str):
        m = re.search(r"(?:/dp/|/gp/product/)([A-Z0-9]{10})", url or "", re.IGNORECASE)
        return m.group(1).upper() if m else None

    def _resolve_captcha_if_needed(self, html: str):
        """若当前 page 为 CAPTCHA，等待/人工处理；成功返回最新 html，失败返回 None。"""
        if not self._is_captcha_page(html):
            return html
        self.stats["captcha_hits"] += 1
        print(f"  🚨 检测到 CAPTCHA，先等待 {CAPTCHA_WAIT_SECONDS} 秒...")
        self.page.wait_for_timeout(CAPTCHA_WAIT_SECONDS * 1000)
        html = self.page.content()
        if self._is_captcha_page(html):
            try:
                input("  请在浏览器中手动完成验证，完成后按 Enter 继续...")
            except EOFError:
                print("  ⚠️ 当前环境不支持交互输入，跳过该页面。")
                return None
            html = self.page.content()
        if self._is_captcha_page(html):
            print("  ❌ CAPTCHA 仍未解除，放弃本页")
            return None
        self._save_cookies()
        return html

    def _prime_product_page_reviews(self):
        """滚动到评论区并短暂等待，促使懒加载的 review / profile 链接进入 DOM。"""
        selectors = [
            "#reviewsMedleyFooter",
            '[data-hook="reviews-medley-widget"]',
            "#customer-reviews_feature_div",
            "#reviews-medley-sidebar",
            "#cm-cr-dp-widget",
            "#cr-medley-topCardType",
        ]
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="attached", timeout=4000)
                loc.scroll_into_view_if_needed(timeout=8000)
                break
            except Exception:
                continue
        try:
            self.page.locator('a[href*="customer-reviews"]').first.wait_for(
                state="visible", timeout=15000
            )
        except Exception:
            pass
        for _ in range(5):
            self.page.evaluate("window.scrollBy(0, 650)")
            self.page.wait_for_timeout(random.randint(400, 800))

    def _fetch_product_reviews_list_html(self, product_url: str) -> str:
        """打开 /product-reviews/{ASIN}/ 列表页，补充单条 review 链接（详情页常不含于首屏 HTML）。"""
        asin = self._asin_from_product_url(product_url)
        if not asin:
            return ""
        rv_url = (
            f"https://www.amazon.com/product-reviews/{asin}/"
            f"?ie=UTF8&reviewerType=all_reviews&pageNumber=1"
        )
        try:
            self.page.goto(rv_url, wait_until="domcontentloaded", timeout=35000)
            self.page.wait_for_timeout(random.randint(2000, 4000))
            for _ in range(6):
                self.page.evaluate("window.scrollBy(0, 700)")
                self.page.wait_for_timeout(random.randint(450, 900))
            try:
                self.page.locator('a[href*="customer-reviews"]').first.wait_for(
                    state="visible", timeout=12000
                )
            except Exception:
                pass
            html = self.page.content()
            html = self._resolve_captcha_if_needed(html)
            if html is None:
                return ""
            if self._is_captcha_page(html):
                return ""
            return html
        except Exception as e:
            print(f"  ⚠️ 抓取 product-reviews 列表页失败: {e}")
            return ""

    def fetch_page(self, url: str, url_type: str = None):
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(random.randint(2000, 3500))

            if url_type == URLNormalizer.TYPE_PRODUCT:
                self._prime_product_page_reviews()
            else:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
                self.page.wait_for_timeout(random.randint(500, 1000))

            html = self.page.content()

            # CAPTCHA：只检测与暂停，不做自动绕过
            html = self._resolve_captcha_if_needed(html)
            if html is None:
                return None

            if url_type == URLNormalizer.TYPE_PRODUCT:
                extra = self._fetch_product_reviews_list_html(url)
                if extra:
                    html = html + "\n<!--amazon_review_graph:product-reviews-merge-->\n" + extra

            return html

        except Exception as e:
            print(f"  ❌ 抓取失败: {e}")
            self.stats["fetch_failures"] += 1
            return None

    # ---------------- Traverse ----------------

    def should_stop(self) -> bool:
        return time.time() - self.start_time >= self.runtime_seconds

    def process_url(self, url: str, priority: int):
        canonical, url_type = URLNormalizer.normalize(url)
        if not canonical or canonical in self.visited:
            return

        elapsed = int(time.time() - self.start_time)
        print("\n" + "=" * 70)
        print(f"🔍 [{self.stats['urls_visited'] + 1}] {canonical}")
        if url != canonical:
            print(f"   原始队列 URL: {url[:120]}{'…' if len(url) > 120 else ''}")
        print(f"   类型: {url_type} | 优先级: {priority} | ⏱️ {elapsed}s/{self.runtime_seconds}s")

        # 导航与合并页逻辑使用稳定规范化 URL；成功抓取并解析后再写入 visited
        html = self.fetch_page(canonical, url_type)
        if not html:
            return

        self.visited.mark_visited(canonical, url_type)
        self.stats["urls_visited"] += 1

        if url_type == URLNormalizer.TYPE_PRODUCT:
            self._process_product(html, canonical)
        elif url_type == URLNormalizer.TYPE_PROFILE:
            self._process_profile(html, canonical)
        elif url_type == URLNormalizer.TYPE_REVIEW:
            self._process_review(html, canonical)

    # ---------------- Node processors ----------------

    def _process_product(self, html: str, url: str):
        print("  📦 Product 页面")

        product = extract_product_data(html, url)
        self.products[url] = product
        self.stats["products_crawled"] = len(self.products)

        fields = product["extracted_fields"]
        if "asin" in fields:
            print(f"  ASIN: {fields['asin']}")
        if "title" in fields:
            print(f"  标题: {fields['title'][:70]}")

        # 1) Product -> Review
        review_urls = extract_review_urls(html, url)
        added_reviews = 0
        for review_url in review_urls:
            self._add_edge(url, URLNormalizer.TYPE_PRODUCT, review_url, URLNormalizer.TYPE_REVIEW, "contains_review")
            if self._add_to_queue(review_url, self.PRIORITY_REVIEW):
                added_reviews += 1

        # 2) Product -> Profile
        profile_urls = extract_profile_urls(html, url)
        added_profiles = 0
        for profile_url in profile_urls:
            self._add_edge(url, URLNormalizer.TYPE_PRODUCT, profile_url, URLNormalizer.TYPE_PROFILE, "mentions_profile")
            if self._add_to_queue(profile_url, self.PRIORITY_PROFILE):
                added_profiles += 1

        # 3) Product -> Product（推荐位、对比、广告等，扩大商品覆盖面以发现评论）
        product_urls = extract_product_urls(html, url)
        added_products = 0
        for product_url in product_urls:
            other, _ = URLNormalizer.normalize(product_url)
            if not other or other == url:
                continue
            self._add_edge(
                url,
                URLNormalizer.TYPE_PRODUCT,
                product_url,
                URLNormalizer.TYPE_PRODUCT,
                "related_or_carousel_product",
            )
            if self._add_to_queue(product_url, self.PRIORITY_PRODUCT):
                added_products += 1

        print(f"  ➕ 新 review URL: {added_reviews}")
        print(f"  ➕ 新 profile URL: {added_profiles}")
        print(f"  ➕ 新 product URL（跨商品）: {added_products}")

    def _process_profile(self, html: str, url: str):
        print("  👤 Profile 页面")

        profile = extract_profile_data(html, url)
        self.profiles[url] = profile
        self.stats["profiles_crawled"] = len(self.profiles)

        fields = profile["extracted_fields"]
        if "profile_id" in fields:
            print(f"  Profile ID: {fields['profile_id']}")
        if "username" in fields:
            print(f"  用户名: {fields['username']}")

        # 1) Profile -> Review
        review_urls = extract_review_urls(html, url)
        added_reviews = 0
        for review_url in review_urls:
            self._add_edge(url, URLNormalizer.TYPE_PROFILE, review_url, URLNormalizer.TYPE_REVIEW, "has_review")
            if self._add_to_queue(review_url, self.PRIORITY_REVIEW):
                added_reviews += 1

        # 2) Profile -> Product
        product_urls = extract_product_urls(html, url)
        added_products = 0
        for product_url in product_urls:
            self._add_edge(url, URLNormalizer.TYPE_PROFILE, product_url, URLNormalizer.TYPE_PRODUCT, "reviewed_product")
            if self._add_to_queue(product_url, self.PRIORITY_PRODUCT):
                added_products += 1

        print(f"  ➕ 新 review URL: {added_reviews}")
        print(f"  ➕ 新 product URL: {added_products}")

    def _process_review(self, html: str, url: str):
        print("  📝 Review 页面")

        review = extract_review_data(html, url)
        self.reviews[url] = review
        self.stats["reviews_crawled"] = len(self.reviews)

        fields = review["extracted_fields"]
        if "review_id" in fields:
            print(f"  Review ID: {fields['review_id']}")
        if "review_title" in fields:
            print(f"  标题: {fields['review_title'][:70]}")
        if "rating" in fields:
            print(f"  评分: {fields['rating']}")

        # Review -> Profile
        profile_url = fields.get("profile_url")
        if profile_url:
            self._add_edge(url, URLNormalizer.TYPE_REVIEW, profile_url, URLNormalizer.TYPE_PROFILE, "authored_by")
            self._add_to_queue(profile_url, self.PRIORITY_PROFILE)

        # Review -> Product
        product_url = fields.get("product_url")
        if product_url:
            self._add_edge(url, URLNormalizer.TYPE_REVIEW, product_url, URLNormalizer.TYPE_PRODUCT, "belongs_to_product")
            self._add_to_queue(product_url, self.PRIORITY_PRODUCT)

        # 保守补充：直接扫描页面中的 review/profile/product 链接
        extra_reviews = 0
        for review_url in extract_review_urls(html, url):
            if review_url != url:
                self._add_edge(url, URLNormalizer.TYPE_REVIEW, review_url, URLNormalizer.TYPE_REVIEW, "references_review")
                if self._add_to_queue(review_url, self.PRIORITY_REVIEW):
                    extra_reviews += 1

        extra_profiles = 0
        for profile_url in extract_profile_urls(html, url):
            self._add_edge(url, URLNormalizer.TYPE_REVIEW, profile_url, URLNormalizer.TYPE_PROFILE, "references_profile")
            if self._add_to_queue(profile_url, self.PRIORITY_PROFILE):
                extra_profiles += 1

        extra_products = 0
        for product_url in extract_product_urls(html, url):
            self._add_edge(url, URLNormalizer.TYPE_REVIEW, product_url, URLNormalizer.TYPE_PRODUCT, "references_product")
            if self._add_to_queue(product_url, self.PRIORITY_PRODUCT):
                extra_products += 1

        if extra_reviews or extra_profiles or extra_products:
            print(f"  ➕ 扫描补充: review={extra_reviews}, profile={extra_profiles}, product={extra_products}")

    # ---------------- Run & Save ----------------

    def run(self):
        print("=" * 70)
        print("🚀 Amazon Review 图遍历爬虫")
        print("=" * 70)
        print(f"起始 URL: {self.start_url}")
        print(f"运行时长: {self.runtime_seconds // 60} 分钟")
        print("=" * 70)

        self.init_browser()
        self.start_time = time.time()

        self._add_to_queue(self.start_url)

        try:
            while self.url_queue and not self.should_stop():
                url, priority = self._pop_from_queue()
                if url:
                    self.process_url(url, priority)
                    time.sleep(random.uniform(1.5, 2.5))

            elapsed = time.time() - self.start_time
            print("\n" + "=" * 70)
            print("✅ 爬虫完成")
            print("=" * 70)
            print(f"⏱️ 运行时间: {elapsed:.1f}s")
            print("📊 统计:")
            for k, v in self.stats.items():
                print(f"  - {k}: {v}")
            print(f"  - queue_remaining: {len(self.url_queue)}")
            print(f"  - unique_products: {len(self.products)}")
            print(f"  - unique_profiles: {len(self.profiles)}")
            print(f"  - unique_reviews: {len(self.reviews)}")
            print(f"  - unique_edges: {len(self.edges)}")

            self.save_results()

        finally:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()

    def save_results(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        graph_file = OUTPUT_DIR / f"review_graph_{timestamp}.json"
        graph_data = {
            "summary": {
                "products": len(self.products),
                "profiles": len(self.profiles),
                "reviews": len(self.reviews),
                "edges": len(self.edges),
                "visited_urls": len(self.visited),
            },
            "products": list(self.products.values()),
            "profiles": list(self.profiles.values()),
            "reviews": list(self.reviews.values()),
            "edges": self.edges,
            "pending_urls": [item[2] for item in sorted(self.url_queue)],
        }
        with open(graph_file, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        print(f"💾 图数据: {graph_file}")

        review_urls_file = OUTPUT_DIR / f"review_urls_{timestamp}.txt"
        with open(review_urls_file, "w", encoding="utf-8") as f:
            for url in sorted(self.reviews.keys()):
                f.write(url + "\n")
        print(f"💾 review URL 列表: {review_urls_file}")

        stats_file = OUTPUT_DIR / f"stats_{timestamp}.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        print(f"💾 统计: {stats_file}")


# ============================================================
# 主程序
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Amazon review/profile/product 图遍历爬虫")
    parser.add_argument(
        "--start-url",
        required=True,
        help="任意一个 Amazon product URL，例如 https://www.amazon.com/dp/B0D1XD1ZV3/"
    )
    parser.add_argument(
        "--runtime-minutes",
        type=int,
        default=DEFAULT_RUNTIME_MINUTES,
        help=f"运行时长（分钟），默认 {DEFAULT_RUNTIME_MINUTES}"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    start_raw = (args.start_url or "").strip()
    normalized, url_type = URLNormalizer.normalize(start_raw)
    if not normalized or url_type != URLNormalizer.TYPE_PRODUCT:
        raise ValueError("start-url 必须是一个可规范化的 Amazon product URL")

    crawler = AmazonReviewGraphCrawler(
        start_url=start_raw,
        runtime_minutes=args.runtime_minutes
    )
    crawler.run()


if __name__ == "__main__":
    main()
