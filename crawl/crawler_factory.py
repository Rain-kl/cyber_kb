"""
爬虫工厂
统一管理和创建不同类型的爬虫
"""

from typing import Dict, Type, Optional, Any

from base_crawler import BaseCrawler
from chinacdc_crawler import ChinaCDCCrawler


class CrawlerFactory:
    """爬虫工厂类"""

    def __init__(self):
        self._crawlers: Dict[str, Type[BaseCrawler]] = {}
        self._register_default_crawlers()

    def _register_default_crawlers(self):
        """注册默认爬虫"""
        self.register_crawler("chinacdc", ChinaCDCCrawler)

    def register_crawler(self, name: str, crawler_class: Type[BaseCrawler]):
        """
        注册爬虫类

        Args:
            name: 爬虫名称
            crawler_class: 爬虫类
        """
        self._crawlers[name] = crawler_class
        print(f"Registered crawler: {name}")

    def create_crawler(self, name: str, **kwargs) -> Optional[BaseCrawler]:
        """
        创建爬虫实例

        Args:
            name: 爬虫名称
            **kwargs: 爬虫初始化参数

        Returns:
            爬虫实例，如果未找到则返回None
        """
        if name not in self._crawlers:
            print(
                f"Crawler '{name}' not found. Available crawlers: {list(self._crawlers.keys())}"
            )
            return None

        crawler_class = self._crawlers[name]
        try:
            return crawler_class(**kwargs)
        except Exception as e:
            print(f"Failed to create crawler '{name}': {e}")
            return None

    def list_crawlers(self) -> Dict[str, str]:
        """
        列出所有可用的爬虫

        Returns:
            爬虫名称和描述的字典
        """
        return {
            name: crawler_class.__doc__ or f"{crawler_class.__name__}"
            for name, crawler_class in self._crawlers.items()
        }

    async def run_crawler(
        self,
        name: str,
        save_format: str = "csv",
        filename: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        运行指定的爬虫并保存结果

        Args:
            name: 爬虫名称
            save_format: 保存格式 ("csv" 或 "json")
            filename: 保存文件名
            **kwargs: 爬虫初始化参数

        Returns:
            保存的文件名，失败时返回None
        """
        crawler = self.create_crawler(name, **kwargs)
        if not crawler:
            return None

        try:
            print(f"Running crawler: {name}")
            results = await crawler.run()

            if results:
                saved_file = crawler.save_results(results, save_format, filename)
                return saved_file
            else:
                print("No results to save.")
                return None

        except Exception as e:
            print(f"Error running crawler '{name}': {e}")
            return None

    async def run_crawler_with_save(
        self,
        name: str,
        filename: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """
        运行指定的爬虫并分批保存结果，支持URL去重

        Args:
            name: 爬虫名称
            filename: 保存文件名
            **kwargs: 爬虫初始化参数

        Returns:
            保存的文件名，失败时返回None
        """
        crawler = self.create_crawler(name, **kwargs)
        if not crawler:
            return None

        try:
            print(f"Running crawler with batch save: {name}")
            saved_file = await crawler.run_with_save(filename)
            return saved_file
        except Exception as e:
            print(f"Error running crawler '{name}': {e}")
            return None


class CrawlerConfig:
    """爬虫配置管理"""

    def __init__(self):
        self.configs = {
            "chinacdc": {
                "cache_dir": "./crawl_cache/chinacdc",
                "batch_size": 20,
                "delay": 2,
            },
            "sina_news": {
                "cache_dir": "./crawl_cache/sina",
                "batch_size": 10,
                "delay": 3,
            },
            "generic_news": {
                "cache_dir": "./crawl_cache/generic",
                "batch_size": 15,
                "delay": 2,
            },
        }

    def get_config(self, crawler_name: str) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.configs.get(crawler_name, {})

    def set_config(self, crawler_name: str, config: Dict[str, Any]):
        """设置爬虫配置"""
        self.configs[crawler_name] = config

    def update_config(self, crawler_name: str, **kwargs):
        """更新爬虫配置"""
        if crawler_name not in self.configs:
            self.configs[crawler_name] = {}
        self.configs[crawler_name].update(kwargs)


# 全局工厂实例
crawler_factory = CrawlerFactory()
crawler_config = CrawlerConfig()


async def main():
    """主函数示例"""
    # 列出所有可用爬虫
    print("Available crawlers:")
    for name, desc in crawler_factory.list_crawlers().items():
        print(f"  {name}: {desc}")

    # 运行中国疾控中心爬虫
    print("\n=== Running China CDC Crawler ===")
    config = crawler_config.get_config("chinacdc")
    result_file = await crawler_factory.run_crawler_with_save(
        "chinacdc", save_format="csv", filename="chinacdc_results.csv", **config
    )

    if result_file:
        print(f"China CDC crawling completed, saved to: {result_file}")

    # 如果需要运行其他爬虫，可以继续添加
    # print("\n=== Running News Crawler ===")
    # news_config = crawler_config.get_config("generic_news")
    # news_config.update({
    #     "base_url": "https://example.com",
    #     "list_url": "https://example.com/news"
    # })
    # news_result = await crawler_factory.run_crawler(
    #     "generic_news",
    #     save_format="json",
    #     **news_config
    # )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
