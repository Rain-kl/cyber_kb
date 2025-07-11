# https://www.msdmanuals.cn/sitemap.ashx
"""
默沙东手册爬虫实现
基于通用爬虫框架的具体实现

特性：
- 边爬边保存：爬一批保存一批，避免内存占用过大
- URL去重：自动跳过已存在的URL，支持断点续爬
- 错误跳过：遇到错误的URL自动跳过，不影响整体进度
- 缓存支持：重复访问的URL从缓存读取，提高效率

使用方法：
python msd_crawler.py
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from urllib.parse import urlparse

import html2text
from lxml import etree

from .base_crawler import BaseCrawler, DataParser, clean_html_content

attention_list = [
    "cancer",
    "men-s-health-issues",
    "children-s-health-issues",
    "brain-spinal-cord-and-nerve-disorders",
    "ear-nose-and-throat-disorders",
    "women-s-health-issues",
    "lung-and-airway-disorders",
    "skin-disorders",
    "liver-and-gallbladder-disorders",
    "kidney-and-urinary-tract-disorders",
    "infections",
    "injuries-and-poisoning",
    "bone-joint-and-muscle-disorders",
    "special-subjects",
    "fundamentals",
    "digestive-disorders",
    "hormonal-and-metabolic-disorders",
    "heart-and-blood-vessel-disorders",
    "mental-health-disorders",
    "blood-disorders",
    "mouth-and-dental-disorders",
    "eye-disorders",
    "older-people-s-health-issues",
    "drugs",
    "immune-disorders",
    "disorders-of-nutrition",
]


class MSDParser(DataParser):
    """默沙东手册数据解析器"""

    def parse_content(self, html: str) -> Dict[str, Any]:
        """解析内容页面"""
        tree = etree.HTML(html)
        main_content = tree.xpath(
            '//div[@class="Topic_topicContainerRight__1T_vb false false"]'
        )
        if not main_content:
            print("未找到目标内容块")
            return None

        if main_content:
            # 清理HTML
            cleaned_html = clean_html_content(main_content[0])

            # 配置html2text完全忽略外部资源
            h = html2text.HTML2Text()
            h.ignore_links = True  # 完全忽略链接
            h.ignore_images = True  # 完全忽略图片
            h.body_width = 0  # 不限制行宽
            h.unicode_snob = True  # 处理中文

            # 转换并清理
            markdown = h.handle(cleaned_html)
            return {
                "title": tree.xpath(
                    '//div[@class="TopicHead_topic__header__container__sJqaX TopicHead_headerContainerMediaNone__s8aMz"]//h1//text()'
                )[0].strip(),
                "content": markdown,
            }

    def parse_urls_list(self, html: str) -> List[str]:
        """解析URL列表页面"""
        """
            解析 sitemap 并提取符合条件的 URL

            Args:
                source: 可以是以下任意一种:
                    - URL 字符串 (以 http:// 或 https:// 开头)
                    - 本地文件路径
                    - XML 字符串内容
                attention_list: 要匹配的关键词列表

            Returns:
                list: 符合条件的 URL 列表
            """
        xml_content = html
        # 解析 XML
        root = ET.fromstring(xml_content)

        # 定义命名空间
        namespace = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # 提取所有 URL
        urls = []
        for url_element in root.findall(".//sitemap:url", namespace):
            loc_element = url_element.find("sitemap:loc", namespace)
            if loc_element is not None:
                urls.append(loc_element.text)

        # 筛选符合条件的 URL
        filtered_urls = []
        for url in urls:
            # 解析 URL 获取路径
            parsed_url = urlparse(url)
            path = parsed_url.path

            # 检查是否匹配 /home/{attention} 格式
            for attention in attention_list:
                pattern = f"/home/{attention}"
                if path.startswith(pattern):
                    filtered_urls.append(url)
                    break  # 找到匹配后跳出内层循环
        print(len(filtered_urls), "符合条件的URL数量")
        return filtered_urls


class MSDCrawler(BaseCrawler):
    """默沙东手册爬虫"""

    def create_parser(self) -> DataParser:
        """创建数据解析器"""
        return MSDParser()

    def get_urls_list_urls(self) -> List[str]:
        """获取URL列表页面的URL"""
        return ["https://www.msdmanuals.cn/sitemap.ashx"]


async def main():
    """主函数 - 边爬边保存模式"""
    # 创建爬虫实例，配置合适的批次大小和延迟
    crawler = MSDCrawler(batch_size=20, delay=0.5)

    # 使用边爬边保存功能，支持断点续传和URL去重
    filename = "msd_crawl_results.csv"
    print(f"开始爬取MSD手册数据，结果将保存到: {filename}")

    result_file = await crawler.run_with_save(filename)

    if result_file:
        print(f"爬取完成，数据已保存到: {result_file}")
    else:
        print("爬取失败")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
