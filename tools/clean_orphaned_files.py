#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理孤立的 processed 文件
当 origin 文件被删除但 processed 文件仍然存在时，使用此工具清理
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.user_file_manager import LocalUserFileManager
from utils.user_database import default_kb_db


def clean_orphaned_processed_files(user_token: str, dry_run: bool = True):
    """清理孤立的 processed 文件

    Args:
        user_token: 用户令牌
        dry_run: 是否为试运行模式（仅显示会删除的文件，不实际删除）
    """
    file_manager = LocalUserFileManager("data")

    try:
        # 获取用户目录
        original_dir, processed_dir = file_manager.get_doc_dirs(user_token)

        if not original_dir.exists() or not processed_dir.exists():
            print(f"用户 {user_token} 的目录不存在")
            return

        # 获取所有 origin 文件的 doc_id
        origin_doc_ids = set()
        for file_path in original_dir.iterdir():
            if file_path.is_file():
                origin_doc_ids.add(file_path.stem)

        # 获取所有 processed 文件的 doc_id
        processed_files = []
        for file_path in processed_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".txt":
                processed_files.append(file_path)

        # 找出孤立的 processed 文件
        orphaned_files = []
        for processed_file in processed_files:
            doc_id = processed_file.stem
            if doc_id not in origin_doc_ids:
                # 检查数据库中是否还有记录
                record = default_kb_db.get_upload_record(doc_id)
                if not record:
                    orphaned_files.append(processed_file)

        print(f"\n=== 清理用户 {user_token} 的孤立 processed 文件 ===")
        print(f"Origin 文件数量: {len(origin_doc_ids)}")
        print(f"Processed 文件数量: {len(processed_files)}")
        print(f"发现孤立文件数量: {len(orphaned_files)}")

        if not orphaned_files:
            print("✓ 没有发现孤立的 processed 文件")
            return

        for orphaned_file in orphaned_files:
            if dry_run:
                print(f"[试运行] 会删除: {orphaned_file}")
            else:
                try:
                    orphaned_file.unlink()
                    print(f"✓ 已删除: {orphaned_file}")
                except Exception as e:
                    print(f"✗ 删除失败: {orphaned_file} - {e}")

        if dry_run:
            print(f"\n这是试运行模式，实际未删除任何文件。")
            print(
                f"如需实际删除，请运行: clean_orphaned_processed_files('{user_token}', dry_run=False)"
            )

    except Exception as e:
        print(f"清理过程中出现错误: {e}")


def clean_all_users_orphaned_files(dry_run: bool = True):
    """清理所有用户的孤立 processed 文件"""
    user_root_dir = Path("data/user/user")

    if not user_root_dir.exists():
        print("用户根目录不存在")
        return

    user_tokens = []
    for user_dir in user_root_dir.iterdir():
        if user_dir.is_dir():
            user_tokens.append(user_dir.name)

    print(f"发现 {len(user_tokens)} 个用户目录")

    for user_token in user_tokens:
        clean_orphaned_processed_files(user_token, dry_run)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="清理孤立的 processed 文件")
    parser.add_argument("--user", help="指定用户令牌")
    parser.add_argument("--all-users", action="store_true", help="清理所有用户")
    parser.add_argument(
        "--execute", action="store_true", help="实际执行删除（默认为试运行）"
    )

    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        print("=== 试运行模式 ===")
        print("使用 --execute 参数来实际执行删除操作")
    else:
        print("=== 执行模式 ===")
        print("将实际删除孤立的 processed 文件")

    if args.user:
        clean_orphaned_processed_files(args.user, dry_run)
    elif args.all_users:
        clean_all_users_orphaned_files(dry_run)
    else:
        # 默认清理 test 用户
        clean_orphaned_processed_files("test", dry_run)
