"""
通用爬虫基础框架
提供可复用的爬虫组件和抽象接口
"""

import asyncio
import csv
import functools
import hashlib
import os
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import diskcache
from crawl4ai import AsyncWebCrawler
from lxml import etree


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = ".cache"):
        self.cache = diskcache.Cache(cache_dir)

    def cache_decorator(self, expire_time: int = 86400 * 7):
        """
        异步函数缓存装饰器

        Args:
            expire_time: 缓存过期时间（秒），默认7天
        """

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = self._generate_cache_key(func.__name__, args, kwargs)

                # 显示缓存键用于调试
                print(f"[CACHE] Key: {cache_key[:16]}... for {func.__name__}")

                # 尝试从缓存获取结果
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    print(
                        f"[CACHE HIT] ✓ {func.__name__}: {args[0] if args else 'N/A'}"
                    )
                    # 只有字典类型才添加 _from_cache 标记
                    if isinstance(cached_result, dict):
                        cached_result["_from_cache"] = True
                    return cached_result

                # 缓存未命中，执行原函数
                print(f"[CACHE MISS] ✗ {func.__name__}: {args[0] if args else 'N/A'}")
                result = await func(*args, **kwargs)

                # 将结果保存到缓存
                if result is not None:
                    # 只有字典类型才添加 _from_cache 标记
                    if isinstance(result, dict):
                        result["_from_cache"] = False
                    self.cache.set(cache_key, result, expire=expire_time)
                    print(f"[CACHE SAVE] ✓ Saved result for {func.__name__}")
                else:
                    print(f"[CACHE SKIP] ✗ No result to cache for {func.__name__}")

                return result

            return wrapper

        return decorator

    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        # 排除 self 参数以避免对象实例影响缓存键
        filtered_args = args[1:] if args and hasattr(args[0], "__dict__") else args
        key_data = f"{func_name}:{str(filtered_args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        print("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "total_entries": len(self.cache),
            "cache_directory": self.cache.directory,
        }


cache_manager = CacheManager(".cache")


class HttpRequester:
    """HTTP请求器"""

    @cache_manager.cache_decorator(expire_time=36000)
    async def request(self, url: str, output_form: str = "html", **kwargs) -> str:
        """
        发送HTTP请求

        Args:
            url: 请求URL
            **kwargs: 额外的请求参数

        Returns:
            响应HTML内容
        """
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, **kwargs)
            if output_form == "html":
                return result.html
            elif output_form == "markdown":
                return result.markdown
            else:
                raise ValueError(
                    f"Unsupported output format: {output_form}. Use 'html', 'json', or 'text'."
                )


class DataParser(ABC):
    """数据解析器抽象基类"""

    @abstractmethod
    def parse_content(self, html: str) -> Dict[str, Any]:
        """
        解析内容页面

        Args:
            html: HTML内容

        Returns:
            解析后的数据字典
        """
        pass

    @abstractmethod
    def parse_urls_list(self, html: str) -> List[str]:
        """
        解析URL列表页面

        Args:
            html: HTML内容

        Returns:
            URL列表
        """
        pass


class DataExporter:
    """数据导出器"""

    def get_existing_urls(self, filename: str) -> set:
        """
        获取CSV文件中已存在的URL

        Args:
            filename: CSV文件名

        Returns:
            已存在的URL集合
        """
        existing_urls = set()
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        url = row.get("url", "").strip()
                        if url:
                            existing_urls.add(url)
            except Exception as e:
                print(f"Error reading existing URLs from {filename}: {e}")
        return existing_urls

    def append_to_csv(
        self,
        results: List[Dict[str, Any]],
        filename: str,
        fieldnames: Optional[List[str]] = None,
    ) -> int:
        """
        追加结果到CSV文件

        Args:
            results: 结果列表
            filename: 文件名
            fieldnames: CSV字段名列表

        Returns:
            实际保存的记录数
        """
        if not results:
            return 0

        # 确保URL字段包含在fieldnames中
        if not fieldnames and results:
            sample_result = results[0]
            fieldnames = [
                k for k in sample_result.keys() if k not in ["_from_cache", "timestamp"]
            ]
            # 确保url字段在第一位
            if "url" in fieldnames:
                fieldnames.remove("url")
            fieldnames.insert(0, "url")

        # 确保保存目录存在
        os.makedirs(
            (
                os.path.dirname(os.path.abspath(filename))
                if os.path.dirname(filename)
                else "."
            ),
            exist_ok=True,
        )

        # 检查文件是否存在，如果不存在则创建并写入表头
        file_exists = os.path.exists(filename)
        saved_count = 0

        try:
            with open(filename, "a", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # 如果文件不存在，写入表头
                if not file_exists:
                    writer.writeheader()

                # 写入数据
                for result in results:
                    if result and isinstance(result, dict):
                        # 清理数据，只保留指定字段
                        cleaned_row = {}
                        for field in fieldnames:
                            value = str(result.get(field, ""))
                            # 清理换行符
                            value = value.replace("\n", " ").replace("\r", " ").strip()
                            cleaned_row[field] = value
                        writer.writerow(cleaned_row)
                        saved_count += 1

            return saved_count

        except Exception as e:
            print(f"Error appending to CSV: {e}")
            return 0

    def save_to_csv(
        self,
        results: List[Dict[str, Any]],
        filename: Optional[str] = None,
        fieldnames: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        将结果保存到CSV文件

        Args:
            results: 结果列表
            filename: 文件名，如果不指定则使用时间戳命名
            fieldnames: CSV字段名列表

        Returns:
            保存的文件名，失败时返回None
        """
        if not results:
            print("No results to save.")
            return None

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_results_{timestamp}.csv"

        # 自动推断字段名，确保包含url字段
        if not fieldnames and results:
            sample_result = results[0]
            fieldnames = [
                k for k in sample_result.keys() if k not in ["_from_cache", "timestamp"]
            ]
            # 确保url字段在第一位
            if "url" in fieldnames:
                fieldnames.remove("url")
            fieldnames.insert(0, "url")

        # 确保保存目录存在
        os.makedirs(
            (
                os.path.dirname(os.path.abspath(filename))
                if os.path.dirname(filename)
                else "."
            ),
            exist_ok=True,
        )

        try:
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for result in results:
                    if result and isinstance(result, dict):
                        # 清理数据，只保留指定字段
                        cleaned_row = {}
                        for field in fieldnames:
                            value = str(result.get(field, ""))
                            # 清理换行符
                            value = value.replace("\n", " ").replace("\r", " ").strip()
                            cleaned_row[field] = value
                        writer.writerow(cleaned_row)

            print(f"Results saved to: {os.path.abspath(filename)}")
            print(f"Total records saved: {len(results)}")
            return filename

        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return None

    def save_to_json(
        self, results: List[Dict[str, Any]], filename: Optional[str] = None
    ) -> Optional[str]:
        """
        将结果保存到JSON文件

        Args:
            results: 结果列表
            filename: 文件名

        Returns:
            保存的文件名，失败时返回None
        """
        import json

        if not results:
            print("No results to save.")
            return None

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_results_{timestamp}.json"

        try:
            # 清理内部字段
            cleaned_results = []
            for result in results:
                clean_result = {
                    k: v for k, v in result.items() if k not in ["_from_cache"]
                }
                cleaned_results.append(clean_result)

            with open(filename, "w", encoding="utf-8") as jsonfile:
                json.dump(cleaned_results, jsonfile, ensure_ascii=False, indent=2)

            print(f"Results saved to: {os.path.abspath(filename)}")
            print(f"Total records saved: {len(results)}")
            return filename

        except Exception as e:
            print(f"Error saving to JSON: {e}")
            return None


class BatchCrawler:
    """批量爬虫管理器"""

    def __init__(self, batch_size: int = 20, delay: float = 2):
        self.batch_size = batch_size
        self.delay = delay

    async def batch_crawl_and_save(
        self,
        urls: List[str],
        crawl_func,
        exporter,
        filename: str,
        existing_urls: set = None,
    ) -> List[Dict[str, Any]]:
        """
        批量爬取URL并分批保存，支持URL去重

        Args:
            urls: URL列表
            crawl_func: 爬取单个URL的函数
            exporter: 数据导出器实例
            filename: 保存文件名
            existing_urls: 已存在的URL集合

        Returns:
            所有爬取结果列表
        """
        if existing_urls is None:
            existing_urls = exporter.get_existing_urls(filename)

        # 过滤已存在的URL
        filtered_urls = [url for url in urls if url not in existing_urls]
        skipped_count = len(urls) - len(filtered_urls)

        if skipped_count > 0:
            print(f"Skipped {skipped_count} URLs that already exist in {filename}")

        if not filtered_urls:
            print("All URLs already exist, no new URLs to crawl.")
            return []

        print(f"Will crawl {len(filtered_urls)} new URLs")

        all_results = []
        total_batches = (len(filtered_urls) + self.batch_size - 1) // self.batch_size
        cache_hits = 0
        new_crawls = 0
        total_saved = 0

        for i in range(0, len(filtered_urls), self.batch_size):
            batch_urls = filtered_urls[i : i + self.batch_size]
            current_batch = i // self.batch_size + 1

            print(
                f"Processing batch {current_batch}/{total_batches} ({len(batch_urls)} URLs)"
            )

            # 并发处理当前批次的URL
            batch_tasks = [crawl_func(url) for url in batch_urls]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 处理结果，过滤异常
            batch_success_results = []
            batch_cache_hits = 0
            batch_new_crawls = 0
            batch_errors = 0

            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    print(f"Error crawling {batch_urls[j]}: {result}")
                    batch_errors += 1
                else:
                    batch_success_results.append(result)
                    all_results.append(result)
                    if result.get("_from_cache", False):
                        batch_cache_hits += 1
                    else:
                        batch_new_crawls += 1

            cache_hits += batch_cache_hits
            new_crawls += batch_new_crawls

            # 保存当前批次的成功结果
            if batch_success_results:
                saved_count = exporter.append_to_csv(batch_success_results, filename)
                total_saved += saved_count
                print(
                    f"Batch {current_batch}: saved {saved_count} records to {filename}"
                )

            print(
                f"Batch {current_batch} completed: {len(batch_success_results)} success, {batch_errors} errors"
            )

            # 批次间等待
            if i + self.batch_size < len(filtered_urls):
                print(f"Waiting {self.delay} seconds before next batch...")
                await asyncio.sleep(self.delay)

        # 显示统计信息
        print(f"\nCrawling statistics:")
        print(f"Total URLs: {len(urls)}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Crawled: {len(filtered_urls)}")
        print(f"Cache hits: {cache_hits}")
        print(f"New crawls: {new_crawls}")
        print(f"Total saved: {total_saved}")
        print(
            f"Cache hit rate: {cache_hits / (cache_hits + new_crawls) * 100:.1f}%"
            if (cache_hits + new_crawls) > 0
            else "N/A"
        )

        return all_results

    async def batch_crawl_urls(
        self, urls: List[str], crawl_func
    ) -> List[Dict[str, Any]]:
        """
        批量爬取URL（保持向后兼容）

        Args:
            urls: URL列表
            crawl_func: 爬取单个URL的函数

        Returns:
            爬取结果列表
        """
        results = []
        total_batches = (len(urls) + self.batch_size - 1) // self.batch_size
        cache_hits = 0
        new_crawls = 0

        for i in range(0, len(urls), self.batch_size):
            batch_urls = urls[i : i + self.batch_size]
            current_batch = i // self.batch_size + 1

            print(
                f"Processing batch {current_batch}/{total_batches} ({len(batch_urls)} URLs)"
            )

            # 并发处理当前批次的URL
            batch_tasks = [crawl_func(url) for url in batch_urls]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 处理结果
            batch_cache_hits = 0
            batch_new_crawls = 0
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    print(f"Error crawling {batch_urls[j]}: {result}")
                else:
                    results.append(result)
                    if result.get("_from_cache", False):
                        batch_cache_hits += 1
                    else:
                        batch_new_crawls += 1

            cache_hits += batch_cache_hits
            new_crawls += batch_new_crawls

            print(
                f"Batch {current_batch} completed, got {len([r for r in batch_results if not isinstance(r, Exception)])} valid results"
            )

            # 批次间等待
            if i + self.batch_size < len(urls):
                print(f"Waiting {self.delay} seconds before next batch...")
                await asyncio.sleep(self.delay)

        # 显示统计信息
        print(f"\nCrawling statistics:")
        print(f"Cache hits: {cache_hits}")
        print(f"New crawls: {new_crawls}")
        print(
            f"Cache hit rate: {cache_hits / (cache_hits + new_crawls) * 100:.1f}%"
            if (cache_hits + new_crawls) > 0
            else "N/A"
        )

        return results


class BaseCrawler(ABC):
    """爬虫基类"""

    def __init__(self, batch_size: int = 20, delay: float = 2):
        self.requester = HttpRequester()
        self.exporter = DataExporter()
        self.batch_crawler = BatchCrawler(batch_size, delay)
        self.parser = self.create_parser()

    @abstractmethod
    def create_parser(self) -> DataParser:
        """创建数据解析器"""
        pass

    @abstractmethod
    def get_urls_list_urls(self) -> List[str]:
        """
        获取URL列表页面的URL列表（支持多页）

        Returns:
            URL列表页面的URL列表，用于支持翻页操作
            例如: ['page1_url', 'page2_url', 'page3_url', ...]
        """
        pass

    def get_urls_list_url(self) -> str:
        """
        获取URL列表页面的URL（单页版本，保持向后兼容）

        如果子类只需要处理单页，可以重写此方法。
        默认实现会调用 get_urls_list_urls() 并返回第一个URL。

        Returns:
            单个URL列表页面的URL
        """
        urls = self.get_urls_list_urls()
        if urls:
            return urls[0]
        raise NotImplementedError(
            "Must implement either get_urls_list_url or get_urls_list_urls"
        )

    async def get_urls(self) -> List[str]:
        """获取所有需要爬取的URL（支持多页获取）"""

        # 使用缓存装饰器缓存所有页面的URL结果
        @cache_manager.cache_decorator(expire_time=3600)  # URL列表缓存1小时
        async def _get_all_urls_cached():
            all_urls = []
            list_page_urls = self.get_urls_list_urls()

            print(f"Found {len(list_page_urls)} URL list pages to process")

            # 遍历所有URL列表页面
            for i, list_url in enumerate(list_page_urls, 1):
                try:
                    print(
                        f"Processing URL list page {i}/{len(list_page_urls)}: {list_url}"
                    )
                    html = await self.requester.request(list_url)
                    page_urls = self.parser.parse_urls_list(html)
                    all_urls.extend(page_urls)
                    print(f"Got {len(page_urls)} URLs from page {i}")

                    # 页面间等待，避免请求过于频繁
                    if i < len(list_page_urls):
                        await asyncio.sleep(1)

                except Exception as e:
                    print(f"Error processing URL list page {i} ({list_url}): {e}")
                    continue

            # 去重
            unique_urls = list(dict.fromkeys(all_urls))  # 保持顺序的去重
            removed_duplicates = len(all_urls) - len(unique_urls)

            if removed_duplicates > 0:
                print(f"Removed {removed_duplicates} duplicate URLs")

            return {
                "urls": unique_urls,
                "timestamp": time.time(),
                "count": len(unique_urls),
                "total_pages": len(list_page_urls),
                "raw_count": len(all_urls),
            }

        url_data = await _get_all_urls_cached()
        return url_data.get("urls", []) if isinstance(url_data, dict) else url_data

    async def crawl_single_url(self, url: str) -> Dict[str, Any]:
        """爬取单个URL"""

        # 使用缓存装饰器
        @cache_manager.cache_decorator(expire_time=86400 * 7)  # 缓存7天
        async def _fetch_and_parse_content(url):
            html = await self.requester.request(url)
            parsed_data = self.parser.parse_content(html)
            parsed_data["url"] = url
            return parsed_data

        try:
            return await _fetch_and_parse_content(url)
        except Exception as e:
            raise Exception(f"Failed to crawl {url}: {str(e)}")

    async def run(self) -> List[Dict[str, Any]]:
        """运行爬虫"""
        # 获取URL列表
        urls = await self.get_urls()
        print(f"Found {len(urls)} URLs")

        # 显示缓存状态
        cache_stats = cache_manager.get_cache_stats()
        print(f"Cache size: {cache_stats['total_entries']} entries")

        # 批量爬取
        results = await self.batch_crawler.batch_crawl_urls(urls, self.crawl_single_url)

        print(f"\nCrawling completed!")
        print(f"Total URLs found: {len(urls)}")
        print(f"Successfully crawled: {len(results)}")

        return results

    async def run_with_save(self, filename: Optional[str] = None) -> str:
        """
        运行爬虫并分批保存结果，支持URL去重

        Args:
            filename: 保存文件名，如果不指定则使用时间戳命名

        Returns:
            保存的文件名
        """
        # 生成文件名
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_results_{timestamp}.csv"

        # 获取URL列表
        urls = await self.get_urls()
        print(f"Found {len(urls)} URLs")

        # 显示缓存状态
        cache_stats = cache_manager.get_cache_stats()
        print(f"Cache size: {cache_stats['total_entries']} entries")

        # 获取已存在的URL
        existing_urls = self.exporter.get_existing_urls(filename)
        print(f"Found {len(existing_urls)} existing URLs in {filename}")

        # 批量爬取并保存
        results = await self.batch_crawler.batch_crawl_and_save(
            urls, self.crawl_single_url, self.exporter, filename, existing_urls
        )

        print(f"\nCrawling completed!")
        print(f"Results saved to: {os.path.abspath(filename)}")

        return filename

    def save_results(
        self,
        results: List[Dict[str, Any]],
        format: str = "csv",
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        保存结果

        Args:
            results: 结果列表
            format: 保存格式 ("csv" 或 "json")
            filename: 文件名

        Returns:
            保存的文件名
        """
        if format.lower() == "csv":
            return self.exporter.save_to_csv(results, filename)
        elif format.lower() == "json":
            return self.exporter.save_to_json(results, filename)
        else:
            print(f"Unsupported format: {format}")
            return None

    def generate_paginated_urls(
        self,
        base_url: str,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        page_param: str = "page",
    ) -> List[str]:
        """
        生成翻页URL的辅助方法

        Args:
            base_url: 基础URL，应该包含查询参数的格式
            start_page: 起始页码
            max_pages: 最大页数，如果为None则需要子类自己控制
            page_param: 页码参数名

        Returns:
            翻页URL列表

        Examples:
            # 生成标准翻页URL
            generate_paginated_urls("https://example.com/list?page={}", 1, 10)
            # 结果: ["https://example.com/list?page=1", "https://example.com/list?page=2", ...]

            # 自定义页码参数
            generate_paginated_urls("https://example.com/list?p={}", 1, 5, "p")
        """
        urls = []

        if max_pages is None:
            # 如果没有指定最大页数，至少返回第一页
            max_pages = 1

        for page in range(start_page, start_page + max_pages):
            if "{}" in base_url:
                # 如果URL包含{}占位符，直接格式化
                url = base_url.format(page)
            elif page_param in base_url:
                # 如果URL已经包含页码参数，替换它
                import re

                url = re.sub(f"{page_param}=\\d+", f"{page_param}={page}", base_url)
            else:
                # 如果URL不包含页码参数，添加它
                separator = "&" if "?" in base_url else "?"
                url = f"{base_url}{separator}{page_param}={page}"
            urls.append(url)

        return urls

    async def auto_detect_max_pages(
        self, base_url_template: str, max_check_pages: int = 50
    ) -> int:
        """
        自动检测最大页数的辅助方法

        Args:
            base_url_template: URL模板，使用{}作为页码占位符
            max_check_pages: 最大检查页数

        Returns:
            检测到的最大页数
        """
        print(f"Auto-detecting max pages for: {base_url_template}")

        for page in range(1, max_check_pages + 1):
            try:
                url = base_url_template.format(page)
                html = await self.requester.request(url)
                urls = self.parser.parse_urls_list(html)

                # 如果这一页没有找到任何URL，认为已经到了最后一页
                if not urls:
                    print(f"No URLs found on page {page}, stopping at page {page - 1}")
                    return max(1, page - 1)

                print(f"Page {page}: found {len(urls)} URLs")

                # 添加小延迟避免请求过快
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"Error checking page {page}: {e}")
                # 如果出错，返回前一页作为最大页数
                return max(1, page - 1)

        print(f"Reached max check limit ({max_check_pages}), using that as max pages")
        return max_check_pages


def clean_html_content(element):
    """清理HTML内容，移除所有外部资源"""

    # 复制元素以避免修改原始DOM
    import copy

    clean_element = copy.deepcopy(element)

    # 移除所有img标签
    for img in clean_element.xpath(".//img"):
        img.getparent().remove(img)

    # 移除所有svg标签
    for svg in clean_element.xpath(".//svg"):
        svg.getparent().remove(svg)

    # 移除所有带有src属性的元素(视频、音频等)
    for elem in clean_element.xpath(".//*[@src]"):
        elem.getparent().remove(elem)

    # 移除所有link标签(外部CSS等)
    for link in clean_element.xpath(".//link"):
        link.getparent().remove(link)

    # 移除所有script标签
    for script in clean_element.xpath(".//script"):
        script.getparent().remove(script)

    # 移除所有style标签
    for style in clean_element.xpath(".//style"):
        style.getparent().remove(style)

    # 移除所有iframe
    for iframe in clean_element.xpath(".//iframe"):
        iframe.getparent().remove(iframe)

    # 移除所有object和embed标签
    for obj in clean_element.xpath(".//object | .//embed"):
        obj.getparent().remove(obj)

    # 清理所有元素的属性，只保留必要的结构属性
    for elem in clean_element.xpath(".//*"):
        # 保留的属性列表
        keep_attrs = ["href"]  # 如果您想保留链接结构但不显示

        # 移除除保留属性外的所有属性
        attrs_to_remove = []
        for attr in elem.attrib:
            if attr not in keep_attrs:
                attrs_to_remove.append(attr)

        for attr in attrs_to_remove:
            del elem.attrib[attr]

    # 如果您完全不想要任何链接，取消注释下面的代码
    # for link in clean_element.xpath('.//a'):
    #     # 保留链接文本但移除链接标签
    #     if link.text:
    #         link.tail = (link.tail or '') + (link.text or '')
    #     parent = link.getparent()
    #     parent.remove(link)

    return etree.tostring(clean_element, encoding="unicode")
