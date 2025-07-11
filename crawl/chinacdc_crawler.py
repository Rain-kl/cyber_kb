"""
中国疾控中心爬虫实现
基于通用爬虫框架的具体实现
"""

from typing import List, Dict, Any

from lxml import etree

from base_crawler import BaseCrawler, DataParser


class ChinaCDCParser(DataParser):
    """中国疾控中心数据解析器"""

    def parse_content(self, html: str) -> Dict[str, Any]:
        """解析内容页面"""
        tree = etree.HTML(html)
        title = tree.xpath('//div[@class="left fl"]/h5//text()')[0].strip()
        content = tree.xpath(
            '//div[@class="left fl"]//div[@class="TRS_Editor"]//text()[not(ancestor::style)]'
        )
        return {
            "title": title,
            "content": "\n".join(content).strip(),
        }

    def parse_urls_list(self, html: str) -> List[str]:
        """解析URL列表页面"""
        tree = etree.HTML(html)
        urls = tree.xpath('//p[@class="search-title-text"]/a/@href')
        return urls


class ChinaCDCCrawler(BaseCrawler):
    """中国疾控中心爬虫"""

    def create_parser(self) -> DataParser:
        """创建数据解析器"""
        return ChinaCDCParser()

    def get_urls_list_url(self) -> str:
        """获取URL列表页面的URL"""
        return "https://www.chinacdc.cn/was5/web/search?page=1&channelid=243142&perpage=300"




async def main():
    """主函数 - 边爬边保存模式"""
    # 创建爬虫实例，配置合适的批次大小和延迟
    crawler = ChinaCDCCrawler( batch_size=20, delay=0.5)

    # 使用边爬边保存功能，支持断点续传和URL去重
    filename = "chinacdc_crawl_results.csv"

    result_file = await crawler.run_with_save(filename)

    if result_file:
        print(f"爬取完成，数据已保存到: {result_file}")
    else:
        print("爬取失败")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
