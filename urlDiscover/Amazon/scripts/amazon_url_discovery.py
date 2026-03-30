# -*- coding: utf-8 -*-
"""
Amazon Products URL 发现器

目标: 发现尽可能多的 Amazon 产品页面 URL
URL 格式: amazon.com/dp/{ASIN}
ASIN: 10位字母数字标识符

发现策略:
1. 搜索引擎发现种子 URL
2. 从产品页面的关联区域发现更多 URL
3. BFS 递归扩展
"""

import re
import time
import json
import random
from collections import deque
from typing import List, Set, Dict, Optional
from urllib.parse import quote, urljoin, urlparse
from dataclasses import dataclass, field
from datetime import datetime

# 尝试导入 requests，如果没有则提示安装
try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    exit(1)


# ============================================================
# 配置
# ============================================================

@dataclass
class DiscoveryConfig:
    """发现器配置"""
    # 搜索配置
    seed_keywords: List[str] = field(default_factory=lambda: [
        "headphones",
        "laptop",
        "keyboard",
        "mouse",
        "monitor",
        "smartphone",
        "tablet",
        "camera",
        "speaker",
        "smartwatch",
        "earbuds",
        "charger",
        "cable",
        "case",
        "stand",
    ])

    # 品牌关键词 (从 Sample 中的 competitive_position 等字段获取灵感)
    brand_keywords: List[str] = field(default_factory=lambda: [
        "Sony",
        "Apple",
        "Samsung",
        "Bose",
        "Logitech",
        "Anker",
        "JBL",
        "Dell",
        "HP",
        "Lenovo",
    ])

    # 爬取限制
    max_urls: int = 10000           # 最大发现 URL 数量
    max_depth: int = 3              # 最大遍历深度
    max_seeds_per_keyword: int = 20 # 每个关键词的种子数量

    # 请求配置
    request_delay: float = 1.0      # 请求间隔 (秒)
    request_timeout: int = 30       # 请求超时 (秒)
    max_retries: int = 3            # 最大重试次数

    # 输出配置
    output_file: str = "amazon_product_urls.txt"
    checkpoint_file: str = "amazon_discovery_checkpoint.json"
    checkpoint_interval: int = 100  # 每发现 N 个 URL 保存一次检查点


# ============================================================
# Amazon URL 工具
# ============================================================

class AmazonURLUtils:
    """Amazon URL 相关工具"""

    # ASIN 正则: 10位字母数字
    ASIN_PATTERN = re.compile(r'\b([A-Z0-9]{10})\b')

    # 产品 URL 正则模式
    PRODUCT_URL_PATTERNS = [
        re.compile(r'amazon\.com/dp/([A-Z0-9]{10})', re.IGNORECASE),
        re.compile(r'amazon\.com/gp/product/([A-Z0-9]{10})', re.IGNORECASE),
        re.compile(r'amazon\.com/[^/]+/dp/([A-Z0-9]{10})', re.IGNORECASE),
        re.compile(r'amazon\.com/exec/obidos/ASIN/([A-Z0-9]{10})', re.IGNORECASE),
    ]

    # data-asin 属性模式
    DATA_ASIN_PATTERN = re.compile(r'data-asin=["\']([A-Z0-9]{10})["\']', re.IGNORECASE)

    @classmethod
    def extract_asin(cls, url: str) -> Optional[str]:
        """从 URL 中提取 ASIN"""
        for pattern in cls.PRODUCT_URL_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1).upper()
        return None

    @classmethod
    def build_product_url(cls, asin: str) -> str:
        """构建标准产品 URL"""
        return f"https://www.amazon.com/dp/{asin.upper()}"

    @classmethod
    def is_valid_asin(cls, asin: str) -> bool:
        """检查是否是有效的 ASIN"""
        if not asin or len(asin) != 10:
            return False
        return bool(re.match(r'^[A-Z0-9]{10}$', asin.upper()))

    @classmethod
    def extract_asins_from_html(cls, html: str) -> Set[str]:
        """从 HTML 中提取所有 ASIN"""
        asins = set()

        # 从 URL 中提取
        for pattern in cls.PRODUCT_URL_PATTERNS:
            for match in pattern.finditer(html):
                asins.add(match.group(1).upper())

        # 从 data-asin 属性提取
        for match in cls.DATA_ASIN_PATTERN.finditer(html):
            asins.add(match.group(1).upper())

        # 过滤无效的
        return {asin for asin in asins if cls.is_valid_asin(asin)}


# ============================================================
# HTTP 请求器
# ============================================================

class HTTPFetcher:
    """HTTP 请求器，带重试和限流"""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.session = requests.Session()
        self.last_request_time = 0

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _rate_limit(self):
        """限流"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.config.request_delay:
            time.sleep(self.config.request_delay - elapsed)
        self.last_request_time = time.time()

    def fetch(self, url: str) -> Optional[str]:
        """抓取 URL 内容"""
        self._rate_limit()

        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=self.config.request_timeout,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 503:
                    # Amazon 反爬，等待后重试
                    wait_time = (attempt + 1) * 5
                    print(f"  [503] 被限流，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                elif response.status_code == 404:
                    return None  # 页面不存在，不重试
                else:
                    print(f"  [HTTP {response.status_code}] {url[:50]}...")

            except requests.Timeout:
                print(f"  [超时] {url[:50]}...")
            except requests.RequestException as e:
                print(f"  [错误] {url[:50]}... - {e}")

            if attempt < self.config.max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避

        return None


# ============================================================
# 搜索引擎种子发现
# ============================================================

class SeedDiscoverer:
    """通过搜索引擎发现种子 URL"""

    def __init__(self, fetcher: HTTPFetcher, config: DiscoveryConfig):
        self.fetcher = fetcher
        self.config = config

    def discover_seeds(self) -> Set[str]:
        """发现种子 ASIN"""
        all_asins = set()

        # 1. 类目关键词搜索
        print("\n[种子发现] 类目关键词搜索...")
        for keyword in self.config.seed_keywords:
            asins = self._search_amazon(keyword)
            print(f"  '{keyword}' -> {len(asins)} 个 ASIN")
            all_asins.update(asins)

        # 2. 品牌关键词搜索
        print("\n[种子发现] 品牌关键词搜索...")
        for brand in self.config.brand_keywords:
            asins = self._search_amazon(brand)
            print(f"  '{brand}' -> {len(asins)} 个 ASIN")
            all_asins.update(asins)

        # 3. Best Sellers 页面
        print("\n[种子发现] Best Sellers 页面...")
        bestseller_asins = self._discover_from_bestsellers()
        print(f"  Best Sellers -> {len(bestseller_asins)} 个 ASIN")
        all_asins.update(bestseller_asins)

        print(f"\n[种子发现] 共发现 {len(all_asins)} 个种子 ASIN")
        return all_asins

    def _search_amazon(self, keyword: str) -> Set[str]:
        """在 Amazon 搜索页面发现 ASIN"""
        asins = set()

        # Amazon 搜索 URL
        search_url = f"https://www.amazon.com/s?k={quote(keyword)}"

        html = self.fetcher.fetch(search_url)
        if html:
            asins = AmazonURLUtils.extract_asins_from_html(html)

        return asins

    def _discover_from_bestsellers(self) -> Set[str]:
        """从 Best Sellers 页面发现 ASIN"""
        asins = set()

        bestseller_categories = [
            "electronics",
            "computers",
            "home-garden",
            "sports-outdoors",
            "toys-games",
        ]

        for category in bestseller_categories[:3]:  # 限制数量
            url = f"https://www.amazon.com/Best-Sellers/zgbs/{category}"
            html = self.fetcher.fetch(url)
            if html:
                found = AmazonURLUtils.extract_asins_from_html(html)
                asins.update(found)

        return asins


# ============================================================
# 页面扩展器
# ============================================================

class PageExpander:
    """从产品页面发现更多 ASIN"""

    def __init__(self, fetcher: HTTPFetcher):
        self.fetcher = fetcher

    def expand(self, asin: str) -> Set[str]:
        """
        从产品页面发现关联的 ASIN

        发现来源:
        - Frequently bought together
        - Customers who viewed this also viewed
        - Compare with similar items
        - Sponsored products
        - 品牌店铺链接
        """
        url = AmazonURLUtils.build_product_url(asin)
        html = self.fetcher.fetch(url)

        if not html:
            return set()

        # 提取所有 ASIN
        found_asins = AmazonURLUtils.extract_asins_from_html(html)

        # 排除自己
        found_asins.discard(asin.upper())

        return found_asins


# ============================================================
# BFS 爬虫控制器
# ============================================================

class CrawlController:
    """BFS 爬虫控制器"""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.fetcher = HTTPFetcher(config)
        self.seed_discoverer = SeedDiscoverer(self.fetcher, config)
        self.page_expander = PageExpander(self.fetcher)

        # 状态
        self.discovered_asins: Set[str] = set()
        self.visited_asins: Set[str] = set()
        self.queue: deque = deque()  # (asin, depth)

        # 统计
        self.stats = {
            "start_time": None,
            "seeds_count": 0,
            "visited_count": 0,
            "discovered_count": 0,
        }

    def run(self) -> Set[str]:
        """运行发现流程"""
        self.stats["start_time"] = datetime.now()

        print("=" * 60)
        print("Amazon Products URL 发现器")
        print("=" * 60)
        print(f"目标: 发现 {self.config.max_urls} 个产品 URL")
        print(f"最大深度: {self.config.max_depth}")

        # Step 1: 种子发现
        print("\n" + "-" * 60)
        print("Phase 1: 种子发现")
        print("-" * 60)

        seed_asins = self.seed_discoverer.discover_seeds()
        self.stats["seeds_count"] = len(seed_asins)

        # 初始化队列
        for asin in seed_asins:
            self.queue.append((asin, 0))
            self.discovered_asins.add(asin)

        # Step 2: BFS 扩展
        print("\n" + "-" * 60)
        print("Phase 2: BFS 图遍历扩展")
        print("-" * 60)

        self._bfs_crawl()

        # Step 3: 输出结果
        print("\n" + "-" * 60)
        print("Phase 3: 输出结果")
        print("-" * 60)

        self._save_results()
        self._print_stats()

        return self.discovered_asins

    def _bfs_crawl(self):
        """BFS 遍历"""
        while self.queue and len(self.discovered_asins) < self.config.max_urls:
            asin, depth = self.queue.popleft()

            # 跳过已访问
            if asin in self.visited_asins:
                continue
            self.visited_asins.add(asin)
            self.stats["visited_count"] += 1

            # 进度输出
            if self.stats["visited_count"] % 10 == 0:
                print(f"  [进度] 已访问: {self.stats['visited_count']}, "
                      f"已发现: {len(self.discovered_asins)}, "
                      f"队列: {len(self.queue)}, "
                      f"深度: {depth}")

            # 定期保存检查点
            if self.stats["visited_count"] % self.config.checkpoint_interval == 0:
                self._save_checkpoint()

            # 如果达到深度限制，不再扩展
            if depth >= self.config.max_depth:
                continue

            # 扩展: 从页面发现新 ASIN
            try:
                new_asins = self.page_expander.expand(asin)

                # 添加新发现的 ASIN 到队列
                new_count = 0
                for new_asin in new_asins:
                    if new_asin not in self.discovered_asins:
                        self.discovered_asins.add(new_asin)
                        self.queue.append((new_asin, depth + 1))
                        new_count += 1

                if new_count > 0:
                    print(f"    {asin} (深度{depth}) -> 发现 {new_count} 个新 ASIN")

            except Exception as e:
                print(f"    [错误] {asin}: {e}")

    def _save_results(self):
        """保存结果到文件"""
        urls = [AmazonURLUtils.build_product_url(asin) for asin in sorted(self.discovered_asins)]

        with open(self.config.output_file, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(url + "\n")

        print(f"已保存 {len(urls)} 个 URL 到 {self.config.output_file}")

    def _save_checkpoint(self):
        """保存检查点"""
        checkpoint = {
            "discovered_asins": list(self.discovered_asins),
            "visited_asins": list(self.visited_asins),
            "queue": list(self.queue),
            "stats": self.stats,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.config.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, default=str)

    def load_checkpoint(self) -> bool:
        """加载检查点"""
        try:
            with open(self.config.checkpoint_file, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)

            self.discovered_asins = set(checkpoint["discovered_asins"])
            self.visited_asins = set(checkpoint["visited_asins"])
            self.queue = deque([(item[0], item[1]) for item in checkpoint["queue"]])
            self.stats = checkpoint["stats"]

            print(f"已加载检查点: {len(self.discovered_asins)} 个已发现, "
                  f"{len(self.visited_asins)} 个已访问")
            return True

        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"加载检查点失败: {e}")
            return False

    def _print_stats(self):
        """打印统计信息"""
        duration = datetime.now() - self.stats["start_time"]

        print("\n" + "=" * 60)
        print("统计信息")
        print("=" * 60)
        print(f"  种子数量: {self.stats['seeds_count']}")
        print(f"  已访问页面: {self.stats['visited_count']}")
        print(f"  已发现 ASIN: {len(self.discovered_asins)}")
        print(f"  运行时间: {duration}")
        print(f"  平均速度: {self.stats['visited_count'] / max(duration.total_seconds(), 1):.2f} 页/秒")


# ============================================================
# 主入口
# ============================================================

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Amazon Products URL 发现器")
    parser.add_argument("--max-urls", type=int, default=1000, help="最大发现 URL 数量")
    parser.add_argument("--max-depth", type=int, default=2, help="最大遍历深度")
    parser.add_argument("--delay", type=float, default=1.0, help="请求间隔(秒)")
    parser.add_argument("--output", type=str, default="amazon_product_urls.txt", help="输出文件")
    parser.add_argument("--resume", action="store_true", help="从检查点恢复")

    args = parser.parse_args()

    # 创建配置
    config = DiscoveryConfig(
        max_urls=args.max_urls,
        max_depth=args.max_depth,
        request_delay=args.delay,
        output_file=args.output,
    )

    # 创建控制器
    controller = CrawlController(config)

    # 尝试恢复
    if args.resume:
        controller.load_checkpoint()

    # 运行
    try:
        discovered = controller.run()
        print(f"\n完成! 共发现 {len(discovered)} 个产品 URL")
    except KeyboardInterrupt:
        print("\n\n用户中断，保存检查点...")
        controller._save_checkpoint()
        controller._save_results()
        print("已保存，可以使用 --resume 参数继续")


if __name__ == "__main__":
    main()
