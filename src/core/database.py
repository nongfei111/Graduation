"""
CLAUDE 智能门铃系统 - 数据库模块
负责 SQLite 数据库操作，包括家庭成员和访客记录管理
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import json
import numpy as np


class Database:
    """智能门铃系统数据库管理类"""

    def __init__(self, db_path: str = "data/database/doorbell.db"):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 家庭成员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # 人脸特征表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                embedding BLOB NOT NULL,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
            )
        ''')

        # 访客记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitor_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_type TEXT NOT NULL,
                member_id INTEGER,
                name TEXT,
                image_path TEXT,
                embedding BLOB,
                confidence REAL,
                duration_seconds INTEGER,
                is_alert INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        ''')

        # 系统日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_type TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    # ==================== 家庭成员管理 ====================

    def add_member(self, name: str) -> int:
        """
        添加家庭成员

        Args:
            name: 成员姓名

        Returns:
            成员 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO members (name) VALUES (?)', (name,))
            conn.commit()
            member_id = cursor.lastrowid
            return member_id
        except sqlite3.IntegrityError:
            raise ValueError(f"成员 '{name}' 已存在")
        finally:
            conn.close()

    def update_member(self, member_id: int, name: str) -> bool:
        """更新成员信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE members SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (name, member_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def delete_member(self, member_id: int) -> bool:
        """删除成员（软删除）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE members SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (member_id,)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def get_member(self, member_id: int) -> Optional[Dict]:
        """获取成员信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM members WHERE id = ? AND is_active = 1', (member_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_members(self) -> List[Dict]:
        """获取所有活跃成员"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM members WHERE is_active = 1 ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== 人脸特征管理 ====================

    def add_face_embedding(self, member_id: int, embedding: np.ndarray, image_path: str = None) -> int:
        """
        添加人脸特征向量

        Args:
            member_id: 成员 ID
            embedding: 人脸特征向量 (numpy array)
            image_path: 人脸图片路径

        Returns:
            记录 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        embedding_bytes = embedding.tobytes()
        cursor.execute(
            'INSERT INTO face_embeddings (member_id, embedding, image_path) VALUES (?, ?, ?)',
            (member_id, embedding_bytes, image_path)
        )
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    def get_face_embeddings(self, member_id: int = None) -> List[Tuple[int, np.ndarray]]:
        """
        获取人脸特征向量

        Args:
            member_id: 成员 ID，None 表示获取所有

        Returns:
            [(member_id, embedding), ...]
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if member_id:
            cursor.execute('''
                SELECT fe.member_id, fe.embedding
                FROM face_embeddings fe
                JOIN members m ON fe.member_id = m.id
                WHERE fe.member_id = ? AND m.is_active = 1
            ''', (member_id,))
        else:
            cursor.execute('''
                SELECT fe.member_id, fe.embedding
                FROM face_embeddings fe
                JOIN members m ON fe.member_id = m.id
                WHERE m.is_active = 1
            ''')

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            embedding = np.frombuffer(row[1], dtype=np.float32)
            results.append((row[0], embedding))

        return results

    def delete_face_embeddings(self, member_id: int) -> bool:
        """删除成员的所有人脸特征"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM face_embeddings WHERE member_id = ?', (member_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    # ==================== 访客记录管理 ====================

    def add_visitor_record(self, visitor_type: str, member_id: int = None,
                          name: str = None, image_path: str = None,
                          embedding: np.ndarray = None, confidence: float = None,
                          duration_seconds: int = None, is_alert: bool = False) -> int:
        """
        添加访客记录

        Args:
            visitor_type: 访客类型 ('member' 或 'stranger')
            member_id: 成员 ID（如果是家庭成员）
            name: 访客姓名
            image_path: 抓拍图片路径
            embedding: 人脸特征向量
            confidence: 识别置信度
            duration_seconds: 停留时长（秒）
            is_alert: 是否触发警报

        Returns:
            记录 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        embedding_bytes = embedding.tobytes() if embedding is not None else None

        cursor.execute('''
            INSERT INTO visitor_records
            (visitor_type, member_id, name, image_path, embedding, confidence, duration_seconds, is_alert)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (visitor_type, member_id, name, image_path, embedding_bytes,
              confidence, duration_seconds, 1 if is_alert else 0))

        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    def get_visitor_records(self, limit: int = 100, offset: int = 0,
                           visitor_type: str = None, date_from: str = None,
                           date_to: str = None) -> List[Dict]:
        """
        获取访客记录

        Args:
            limit: 返回数量限制
            offset: 偏移量
            visitor_type: 访客类型过滤
            date_from: 起始日期
            date_to: 结束日期

        Returns:
            访客记录列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM visitor_records WHERE 1=1'
        params = []

        if visitor_type:
            query += ' AND visitor_type = ?'
            params.append(visitor_type)

        if date_from:
            query += ' AND created_at >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND created_at <= ?'
            params.append(date_to)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_visitor_count(self, visitor_type: str = None, date_from: str = None,
                         date_to: str = None) -> int:
        """获取访客数量统计"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = 'SELECT COUNT(*) FROM visitor_records WHERE 1=1'
        params = []

        if visitor_type:
            query += ' AND visitor_type = ?'
            params.append(visitor_type)

        if date_from:
            query += ' AND created_at >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND created_at <= ?'
            params.append(date_to)

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ==================== 系统日志管理 ====================

    def add_log(self, log_type: str, message: str, details: str = None) -> int:
        """添加系统日志"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO system_logs (log_type, message, details) VALUES (?, ?, ?)',
            (log_type, message, details)
        )
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return log_id

    def get_logs(self, limit: int = 100, log_type: str = None) -> List[Dict]:
        """获取系统日志"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if log_type:
            cursor.execute(
                'SELECT * FROM system_logs WHERE log_type = ? ORDER BY created_at DESC LIMIT ?',
                (log_type, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?',
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== 统计功能 ====================

    def get_statistics(self) -> Dict:
        """获取系统统计信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 家庭成员数量
        cursor.execute('SELECT COUNT(*) FROM members WHERE is_active = 1')
        member_count = cursor.fetchone()[0]

        # 今日访客记录
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            'SELECT COUNT(*) FROM visitor_records WHERE DATE(created_at) = ?',
            (today,)
        )
        today_visits = cursor.fetchone()[0]

        # 今日陌生访客
        cursor.execute(
            "SELECT COUNT(*) FROM visitor_records WHERE DATE(created_at) = ? AND visitor_type = 'stranger'",
            (today,)
        )
        today_strangers = cursor.fetchone()[0]

        # 警报次数
        cursor.execute(
            'SELECT COUNT(*) FROM visitor_records WHERE is_alert = 1'
        )
        alert_count = cursor.fetchone()[0]

        conn.close()

        return {
            'member_count': member_count,
            'today_visits': today_visits,
            'today_strangers': today_strangers,
            'alert_count': alert_count
        }

    def export_data(self) -> str:
        """导出所有数据为 JSON"""
        data = {
            'members': self.get_all_members(),
            'visitor_records': self.get_visitor_records(limit=1000),
            'statistics': self.get_statistics(),
            'exported_at': datetime.now().isoformat()
        }
        return json.dumps(data, indent=2, default=str)
