"""
翻页爬虫示例
展示如何使用修改后的 BaseCrawler 框架处理翻页
"""

from typing import List, Dict, Any

from lxml import etree

from crawl.base_crawler import BaseCrawler, DataParser


class ExamplePaginatedParser(DataParser):
    """示例翻页解析器"""

    def parse_urls_list(self, html: str) -> List[str]:
        """解析URL列表页面，提取文章链接"""
        try:
            root = etree.HTML(html)
            # 示例：提取所有文章链接
            urls = root.xpath('//a[contains(@href, "/article/")]/@href')
            # 确保URL是完整的
            base_url = "https://example.com"
            full_urls = []
            for url in urls:
                if url.startswith("http"):
                    full_urls.append(url)
                else:
                    full_urls.append(base_url + url)
            return full_urls
        except Exception as e:
            print(f"Error parsing URLs list: {e}")
            return []

    def parse_content(self, html: str) -> Dict[str, Any]:
        """解析文章内容页面"""
        try:
            root = etree.HTML(html)

            # 提取标题
            title_elements = root.xpath(
                '//h1[@class="title"]//text() | //title//text()'
            )
            title = "".join(title_elements).strip() if title_elements else "No title"

            # 提取内容
            content_elements = root.xpath('//div[@class="content"]//text()')
            content = "\n".join(
                [text.strip() for text in content_elements if text.strip()]
            )

            # 提取发布时间
            date_elements = root.xpath('//span[@class="date"]//text()')
            publish_date = date_elements[0].strip() if date_elements else ""

            return {
                "title": title,
                "content": content,
                "publish_date": publish_date,
                "content_length": len(content),
            }
        except Exception as e:
            print(f"Error parsing content: {e}")
            return {
                "title": "Parse Error",
                "content": f"Error: {str(e)}",
                "publish_date": "",
                "content_length": 0,
            }


class ExamplePaginatedCrawler(BaseCrawler):
    """示例翻页爬虫 - 方法1：手动指定页面URL列表"""

    def __init__(self, base_url: str, total_pages: int, **kwargs):
        self.base_url = base_url
        self.total_pages = total_pages
        super().__init__(**kwargs)

    def create_parser(self) -> DataParser:
        return ExamplePaginatedParser()

    def get_urls_list_urls(self) -> List[str]:
        """返回所有URL列表页面的URL"""
        # 方法1：手动生成所有页面URL
        urls = []
        for page in range(1, self.total_pages + 1):
            url = f"{self.base_url}?page={page}"
            urls.append(url)
        return urls


class ExampleAutoPaginatedCrawler(BaseCrawler):
    """示例自动翻页爬虫 - 方法2：使用辅助方法自动生成"""

    def __init__(self, base_url_template: str, max_pages: int = None, **kwargs):
        self.base_url_template = base_url_template
        self.max_pages = max_pages
        super().__init__(**kwargs)

    def create_parser(self) -> DataParser:
        return ExamplePaginatedParser()

    def get_urls_list_urls(self) -> List[str]:
        """使用辅助方法生成翻页URL"""
        if self.max_pages:
            # 如果指定了最大页数，直接生成
            return self.generate_paginated_urls(
                self.base_url_template, start_page=1, max_pages=self.max_pages
            )
        else:
            # 如果没有指定，先返回第一页，实际使用时可以先自动检测
            return [self.base_url_template.format(1)]


class ExampleSmartPaginatedCrawler(BaseCrawler):
    """示例智能翻页爬虫 - 方法3：自动检测页数"""

    def __init__(self, base_url_template: str, **kwargs):
        self.base_url_template = base_url_template
        self._detected_max_pages = None
        super().__init__(**kwargs)

    def create_parser(self) -> DataParser:
        return ExamplePaginatedParser()

    async def get_urls_list_urls_async(self) -> List[str]:
        """异步方法：自动检测最大页数并生成URL列表"""
        if self._detected_max_pages is None:
            self._detected_max_pages = await self.auto_detect_max_pages(
                self.base_url_template, max_check_pages=10  # 最多检查10页
            )

        return self.generate_paginated_urls(
            self.base_url_template, start_page=1, max_pages=self._detected_max_pages
        )

    def get_urls_list_urls(self) -> List[str]:
        """同步方法：需要在运行前调用异步检测方法"""
        if self._detected_max_pages is None:
            # 如果还没有检测过，先返回第一页
            print("Warning: Max pages not detected yet, returning first page only")
            return [self.base_url_template.format(1)]

        return self.generate_paginated_urls(
            self.base_url_template, start_page=1, max_pages=self._detected_max_pages
        )

    async def run_with_auto_detection(self) -> List[Dict[str, Any]]:
        """运行爬虫，自动检测页数"""
        # 先检测最大页数
        await self.get_urls_list_urls_async()
        # 然后运行常规流程
        return await self.run()


# 使用示例
async def example_usage():
    """使用示例"""

    print("=== 示例1：手动指定页面数量 ===")
    crawler1 = ExamplePaginatedCrawler(
        base_url="https://example.com/news", total_pages=5, batch_size=10, delay=1
    )
    # results1 = await crawler1.run()
    # print(f"获取到 {len(results1)} 条结果")

    print("\n=== 示例2：使用辅助方法生成URL ===")
    crawler2 = ExampleAutoPaginatedCrawler(
        base_url_template="https://example.com/articles?page={}",
        max_pages=3,
        batch_size=15,
        delay=1.5,
    )
    # results2 = await crawler2.run()
    # print(f"获取到 {len(results2)} 条结果")

    print("\n=== 示例3：智能检测页数 ===")
    crawler3 = ExampleSmartPaginatedCrawler(
        base_url_template="https://example.com/blog?p={}", batch_size=20, delay=2
    )
    # results3 = await crawler3.run_with_auto_detection()
    # print(f"获取到 {len(results3)} 条结果")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
