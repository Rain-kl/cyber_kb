import abc
from typing import List, Dict, Any


class MemoryDatabaseInterface(abc.ABC):
    """数据库抽象接口类"""

    @abc.abstractmethod
    def connect(self) -> None:
        """连接到数据库"""
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""
        pass

    @abc.abstractmethod
    def init_tables(self) -> None:
        """初始化数据库表"""
        pass

    @abc.abstractmethod
    def add_layer1_record(self, apikey: str, content: str) -> int:
        """添加 layer1 记录"""
        pass

    @abc.abstractmethod
    def add_layer3_record(self, apikey: str, behavior: str, instruction: str) -> int:
        """添加 layer3 记录"""
        pass

    @abc.abstractmethod
    def get_layer1_records_by_apikey(self, apikey: str) -> List[Dict[str, Any]]:
        """根据 apikey 获取 layer1 记录"""
        pass

    @abc.abstractmethod
    def get_layer3_records_by_apikey(self, apikey: str) -> List[Dict[str, Any]]:
        """根据 apikey 获取 layer3 记录"""
        pass

    @abc.abstractmethod
    def update_layer1_content(self, record_id: int, content: str) -> bool:
        """更新 layer1 记录内容"""
        pass

    @abc.abstractmethod
    def update_layer3_record(
        self, record_id: int, behavior: str, instruction: str
    ) -> bool:
        """更新 layer3 记录"""
        pass

    @abc.abstractmethod
    def delete_layer1_record(self, record_id: int) -> bool:
        """删除 layer1 记录"""
        pass

    @abc.abstractmethod
    def delete_layer3_record(self, record_id: int) -> bool:
        """删除 layer3 记录"""
        pass
