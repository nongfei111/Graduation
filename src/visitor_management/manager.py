#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
访客管理器
负责家庭成员管理、访客记录存储、历史查询

功能定位索引（设备端本地“留痕”模块）：
- 家庭成员访问日志：log_access() -> data/access_logs.json
- 陌生访客记录：log_unknown_visitor() -> data/visitors.json（包含抓拍路径）
- 统计信息：get_visitor_stats()

调用位置：
- main.py 识别为成员：VisitorManager.log_access()
- main.py 识别为陌生：VisitorManager.log_unknown_visitor()
- DataSync 会读取 visitors.json / access_logs.json 并上报云端
"""

import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from config.settings import DatabaseConfig, Config

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
        self.data = self._load()

    def _load(self) -> Dict:
        """加载数据库"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载数据库失败：{e}")
                return {}
        return {}

    def _save(self):
        """保存数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        """获取数据"""
        return self.data.get(key, default)

    def set(self, key: str, value):
        """设置数据"""
        self.data[key] = value
        self._save()

    def append(self, key: str, item):
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

    def clear(self):
        """清空数据库"""
        self.data = {}
        self._save()


class VisitorManager:
    """访客管理器"""

    def __init__(self, data_dir: str = None):
        """
        初始化访客管理器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir or Config.DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)

        # 初始化数据库
        self.family_db = Database(os.path.join(self.data_dir, 'family_members.json'))
        self.visitors_db = Database(os.path.join(self.data_dir, 'visitors.json'))
        self.access_logs_db = Database(os.path.join(self.data_dir, 'access_logs.json'))

        logger.info("访客管理器初始化完成")

    def add_family_member(self, name: str, info: Dict = None) -> bool:
        """
        添加家庭成员

        Args:
            name: 姓名
            info: 其他信息

        Returns:
            是否添加成功
        """
        members = self.family_db.get('members', {})
        if name in members:
            logger.warning(f"成员已存在：{name}")
            return False

        members[name] = info or {}
        self.family_db.set('members', members)
        logger.info(f"添加家庭成员：{name}")
        return True

    def remove_family_member(self, name: str) -> bool:
        """移除家庭成员"""
        members = self.family_db.get('members', {})
        if name in members:
            del members[name]
            self.family_db.set('members', members)
            logger.info(f"移除家庭成员：{name}")
            return True
        return False

    def get_family_members(self) -> List[str]:
        """获取所有家庭成员名单"""
        return list(self.family_db.get('members', {}).keys())

    def log_access(self, name: str, is_family: bool = True, extra_info: Dict = None):
        """
        记录访问日志

        Args:
            name: 姓名
            is_family: 是否为家庭成员
            extra_info: 额外信息
        """
        log_entry = {
            'name': name,
            'is_family': is_family,
            'timestamp': datetime.now().isoformat(),
            'type': 'access'
        }
        if extra_info:
            log_entry.update(extra_info)

        self.access_logs_db.append('logs', log_entry)
        logger.info(f"记录访问：{name} (家庭成员：{is_family})")

    def log_unknown_visitor(self, face_image_path: str = None, extra_info: Dict = None):
        """
        记录陌生访客

        Args:
            face_image_path: 抓拍图像路径
            extra_info: 额外信息
        """
        visitor_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'unknown_visitor',
            'face_image_path': face_image_path
        }
        if extra_info:
            visitor_entry.update(extra_info)

        self.visitors_db.append('visitors', visitor_entry)
        logger.info(f"记录陌生访客：{face_image_path}")

    def get_access_logs(self, limit: int = 50,
                        start_date: str = None,
                        end_date: str = None) -> List[Dict]:
        """
        获取访问日志

        Args:
            limit: 返回数量限制
            start_date: 开始日期 (ISO 格式)
            end_date: 结束日期 (ISO 格式)

        Returns:
            访问日志列表
        """
        logs = self.access_logs_db.get('logs', [])

        # 日期过滤
        if start_date:
            logs = [l for l in logs if l.get('timestamp', '') >= start_date]
        if end_date:
            logs = [l for l in logs if l.get('timestamp', '') <= end_date]

        # 返回最近的日志
        return logs[-limit:][::-1]

    def get_visitor_stats(self) -> Dict:
        """获取访客统计信息"""
        logs = self.access_logs_db.get('logs', [])
        visitors = self.visitors_db.get('visitors', [])

        # 按姓名统计
        name_count = {}
        for log in logs:
            name = log.get('name', 'unknown')
            name_count[name] = name_count.get(name, 0) + 1

        return {
            'total_access_logs': len(logs),
            'total_unknown_visitors': len(visitors),
            'family_member_visits': sum(1 for l in logs if l.get('is_family', False)),
            'visits_by_member': name_count
        }

    def clear_old_logs(self, days: int = 30):
        """
        清除旧日志

        Args:
            days: 保留最近多少天的日志
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        logs = self.access_logs_db.get('logs', [])

        new_logs = [l for l in logs if l.get('timestamp', '') >= cutoff]

        if len(new_logs) < len(logs):
            self.access_logs_db.set('logs', new_logs)
            logger.info(f"清除 {len(logs) - len(new_logs)} 条旧日志")


if __name__ == "__main__":
    # 测试
    manager = VisitorManager()

    # 添加测试成员
    manager.add_family_member("张三", {'role': '户主'})
    manager.add_family_member("李四", {'role': '配偶'})

    print(f"家庭成员：{manager.get_family_members()}")

    # 记录访问
    manager.log_access("张三", is_family=True)
    manager.log_unknown_visitor("visitors/unknown_001.jpg")

    # 获取统计
    stats = manager.get_visitor_stats()
    print(f"统计信息：{stats}")
