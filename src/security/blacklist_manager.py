import os
import pickle
import logging
from typing import Dict, Optional, List

import cv2
import numpy as np

from config.settings import Config


logger = logging.getLogger(__name__)


class BlacklistManager:
    def __init__(self, face_recognizer, cloud_comm, threshold: Optional[float] = None):
        self.face_recognizer = face_recognizer
        self.cloud_comm = cloud_comm
        self.threshold = threshold if threshold is not None else getattr(face_recognizer, 'threshold', 0.5)
        self.cache_file = os.path.join(Config.MODEL_DATA_DIR, 'blacklist_cache.pkl')
        self.items: Dict[int, Dict] = {}
        self.last_sync: Optional[str] = None
        os.makedirs(Config.MODEL_DATA_DIR, exist_ok=True)
        self._load_cache()

    def _load_cache(self):
        if not os.path.exists(self.cache_file):
            return
        try:
            with open(self.cache_file, 'rb') as f:
                data = pickle.load(f)
            self.items = data.get('items') or {}
            self.last_sync = data.get('last_sync')
        except Exception as e:
            logger.error(f"加载黑名单缓存失败：{e}")

    def _save_cache(self):
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump({'items': self.items, 'last_sync': self.last_sync}, f)
        except Exception as e:
            logger.error(f"保存黑名单缓存失败：{e}")

    def sync(self) -> int:
        items = self.cloud_comm.get_blacklist(since=self.last_sync)
        if not items:
            return 0

        updated = 0
        for it in items:
            try:
                bid = int(it.get('id'))
            except Exception:
                continue

            photo_url = it.get('photo')
            name = it.get('name') or f"blacklist_{bid}"
            updated_at = it.get('updated_at') or self.last_sync

            embedding = None
            if photo_url:
                embedding = self._download_and_embed(photo_url)

            if embedding is not None:
                self.items[bid] = {
                    'id': bid,
                    'name': name,
                    'embedding': embedding,
                    'updated_at': updated_at,
                    'photo_url': photo_url
                }
                updated += 1

            if updated_at:
                if not self.last_sync or str(updated_at) > str(self.last_sync):
                    self.last_sync = str(updated_at)

        if updated:
            self._save_cache()
        return updated

    def _download_and_embed(self, url: str):
        try:
            r = self.cloud_comm.session.get(url, timeout=20)
            if r.status_code != 200:
                return None
            data = np.frombuffer(r.content, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                return None
            return self.face_recognizer._get_embedding(img)
        except Exception as e:
            logger.error(f"下载黑名单照片失败：{e}")
            return None

    def match(self, face_img) -> Dict:
        result = {
            'hit': False,
            'id': None,
            'name': None,
            'confidence': 0.0,
            'distance': float('inf')
        }

        if face_img is None or not self.items:
            return result

        emb = self.face_recognizer._get_embedding(face_img)
        if emb is None:
            return result

        min_d = float('inf')
        best_id = None
        best_name = None
        for bid, it in self.items.items():
            known = it.get('embedding')
            if known is None:
                continue
            d = float(np.linalg.norm(emb - known))
            if d < min_d:
                min_d = d
                best_id = bid
                best_name = it.get('name')

        result['distance'] = min_d
        if best_id is not None and min_d < self.threshold:
            result['hit'] = True
            result['id'] = best_id
            result['name'] = best_name
            result['confidence'] = max(0.0, 1.0 - min_d / self.threshold)
        return result

