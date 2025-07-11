# BaseCrawler 翻页功能使用指南

## 概述

修改后的 `BaseCrawler` 框架现在支持翻页操作，可以处理需要从多个页面获取URL列表的场景。这对于需要爬取分页内容的网站非常有用。

## 主要变更

### 1. 新的抽象方法

```python
@abstractmethod
def get_urls_list_urls(self) -> List[str]:
    """
    获取URL列表页面的URL列表（支持多页）
    
    Returns:
        URL列表页面的URL列表，用于支持翻页操作
        例如: ['page1_url', 'page2_url', 'page3_url', ...]
    """
    pass
```

### 2. 向后兼容支持

保留了原来的 `get_urls_list_url()` 方法，提供默认实现以保持向后兼容性。

### 3. 新增辅助方法

- `generate_paginated_urls()`: 生成翻页URL的辅助方法
- `auto_detect_max_pages()`: 自动检测最大页数的方法

## 使用方法

### 方法1：手动指定页面URL列表

```python
class MyCrawler(BaseCrawler):
    def __init__(self, base_url: str, total_pages: int, **kwargs):
        self.base_url = base_url
        self.total_pages = total_pages
        super().__init__(**kwargs)
    
    def get_urls_list_urls(self) -> List[str]:
        """手动生成所有页面URL"""
        urls = []
        for page in range(1, self.total_pages + 1):
            url = f"{self.base_url}?page={page}"
            urls.append(url)
        return urls
```

### 方法2：使用辅助方法生成URL

```python
class MyCrawler(BaseCrawler):
    def __init__(self, base_url_template: str, max_pages: int, **kwargs):
        self.base_url_template = base_url_template
        self.max_pages = max_pages
        super().__init__(**kwargs)
    
    def get_urls_list_urls(self) -> List[str]:
        """使用辅助方法生成翻页URL"""
        return self.generate_paginated_urls(
            self.base_url_template, 
            start_page=1, 
            max_pages=self.max_pages
        )
```

### 方法3：自动检测页数（推荐）

```python
class SmartCrawler(BaseCrawler):
    def __init__(self, base_url_template: str, **kwargs):
        self.base_url_template = base_url_template
        self._detected_max_pages = None
        super().__init__(**kwargs)
    
    async def detect_and_run(self):
        """先检测页数，然后运行爬虫"""
        # 自动检测最大页数
        self._detected_max_pages = await self.auto_detect_max_pages(
            self.base_url_template, 
            max_check_pages=50
        )
        
        # 运行爬虫
        return await self.run()
    
    def get_urls_list_urls(self) -> List[str]:
        if self._detected_max_pages:
            return self.generate_paginated_urls(
                self.base_url_template, 
                start_page=1, 
                max_pages=self._detected_max_pages
            )
        else:
            # 如果还没检测过，先返回第一页
            return [self.base_url_template.format(1)]
```

## 辅助方法详解

### generate_paginated_urls()

```python
def generate_paginated_urls(self, base_url: str, start_page: int = 1, 
                           max_pages: Optional[int] = None, 
                           page_param: str = "page") -> List[str]:
```

**参数说明：**
- `base_url`: 基础URL，支持多种格式
  - 包含 `{}` 占位符：`"https://example.com/list?page={}"`
  - 已包含页码参数：`"https://example.com/list?page=1"`
  - 不包含页码参数：`"https://example.com/list"`
- `start_page`: 起始页码（默认1）
- `max_pages`: 生成的页数（必须指定）
- `page_param`: 页码参数名（默认"page"）

**使用示例：**
```python
# 使用占位符格式
urls = self.generate_paginated_urls("https://example.com/list?page={}", 1, 10)

# 自定义页码参数
urls = self.generate_paginated_urls("https://example.com/list?p={}", 1, 5, "p")

# 基础URL自动添加参数
urls = self.generate_paginated_urls("https://example.com/list", 1, 3)
```

### auto_detect_max_pages()

```python
async def auto_detect_max_pages(self, base_url_template: str, 
                               max_check_pages: int = 50) -> int:
```

**功能：**
- 自动检测网站的最大页数
- 通过依次访问页面并检查是否有内容来判断
- 当某页没有找到任何URL时，认为已到达最后一页

**参数说明：**
- `base_url_template`: URL模板，使用 `{}` 作为页码占位符
- `max_check_pages`: 最大检查页数（防止无限循环）

## 新特性

### 1. 自动去重

新的 `get_urls()` 方法会自动去除重复的URL，并显示去重统计信息。

### 2. 详细的统计信息

```python
# 缓存的数据结构
{
    "urls": unique_urls, 
    "timestamp": time.time(), 
    "count": len(unique_urls),
    "total_pages": len(list_page_urls),
    "raw_count": len(all_urls)  # 去重前的数量
}
```

### 3. 错误处理

- 单个页面出错不会影响其他页面的处理
- 详细的错误日志记录
- 优雅的降级处理

## 性能优化

### 1. 缓存机制

- URL列表结果会缓存1小时
- 支持多页面结果的整体缓存
- 避免重复的网络请求

### 2. 请求控制

- 页面间自动添加延迟（1秒）
- 可配置的批次大小和延迟时间
- 防止请求过于频繁

### 3. 并发控制

- 支持批量并发处理内容页面
- 合理的错误处理和重试机制

## 迁移指南

### 从旧版本迁移

如果你有使用旧版本 `BaseCrawler` 的代码：

**旧代码：**
```python
class OldCrawler(BaseCrawler):
    def get_urls_list_url(self) -> str:
        return "https://example.com/list"
```

**新代码选项1（最小修改）：**
```python
class NewCrawler(BaseCrawler):
    def get_urls_list_urls(self) -> List[str]:
        return ["https://example.com/list"]  # 单页面列表
```

**新代码选项2（使用翻页）：**
```python
class NewCrawler(BaseCrawler):
    def get_urls_list_urls(self) -> List[str]:
        return self.generate_paginated_urls(
            "https://example.com/list?page={}", 
            1, 10
        )
```

## 最佳实践

1. **优先使用自动检测页数**：避免硬编码页数，让爬虫自适应网站变化
2. **合理设置检查页数上限**：防止无限循环，通常50页已经足够
3. **配置适当的延迟**：尊重网站服务器，避免过于频繁的请求
4. **监控缓存效果**：查看缓存命中率，优化爬虫性能
5. **处理异常情况**：准备好处理页面加载失败、解析错误等情况

## 示例项目

参考 `pagination_example.py` 文件查看完整的使用示例，包括三种不同的翻页实现方式。
