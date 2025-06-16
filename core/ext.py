from utils.user_database import SQLiteUserDatabase, SQLiteKnowledgeBaseDB
from utils.user_file_manager import LocalUserFileManager

# 默认数据库实例
file_manager = LocalUserFileManager("data")
default_user_db = SQLiteUserDatabase(file_manager.user_root_dir / "user.db")
default_kb_db = SQLiteKnowledgeBaseDB(file_manager.user_root_dir / "user.db")
