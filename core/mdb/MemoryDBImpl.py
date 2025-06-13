import datetime
import sqlite3
from typing import List, Dict, Any

from .MemoryDB import MemoryDatabaseInterface


class MemoryDB(MemoryDatabaseInterface):
    """SQLite 数据库实现类"""

    def __init__(self, db_path: str = "./data/memory.db"):
        """初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """支持上下文管理器"""
        self.connect()
        self.init_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.close()
        if exc_type:
            raise exc_val
        return True

    def connect(self) -> None:
        """连接到 SQLite 数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # 设置行工厂，使查询结果以字典形式返回
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            raise Exception(f"数据库连接失败: {e}")

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def init_tables(self) -> None:
        """初始化数据库表结构"""
        if not self.conn:
            self.connect()

        try:
            # 创建 layer1 表
            self.cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS layer1 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apikey TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # 创建 layer3 表
            self.cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS layer3 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apikey TEXT NOT NULL,
                behavior TEXT NOT NULL,
                instruction TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            )

            # 为 apikey 创建索引，优化查询性能
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer1_apikey ON layer1 (apikey)"
            )
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer3_apikey ON layer3 (apikey)"
            )

            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"初始化表失败: {e}")

    def add_layer1_record(self, apikey: str, content: str) -> int:
        """添加 layer1 记录

        Args:
            apikey: 用户标识
            content: 内容

        Returns:
            新记录的 ID
        """
        if not self.conn:
            self.connect()

        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "INSERT INTO layer1 (apikey, content, timestamp) VALUES (?, ?, ?)",
                (apikey, content, current_time),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"添加 layer1 记录失败: {e}")

    def add_layer3_record(self, apikey: str, behavior: str, instruction: str) -> int:
        """添加 layer3 记录

        Args:
            apikey: 用户标识
            behavior: 行为
            instruction: 指令

        Returns:
            新记录的 ID
        """
        if not self.conn:
            self.connect()

        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "INSERT INTO layer3 (apikey, behavior, instruction, timestamp) VALUES (?, ?, ?, ?)",
                (apikey, behavior, instruction, current_time),
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"添加 layer3 记录失败: {e}")

    def get_layer1_records_by_apikey(self, apikey: str) -> List[Dict[str, Any]]:
        """根据 apikey 获取 layer1 记录

        Args:
            apikey: 用户标识

        Returns:
            layer1 记录列表
        """
        if not self.conn:
            self.connect()

        try:
            self.cursor.execute(
                "SELECT * FROM layer1 WHERE apikey = ? ORDER BY timestamp DESC",
                (apikey,),
            )
            results = self.cursor.fetchall()
            return [dict(row) for row in results]
        except sqlite3.Error as e:
            raise Exception(f"查询 layer1 记录失败: {e}")

    def get_layer3_records_by_apikey(self, apikey: str) -> List[Dict[str, Any]]:
        """根据 apikey 获取 layer3 记录

        Args:
            apikey: 用户标识

        Returns:
            layer3 记录列表
        """
        if not self.conn:
            self.connect()

        try:
            self.cursor.execute(
                "SELECT * FROM layer3 WHERE apikey = ? ORDER BY timestamp DESC",
                (apikey,),
            )
            results = self.cursor.fetchall()
            return [dict(row) for row in results]
        except sqlite3.Error as e:
            raise Exception(f"查询 layer3 记录失败: {e}")

    def update_layer1_content(self, record_id: int, content: str) -> bool:
        """更新 layer1 记录内容

        Args:
            record_id: 记录ID
            content: 新内容

        Returns:
            更新是否成功
        """
        if not self.conn:
            self.connect()

        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "UPDATE layer1 SET content = ?, timestamp = ? WHERE id = ?",
                (content, current_time, record_id),
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"更新 layer1 记录失败: {e}")

    def update_layer3_record(
        self, record_id: int, behavior: str, instruction: str
    ) -> bool:
        """更新 layer3 记录

        Args:
            record_id: 记录ID
            behavior: 新的行为
            instruction: 新的指令

        Returns:
            更新是否成功
        """
        if not self.conn:
            self.connect()

        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "UPDATE layer3 SET behavior = ?, instruction = ?, timestamp = ? WHERE id = ?",
                (behavior, instruction, current_time, record_id),
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"更新 layer3 记录失败: {e}")

    def delete_layer1_record(self, record_id: int) -> bool:
        """删除 layer1 记录

        Args:
            record_id: 记录ID

        Returns:
            删除是否成功
        """
        if not self.conn:
            self.connect()

        try:
            self.cursor.execute("DELETE FROM layer1 WHERE id = ?", (record_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"删除 layer1 记录失败: {e}")

    def delete_layer3_record(self, record_id: int) -> bool:
        """删除 layer3 记录

        Args:
            record_id: 记录ID

        Returns:
            删除是否成功
        """
        if not self.conn:
            self.connect()

        try:
            self.cursor.execute("DELETE FROM layer3 WHERE id = ?", (record_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"删除 layer3 记录失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建数据库实例

    with MemoryDB(db_path="test_memory.db") as db:
        db.add_layer1_record("user_123", "这是一条测试内容")
        print(db.get_layer1_records_by_apikey("user_123"))
