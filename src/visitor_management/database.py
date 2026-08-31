#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块
简单的 JSON 数据库实现
"""

import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Database:
    """简单 JSON 数据库"""

    def __init__(self, db_path: str):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.data: Dict = {}
        self._load()

    def _load(self):
        """加载数据库"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"数据库加载成功：{self.db_path}")
            except Exception as e:
                logger.error(f"加载数据库失败：{e}")
                self.data = {}
        else:
            # 创建空数据库
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.data = {}
            self._save()

    def _save(self):
        """保存数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """获取数据"""
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        """设置数据"""
        self.data[key] = value
        self._save()

    def append(self, key: str, item: Any):
        """追加数据到列表"""
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(item)
        self._save()

    def delete(self, key: str):
        """删除数据"""
        if key in self.data:
            del self.data[key]
            self._save()

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return key in self.data

    def keys(self) -> List[str]:
        """获取所有键"""
        return list(self.data.keys())

    def clear(self):
        """清空数据库"""
        self.data = {}
        self._save()

    def __getitem__(self, key: str) -> Any:
        """支持字典访问"""
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return key in self.data

    def __len__(self) -> int:
        """获取数据项数量"""
        return len(self.data)


if __name__ == "__main__":
    # 测试
    db = Database('test_db.json')
    db.set('name', 'test')
    db.append('items', {'id': 1, 'value': 'hello'})
    print(f"数据：{db.data}")

    # 清理
    os.remove('test_db.json')
    print("测试完成")
