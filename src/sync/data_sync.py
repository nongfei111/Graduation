#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据同步模块
负责本地数据库存储、WiFi 数据同步、手机 APP 通信接口

功能定位索引（设备端同步调度器）：
- 成员同步（人脸库更新）：sync_members_if_needed() / sync_members()
  - 从云端拉取 members 列表与照片 URL
  - 写入 data/faces/<name>/cloud_member_<id>.jpg
  - 触发 recognizer.reload_known_faces(force_rebuild=True) 重建 faces_cache.pkl
- 访客记录上报（设备端缓存 -> 云端落库）：sync_data() -> _upload_visitors()
- 访问日志上报：sync_data() -> _upload_logs()

调用位置：
- main.py 主循环内周期调用：data_sync.sync_members_if_needed() / data_sync.sync_if_needed()
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from config.settings import NetworkConfig, Config

logger = logging.getLogger(__name__)


class DataSync:
    """数据同步类"""

    def __init__(self, server_host: str = None, server_port: int = None, cloud_comm=None, recognizer=None):
        """
        初始化数据同步

        Args:
            server_host: 服务器地址
            server_port: 服务器端口
        """
        self.server_host = server_host or NetworkConfig.SERVER_HOST
        self.server_port = server_port or NetworkConfig.SERVER_PORT
        self.sync_interval = NetworkConfig.SYNC_INTERVAL
        self.last_sync_time: Optional[datetime] = None
        self.cloud_comm = cloud_comm
        self.recognizer = recognizer
        self._last_member_sync_ts = 0.0

        self.data_dir = Config.DATA_DIR
        self.visitors_file = os.path.join(self.data_dir, 'visitors.json')
        self.logs_file = os.path.join(self.data_dir, 'access_logs.json')

        logger.info(f"DataSync 初始化完成 (服务器：{self.server_host}:{self.server_port})")

    def sync_members_if_needed(self, min_interval_sec: int = 60) -> bool:
        now = time.time()
        if now - self._last_member_sync_ts < min_interval_sec:
            return False
        ok = self.sync_members()
        self._last_member_sync_ts = now
        return ok

    def sync_members(self) -> bool:
        if not self.cloud_comm:
            return False

        data = self.cloud_comm.get_device_members()
        if data is None:
            return False

        members = data.get('members') or []
        face_dir = Config.FACE_DATA_DIR
        os.makedirs(face_dir, exist_ok=True)

        expected_files = set()
        updated = False
        for m in members:
            try:
                member_id = m.get('id')
                name = (m.get('name') or '').strip() or '未命名'
                face_url = m.get('face_image')
                if not face_url:
                    continue

                member_folder = os.path.join(face_dir, name)
                os.makedirs(member_folder, exist_ok=True)

                filename = f"cloud_member_{member_id}.jpg" if member_id is not None else "cloud_member.jpg"
                target_path = os.path.join(member_folder, filename)
                expected_files.add(os.path.abspath(target_path))

                r = self.cloud_comm.session.get(face_url, timeout=15)
                if r.status_code != 200:
                    continue
                content = r.content or b''
                if not content:
                    continue

                old = None
                if os.path.exists(target_path):
                    try:
                        with open(target_path, 'rb') as f:
                            old = f.read()
                    except Exception:
                        old = None

                if old != content:
                    with open(target_path, 'wb') as f:
                        f.write(content)
                    updated = True
            except Exception:
                continue

        try:
            for root, _, files in os.walk(face_dir):
                for fn in files:
                    if not fn.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    if not fn.startswith('cloud_member_') and fn != 'cloud_member.jpg':
                        continue
                    p = os.path.abspath(os.path.join(root, fn))
                    if p not in expected_files:
                        try:
                            os.remove(p)
                            updated = True
                        except Exception:
                            pass

            for name in os.listdir(face_dir):
                d = os.path.join(face_dir, name)
                if os.path.isdir(d) and not os.listdir(d):
                    try:
                        os.rmdir(d)
                    except Exception:
                        pass
        except Exception:
            pass

        if updated and self.recognizer and hasattr(self.recognizer, 'reload_known_faces'):
            try:
                self.recognizer.reload_known_faces(force_rebuild=True)
            except Exception:
                pass

        return True

    def sync_if_needed(self) -> bool:
        """
        检查是否需要同步数据

        Returns:
            是否执行了同步
        """
        if self.last_sync_time is None:
            return self.sync_data()

        elapsed = (datetime.now() - self.last_sync_time).total_seconds()
        if elapsed >= self.sync_interval:
            return self.sync_data()

        return False

    def sync_data(self) -> bool:
        """
        执行数据同步

        Returns:
            是否同步成功
        """
        logger.info("开始同步数据...")

        try:
            self.sync_members_if_needed(min_interval_sec=60)

            # 上传访客记录
            if os.path.exists(self.visitors_file):
                self._upload_visitors()

            # 上传访问日志
            if os.path.exists(self.logs_file):
                self._upload_logs()

            self.last_sync_time = datetime.now()
            logger.info("数据同步完成")
            return True

        except Exception as e:
            logger.error(f"数据同步失败：{e}")
            return False

    def _upload_visitors(self):
        """上传访客记录"""
        with open(self.visitors_file, 'r', encoding='utf-8') as f:
            visitors = json.load(f)

        items = visitors.get('visitors', []) if isinstance(visitors, dict) else []
        if not self.cloud_comm:
            logger.info("未配置云端通信，跳过访客记录上传")
            return

        success = 0
        attempted = 0
        remaining = []
        max_upload_per_sync = 1
        for idx, v in enumerate(items):
            if attempted >= max_upload_per_sync:
                remaining.extend(items[idx:])
                break
            try:
                t = (v.get('type') or '').strip().lower()
                if t in ('family',):
                    visitor_type = 'family'
                else:
                    visitor_type = 'stranger'
                member_name = v.get('name') if visitor_type == 'family' else None
                confidence = float(v.get('confidence') or 0.0)
                photo_path = v.get('face_image_path')
                attempted += 1
                vid = self.cloud_comm.upload_visitor(
                    visitor_type=visitor_type,
                    member_name=member_name,
                    confidence=confidence,
                    photo_path=photo_path
                )
                if vid:
                    success += 1
                else:
                    remaining.append(v)
            except Exception:
                remaining.append(v)

        logger.info(f"访客记录上传完成：{success}/{attempted}")
        try:
            if isinstance(visitors, dict):
                visitors['visitors'] = remaining
            else:
                visitors = {'visitors': remaining}
            with open(self.visitors_file, 'w', encoding='utf-8') as f:
                json.dump(visitors, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _upload_logs(self):
        """上传访问日志"""
        with open(self.logs_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)

        logger.info(f"准备上传 {len(logs.get('logs', []))} 条访问日志")

    def download_data(self, data_type: str) -> Optional[Dict]:
        """
        从服务器下载数据

        Args:
            data_type: 数据类型 ('visitors' 或 'logs')

        Returns:
            下载的数据，失败返回 None
        """
        logger.info(f"请求下载 {data_type} 数据...")
        # 实际实现需要通过网络请求
        return None

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        return {
            'server': f"{self.server_host}:{self.server_port}",
            'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_interval': self.sync_interval,
            'visitors_file_exists': os.path.exists(self.visitors_file),
            'logs_file_exists': os.path.exists(self.logs_file)
        }


if __name__ == "__main__":
    # 测试
    sync = DataSync()
    print(f"同步状态：{sync.get_sync_status()}")
