"""
Flask API 服务器 - 为安卓 APP 提供数据接口
支持设备注册、远程控制、实时通信

功能定位索引（从“我要找的功能”反查到代码位置）：
- 认证登录/注册：/api/auth/login, /api/auth/register, /api/auth/refresh（Android：LoginActivity/RegisterActivity -> ApiService）
- 设备管理/心跳/状态：/api/device/register, /api/device/heartbeat, /api/device/status（设备端：CloudCommunication）
- 活体检测复核：/api/liveness/check（设备端：CloudCommunication.check_liveness -> main.py:_check_liveness）
- 访客记录上传/查询/删除：/api/visitor/upload, /api/visitor/list, /api/visitor/<id>/delete（设备端上传，Android 端查看）
- 远程控制命令创建：/api/control/unlock|snapshot|alert|speak|restart（Android 端发起；云端入库并投递；设备端 RemoteController 执行）
- 命令结果回执：/api/command/result（设备端执行后回传，更新 remote_commands 状态）
- 报警管理：/api/alert/list, /api/alert/handle（Android 查看与处理）
- 统计看板：/api/stats（Android 首页统计卡片）
- 成员/照片上传：/api/member/*（Android 成员管理；设备端同步成员库）
- 黑名单：/api/blacklist/*（当前 UI 可能未启用；设备端可同步并在本地拦截）

工程约定（便于快速定位与排障）：
- 路由层（Controller）集中在本文件：按“模块分区注释”划分（用户认证/设备管理/访客管理/远程控制/统计/成员管理等）
- 数据落库：MySQL（pymysql）；缓存与防重放：Redis；命令推送：MQTT（publish_command）
"""

import os
import json
import base64
import logging
import hmac
import hashlib
import secrets
import time
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import pymysql
import redis
import bcrypt
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from mqtt_publisher import publish_command

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smart-doorbell-2026-secret')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-2026')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)

jwt = JWTManager(app)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库配置
DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'doorbell'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'smart_doorbell'),
    'charset': 'utf8mb4'
}

# Redis 配置
redis_client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    password=os.environ.get('REDIS_PASSWORD', None) or None,
    db=0,
    decode_responses=True
)

# 上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

_LAST_VISITOR_CLEANUP_TS = 0.0


def _safe_remove_upload(rel_path: Optional[str]) -> bool:
    if not rel_path:
        return False
    p = _normalize_path(str(rel_path)).lstrip('/')
    if '..' in p.split('/'):
        return False
    abs_path = os.path.abspath(os.path.join(UPLOAD_DIR, p))
    upload_root = os.path.abspath(UPLOAD_DIR)
    if not abs_path.startswith(upload_root + os.sep):
        return False
    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
            return True
    except Exception:
        return False
    return False


def _cleanup_old_visitors(conn, days: int = 7, max_rows: int = 2000, min_interval_sec: int = 3600) -> int:
    global _LAST_VISITOR_CLEANUP_TS
    now_ts = time.time()
    if now_ts - _LAST_VISITOR_CLEANUP_TS < float(min_interval_sec):
        return 0
    _LAST_VISITOR_CLEANUP_TS = now_ts

    cutoff = datetime.now() - timedelta(days=days)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        'SELECT id, photo_path FROM visitors WHERE created_at < %s ORDER BY created_at ASC LIMIT %s',
        (cutoff, int(max_rows))
    )
    rows = cursor.fetchall() or []
    if not rows:
        return 0

    ids = [r.get('id') for r in rows if r.get('id') is not None]
    photo_paths = [r.get('photo_path') for r in rows if r.get('photo_path')]

    if ids:
        ph = ','.join(['%s'] * len(ids))
        cursor2 = conn.cursor()
        cursor2.execute(f'DELETE FROM alarm_logs WHERE visitor_id IN ({ph})', ids)
        cursor2.execute(f'DELETE FROM visitors WHERE id IN ({ph})', ids)
        conn.commit()

    removed = 0
    for p in photo_paths:
        if _safe_remove_upload(p):
            removed += 1

    return len(ids)

def _normalize_path(p: str) -> str:
    return p.replace('\\', '/')


def _to_upload_relpath(stored_path: Optional[str]) -> Optional[str]:
    if not stored_path:
        return None

    p = _normalize_path(str(stored_path))
    upload_dir = _normalize_path(UPLOAD_DIR).rstrip('/')

    if p.startswith('http://') or p.startswith('https://'):
        idx = p.find('/uploads/')
        if idx != -1:
            return p[idx + len('/uploads/'):]
        return None

    if not p.startswith('/'):
        first = p.split('/', 1)[0]
        if not (len(first) == 2 and first[1] == ':'):
            return p.lstrip('/')

    if p.startswith(upload_dir + '/'):
        return p[len(upload_dir) + 1:]

    legacy_prefix = '/home/smart_doorbell/server/uploads/'
    if p.startswith(legacy_prefix):
        return p[len(legacy_prefix):]

    idx = p.find('/uploads/')
    if idx != -1:
        return p[idx + len('/uploads/'):]

    return None


def _build_upload_url(rel_path: str) -> str:
    base = request.host_url.rstrip('/')
    rel = rel_path.lstrip('/')
    return f"{base}/uploads/{rel}"

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _liveness_heuristic(frames: list) -> Dict:
    try:
        from PIL import Image
        from PIL import ImageChops, ImageStat
        import io
    except Exception as e:
        return {'live': False, 'score': 0.0, 'reason': f'heuristic unavailable: {e}'}

    imgs = []
    for b64 in frames:
        if not b64:
            continue
        try:
            raw = base64.b64decode(b64.split(',')[1] if ',' in b64 else b64)
            im = Image.open(io.BytesIO(raw)).convert('L').resize((64, 64))
            imgs.append(im)
        except Exception:
            continue

    if len(imgs) < 2:
        return {'live': False, 'score': 0.0, 'reason': 'frames too few'}

    diffs = []
    for i in range(1, len(imgs)):
        diff_img = ImageChops.difference(imgs[i], imgs[i - 1])
        mean_diff = float((ImageStat.Stat(diff_img).mean or [0.0])[0])
        diffs.append(mean_diff)

    avg = float(sum(diffs) / max(len(diffs), 1))
    transitions = sum(1 for d in diffs if d >= 2.0)
    live = (transitions >= 2) and (avg >= 2.0)
    score = max(0.0, min(1.0, (avg / 10.0) * (float(transitions) / 4.0)))
    reason = f'avg_diff={avg:.2f}, transitions={transitions}'
    return {'live': bool(live), 'score': score, 'reason': reason}


def _liveness_openai(frames: list) -> Optional[Dict]:
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    base_url = (os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')
    model = os.environ.get('OPENAI_VISION_MODEL') or 'gpt-4o-mini'

    images = []
    for b64 in frames[:5]:
        if not b64:
            continue
        if b64.startswith('data:'):
            url = b64
        else:
            url = f"data:image/jpeg;base64,{b64}"
        images.append({'type': 'image_url', 'image_url': {'url': url}})

    if len(images) < 2:
        return None

    prompt = (
        "你是门禁系统的安全活体检测裁判。输入是同一人的连续多帧人脸图像（可能为真人、纸质照片、手机屏幕翻拍、或其它伪造）。"
        "请非常保守：只有在多帧中能看到非刚体的细微变化（如眨眼/眼睑变化、嘴唇或表情变化、面部肌肉细微运动、真实的三维光影随姿态变化）时才判定真人。"
        "如果多帧主要表现为刚体平移/旋转、整体亮度变化、或虽然清晰但缺乏真实微表情与三维变化，应判定为照片/屏幕翻拍（live=false）。"
        "只输出 JSON：{\"live\":true|false,\"score\":0-1,\"attack_type\":\"none|photo|screen|mask|unknown\",\"reason\":\"...\"}。"
        "若不确定，倾向于 live=false。"
    )

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': prompt}] + images
            }
        ],
        'max_tokens': 120,
        'temperature': 0.0
    }

    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={'Authorization': f"Bearer {api_key}", 'Content-Type': 'application/json'},
            json=payload,
            timeout=20
        )
        j = r.json()
        txt = (((j.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()
        if not txt:
            return None
        try:
            obj = json.loads(txt)
        except Exception:
            start = txt.find('{')
            end = txt.rfind('}')
            if start != -1 and end != -1 and end > start:
                obj = json.loads(txt[start:end + 1])
            else:
                return None

        live = bool(obj.get('live'))
        score = obj.get('score')
        try:
            score = float(score)
        except Exception:
            score = 0.5
        score = max(0.0, min(1.0, score))
        reason = str(obj.get('reason') or '')
        return {'live': live, 'score': score, 'reason': reason, 'provider': 'openai'}
    except Exception as e:
        logger.warning(f"OpenAI 活体检测失败：{e}")
        return None

def _liveness_qwen(frames: list) -> Optional[Dict]:
    api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWEN_API_KEY')
    if not api_key:
        return None

    base_url = (os.environ.get('QWEN_BASE_URL') or 'https://dashscope.aliyuncs.com/compatible-mode/v1').rstrip('/')
    model = os.environ.get('QWEN_VISION_MODEL') or 'qwen-vl-plus'

    images = []
    for b64 in frames[:5]:
        if not b64:
            continue
        url = f"data:image/jpeg;base64,{b64}"
        images.append({'type': 'image_url', 'image_url': {'url': url}})

    if len(images) < 2:
        return None

    prompt = (
        "你是门禁系统的安全活体检测裁判。输入是同一人的连续多帧人脸图像（可能为真人、纸质照片、手机屏幕翻拍、或其它伪造）。"
        "请非常保守：只有在多帧中能看到非刚体的细微变化（如眨眼/眼睑变化、嘴唇或表情变化、面部肌肉细微运动、真实的三维光影随姿态变化）时才判定真人。"
        "如果多帧主要表现为刚体平移/旋转、整体亮度变化、或虽然清晰但缺乏真实微表情与三维变化，应判定为照片/屏幕翻拍（live=false）。"
        "只输出 JSON：{\"live\":true|false,\"score\":0-1,\"attack_type\":\"none|photo|screen|mask|unknown\",\"reason\":\"...\"}。"
        "若不确定，倾向于 live=false。"
    )

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': [{'type': 'text', 'text': prompt}] + images
            }
        ],
        'response_format': {'type': 'json_object'},
        'max_tokens': 120,
        'temperature': 0.0
    }

    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={'Authorization': f"Bearer {api_key}", 'Content-Type': 'application/json'},
            json=payload,
            timeout=20
        )
        j = r.json()
        txt = (((j.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()
        if not txt:
            return None
        try:
            obj = json.loads(txt)
        except Exception:
            start = txt.find('{')
            end = txt.rfind('}')
            if start != -1 and end != -1 and end > start:
                obj = json.loads(txt[start:end + 1])
            else:
                return None
        live = bool(obj.get('live'))
        score = obj.get('score')
        try:
            score = float(score)
        except Exception:
            score = 0.5
        score = max(0.0, min(1.0, score))
        reason = str(obj.get('reason') or '')
        attack_type = str(obj.get('attack_type') or '')
        return {'live': live, 'score': score, 'reason': reason, 'attack_type': attack_type, 'provider': 'qwen'}
    except Exception as e:
        logger.warning(f"通义千问 活体检测失败：{e}")
        return None


def _verify_device_signature(device_id: str, device_token: str) -> Optional[str]:
    ts = request.headers.get('X-Device-Timestamp')
    nonce = request.headers.get('X-Device-Nonce')
    sig = request.headers.get('X-Device-Signature')

    if not ts or not nonce or not sig:
        return '缺少设备鉴权头'

    try:
        ts_int = int(ts)
    except Exception:
        return '设备时间戳格式错误'

    now = int(datetime.now().timestamp())
    if abs(now - ts_int) > 120:
        return '设备时间戳超出允许范围'

    nonce_key = f"device_nonce:{device_id}:{nonce}"
    try:
        if not redis_client.set(nonce_key, '1', nx=True, ex=300):
            return '设备请求重复'
    except Exception:
        return '设备鉴权服务不可用'

    body = request.get_data() or b''
    body_hash = _sha256_hex(body)
    msg = f"{device_id}|{ts}|{nonce}|{body_hash}".encode('utf-8')
    expected = hmac.new(device_token.encode('utf-8'), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return '设备签名校验失败'

    return None


def _require_device_auth(device_id_from_body: Optional[str] = None) -> Dict:
    header_device_id = request.headers.get('X-Device-Id')
    device_id = header_device_id or device_id_from_body
    if not device_id:
        return {'ok': False, 'error': '设备 ID 必填'}

    if header_device_id and device_id_from_body and header_device_id != device_id_from_body:
        return {'ok': False, 'error': '设备 ID 不一致'}

    conn = get_db_connection()
    if not conn:
        return {'ok': False, 'error': '数据库连接失败'}

    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT device_token FROM devices WHERE device_id = %s', (device_id,))
        row = cursor.fetchone()
        if not row:
            return {'ok': False, 'error': '设备未注册'}

        device_token = row.get('device_token')
        if not device_token:
            return {'ok': False, 'error': '设备未绑定密钥'}

        err = _verify_device_signature(device_id, device_token)
        if err:
            return {'ok': False, 'error': err}

        return {'ok': True, 'device_id': device_id, 'conn': conn}
    except Exception as e:
        try:
            conn.close()
        finally:
            pass
        return {'ok': False, 'error': str(e)}


# 静态文件服务（上传的照片）
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传文件的访问"""
    return send_from_directory(UPLOAD_DIR, filename)


# ==================== 数据库连接 ====================

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败：{e}")
        return None


def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                phone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # 家庭表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS families (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                owner_id INT NOT NULL,
                address VARCHAR(255),
                device_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 家庭成员表（关联 users 表，旧版）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS family_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                family_id INT NOT NULL,
                user_id INT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (family_id) REFERENCES families(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 成员表（直接存储成员信息，新版，用于人脸识别）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                family_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                face_image LONGBLOB,
                face_image_path VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (family_id) REFERENCES families(id)
            )
        ''')

        # 设备表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) UNIQUE NOT NULL,
                device_name VARCHAR(100),
                user_id INT,
                device_type VARCHAR(50),
                firmware_version VARCHAR(20),
                last_heartbeat TIMESTAMP,
                is_online BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 访客记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visitors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50),
                visitor_type ENUM('family', 'stranger') NOT NULL,
                member_name VARCHAR(100),
                confidence FLOAT,
                photo_path VARCHAR(255),
                photo_data LONGBLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        ''')

        # 开门记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50),
                user_id INT,
                member_name VARCHAR(100),
                action ENUM('unlock', 'lock', 'remote_unlock') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 报警记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alarm_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50),
                visitor_id INT,
                reason VARCHAR(255) NOT NULL,
                duration INT DEFAULT 0,
                photo_path VARCHAR(255),
                handled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                FOREIGN KEY (visitor_id) REFERENCES visitors(id)
            )
        ''')

        # 远程命令表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS remote_commands (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) NOT NULL,
                command_type ENUM('unlock', 'alert', 'speak', 'snapshot', 'restart') NOT NULL,
                command_data TEXT,
                status ENUM('pending', 'delivered', 'executed', 'failed') DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP NULL,
                executed_at TIMESTAMP NULL,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        ''')

        try:
            cursor.execute("ALTER TABLE devices ADD COLUMN device_token VARCHAR(64) NULL")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE remote_commands ADD COLUMN delivered_at TIMESTAMP NULL")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE remote_commands MODIFY COLUMN status ENUM('pending','delivered','executed','failed') DEFAULT 'pending'")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE remote_commands MODIFY COLUMN command_type ENUM('unlock','alert','speak','snapshot','restart') NOT NULL")
        except Exception:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist_faces (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) NULL,
                user_id INT NULL,
                name VARCHAR(100) NOT NULL,
                photo_path VARCHAR(255) NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_device_id (device_id),
                INDEX idx_updated_at (updated_at)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) NOT NULL,
                blacklist_id INT NULL,
                confidence FLOAT DEFAULT 0,
                photo_path VARCHAR(255) NULL,
                video_path VARCHAR(255) NULL,
                location VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_device_id (device_id),
                INDEX idx_created_at (created_at)
            )
        ''')

        conn.commit()
        logger.info("数据库表初始化完成")
        return True

    except Exception as e:
        logger.error(f"数据库表创建失败：{e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ==================== 通用接口 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'server': 'CLAUDE Smart Doorbell Cloud'
    })


# ==================== 用户认证 ====================

# 开发者调试密码（用于重置测试用户密码）
DEVELOPER_SECRET = "dev-secret-2026"


@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        phone = data.get('phone')

        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码必填'}), 400

        # 用户名格式校验
        if len(username) < 3 or len(username) > 20:
            return jsonify({'success': False, 'error': '用户名长度 3-20 个字符'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少 6 位'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查用户是否存在
        cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': '用户名已存在'}), 400

        # 使用 bcrypt 加密密码
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('''
            INSERT INTO users (username, password_hash, email, phone)
            VALUES (%s, %s, %s, %s)
        ''', (username, password_hash, email or None, phone or None))

        user_id = cursor.lastrowid
        conn.commit()

        # 生成 token
        access_token = create_access_token(identity=str(user_id))

        # 返回与登录一致的格式
        return jsonify({
            'success': True,
            'data': {
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'phone': phone
                },
                'access_token': access_token,
                'refresh_token': access_token  # 简化：refresh token 同 access token
            }
        })

    except Exception as e:
        logger.error(f"注册失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    conn = None
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码必填'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s AND is_active = TRUE', (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

        # 使用 bcrypt 验证密码
        password_hash = user['password_hash']
        # 处理旧的 werkzeug 哈希格式（以 sha256:开头）
        if password_hash.startswith('sha256:') or password_hash.startswith('pbkdf2:'):
            # 旧的 werkzeug 哈希，需要重置密码
            logger.warning(f"用户 {username} 使用旧密码哈希格式，需要重置密码")
            return jsonify({'success': False, 'error': '密码格式不兼容，请联系管理员重置密码'}), 401

        try:
            password_match = bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            password_match = False

        if not password_match:
            return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

        # 生成 token
        access_token = create_access_token(identity=str(user['id']))
        refresh_token = create_access_token(identity=str(user['id']))

        return jsonify({
            'success': True,
            'data': {
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'phone': user['phone'],
                    'avatar': None,
                    'created_at': user['created_at'].strftime('%Y-%m-%d %H:%M:%S') if user.get('created_at') else ''
                },
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        })

    except Exception as e:
        logger.error(f"登录失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required()
def refresh_token():
    """刷新 Token"""
    try:
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user)
        return jsonify({'success': True, 'access_token': new_token})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/family/list', methods=['GET'])
@jwt_required()
def get_family_list():
    """获取用户的家庭列表"""
    try:
        user_id = int(get_jwt_identity())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 查询用户所属的家庭（如果家庭表存在）
        cursor.execute('''
            SELECT id, name, owner_id, address, created_at
            FROM families
            WHERE owner_id = %s OR id IN (
                SELECT family_id FROM family_members WHERE user_id = %s
            )
        ''', (user_id, user_id))

        families = cursor.fetchall()

        # 如果用户没有家庭，自动创建一个
        if not families:
            default_name = f"{user_id} 的家庭"
            cursor.execute('''
                INSERT INTO families (name, owner_id)
                VALUES (%s, %s)
            ''', (default_name, user_id))
            conn.commit()

            family_id = cursor.lastrowid
            # 添加成员关系
            cursor.execute('''
                INSERT INTO family_members (family_id, user_id)
                VALUES (%s, %s)
            ''', (family_id, user_id))
            conn.commit()

            families = [{
                'id': family_id,
                'name': default_name,
                'owner_id': user_id,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }]

        return jsonify({
            'success': True,
            'data': {
                'families': families
            }
        })

    except pymysql.err.ProgrammingError as e:
        # 表不存在时，自动创建家庭表并返回默认家庭
        logger.warning(f"家庭表不存在，正在创建：{e}")
        return _create_default_family(user_id)
    except Exception as e:
        logger.error(f"获取家庭列表失败：{e}")
        # 返回空列表而不是错误
        return jsonify({
            'success': True,
            'data': {
                'families': []
            }
        }), 200
    finally:
        if 'conn' in locals() and conn:
            conn.close()


def _create_default_family(user_id):
    """创建家庭表并返回默认家庭"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()

        # 创建家庭表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS families (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                owner_id INT NOT NULL,
                address VARCHAR(255),
                device_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建家庭成员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS family_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                family_id INT NOT NULL,
                user_id INT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (family_id) REFERENCES families(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # 创建默认家庭
        default_name = f"{user_id} 的家庭"
        cursor.execute('''
            INSERT INTO families (name, owner_id)
            VALUES (%s, %s)
        ''', (default_name, user_id))

        family_id = cursor.lastrowid

        # 添加成员关系
        cursor.execute('''
            INSERT INTO family_members (family_id, user_id)
            VALUES (%s, %s)
        ''', (family_id, user_id))

        conn.commit()

        return jsonify({
            'success': True,
            'data': {
                'families': [{
                    'id': family_id,
                    'name': default_name,
                    'owner_id': user_id,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }]
            }
        })

    except Exception as e:
        logger.error(f"创建家庭表失败：{e}")
        return jsonify({
            'success': True,
            'data': {
                'families': []
            }
        }), 200
    finally:
        if 'conn' in locals() and conn:
            conn.close()


# ==================== 开发者调试接口（仅开发环境） ====================

@app.route('/api/dev/users', methods=['GET'])
def dev_list_users():
    """
    【开发者专用】查询所有用户信息
    仅限开发调试使用，生产环境请禁用！
    """
    try:
        # 简单的开发者令牌验证（实际项目中应使用更严格的认证）
        dev_token = request.headers.get('X-Dev-Token')
        if dev_token != DEVELOPER_SECRET:
            return jsonify({'success': False, 'error': '未授权访问'}), 401

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('''
            SELECT id, username, email, phone, created_at, is_active
            FROM users
            ORDER BY id DESC
        ''')
        users = cursor.fetchall()

        return jsonify({
            'success': True,
            'users': users,
            'total': len(users)
        })

    except Exception as e:
        logger.error(f"开发者接口查询失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/dev/reset-password', methods=['POST'])
def dev_reset_password():
    """
    【开发者专用】重置用户密码
    仅限开发调试使用，生产环境请禁用！
    """
    try:
        # 验证开发者令牌
        dev_token = request.headers.get('X-Dev-Token')
        if dev_token != DEVELOPER_SECRET:
            return jsonify({'success': False, 'error': '未授权访问'}), 401

        data = request.get_json()
        username = data.get('username')
        new_password = data.get('password')

        if not username or not new_password:
            return jsonify({'success': False, 'error': '用户名和新密码必填'}), 400

        # 生成新的 bcrypt 哈希
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET password_hash = %s
            WHERE username = %s
        ''', (password_hash, username))

        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': '用户不存在'}), 404

        conn.commit()

        return jsonify({
            'success': True,
            'message': f'用户 {username} 密码已重置'
        })

    except Exception as e:
        logger.error(f"密码重置失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 设备管理 ====================

@app.route('/api/device/register', methods=['POST'])
def register_device():
    """设备注册"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        device_name = data.get('device_name', '智能门铃')
        user_id = data.get('user_id')
        device_type = data.get('device_type', 'raspberry_pi_4b')
        firmware_version = data.get('firmware_version', '1.0.0')

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查设备是否已注册
        cursor.execute('SELECT id, device_token FROM devices WHERE device_id = %s', (device_id,))
        existing = cursor.fetchone()
        if existing:
            device_token = existing.get('device_token')
            if not device_token:
                device_token = secrets.token_hex(32)
                cursor2 = conn.cursor()
                cursor2.execute('UPDATE devices SET device_token=%s WHERE device_id=%s', (device_token, device_id))
                conn.commit()
            # 更新设备信息
            cursor2 = conn.cursor()
            cursor2.execute('''
                UPDATE devices SET device_name = %s, device_type = %s,
                firmware_version = %s, last_heartbeat = NOW(), is_online = TRUE
                WHERE device_id = %s
            ''', (device_name, device_type, firmware_version, device_id))
            conn.commit()
            return jsonify({'success': True, 'message': '设备信息已更新', 'device_token': device_token})

        # 新设备注册
        device_token = secrets.token_hex(32)
        cursor2 = conn.cursor()
        cursor2.execute('''
            INSERT INTO devices (device_id, device_name, user_id, device_type, firmware_version, is_online, device_token)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        ''', (device_id, device_name, user_id, device_type, firmware_version, device_token))

        conn.commit()
        logger.info(f"设备注册成功：{device_id}")

        return jsonify({'success': True, 'message': '设备注册成功', 'device_token': device_token})

    except Exception as e:
        logger.error(f"设备注册失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/device/heartbeat', methods=['POST'])
def device_heartbeat():
    """设备心跳"""
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')

        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        conn = auth['conn']

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('''
            UPDATE devices SET last_heartbeat = NOW(), is_online = TRUE
            WHERE device_id = %s
        ''', (device_id,))
        conn.commit()

        # 检查是否有待执行的远程命令
        cursor.execute('''
            SELECT * FROM remote_commands
            WHERE device_id = %s AND status = 'pending'
            ORDER BY created_at ASC LIMIT 1
        ''', (device_id,))
        command = cursor.fetchone()

        result = {'success': True, 'online': True}
        if command:
            result['command'] = {
                'id': command['id'],
                'type': command['command_type'],
                'data': json.loads(command['command_data']) if command['command_data'] else {}
            }
            # 标记命令为已下发
            cursor.execute('''
                UPDATE remote_commands SET status = 'delivered', delivered_at = NOW()
                WHERE id = %s
            ''', (command['id'],))
            conn.commit()

        return jsonify(result)

    except Exception as e:
        logger.error(f"心跳处理失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/command/result', methods=['POST'])
def command_result():
    try:
        data = request.get_json() or {}
        command_id = data.get('command_id')
        success = bool(data.get('success'))
        result_text = data.get('result', '')
        device_id = data.get('device_id')

        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        conn = auth['conn']
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if not command_id:
            return jsonify({'success': False, 'error': 'command_id 必填'}), 400

        cursor.execute('SELECT device_id FROM remote_commands WHERE id=%s', (command_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'error': '命令不存在'}), 404
        if row.get('device_id') != auth['device_id']:
            return jsonify({'success': False, 'error': '无权上报此命令'}), 403

        status = 'executed' if success else 'failed'
        cursor2 = conn.cursor()
        cursor2.execute(
            'UPDATE remote_commands SET status=%s, result=%s, executed_at=NOW() WHERE id=%s',
            (status, result_text, command_id)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"命令结果上报失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/device/status', methods=['GET'])
@jwt_required()
def get_device_status():
    """获取设备状态"""
    conn = None
    try:
        user_id = int(get_jwt_identity())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('''
            SELECT id, device_id, device_name, device_type, firmware_version,
                   last_heartbeat, is_online, created_at
            FROM devices WHERE user_id = %s
        ''', (user_id,))

        devices = cursor.fetchall() or []
        for d in devices:
            try:
                d['is_online'] = bool(int(d.get('is_online') or 0))
            except Exception:
                d['is_online'] = False
            for k in ('last_heartbeat', 'created_at'):
                v = d.get(k)
                if hasattr(v, 'strftime'):
                    try:
                        d[k] = v.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        d[k] = str(v)
        return jsonify({'success': True, 'devices': devices})

    except Exception as e:
        logger.error(f"获取设备状态失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 访客管理 ====================

@app.route('/api/liveness/check', methods=['POST'])
def liveness_check():
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')
        frames = data.get('frames') or []
        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400
        if not isinstance(frames, list) or len(frames) < 2:
            return jsonify({'success': False, 'error': 'frames 必须是数组且至少 2 帧'}), 400
        if len(frames) > 5:
            frames = frames[:5]

        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401
        conn = auth['conn']

        cleaned = []
        total_bytes = 0
        for b64 in frames:
            if not b64:
                continue
            s = b64.split(',')[1] if ',' in b64 else b64
            try:
                raw = base64.b64decode(s)
            except Exception:
                continue
            total_bytes += len(raw)
            if len(raw) > 400_000:
                return jsonify({'success': False, 'error': '单帧过大'}), 400
            cleaned.append(base64.b64encode(raw).decode('utf-8'))

        if total_bytes > 1_500_000:
            return jsonify({'success': False, 'error': '总图片过大'}), 400

        provider = (os.environ.get('LIVENESS_PROVIDER') or 'heuristic').strip().lower()
        res = None

        if provider in ('qwen', 'dashscope', 'tongyi'):
            h = _liveness_heuristic(cleaned)
            h['provider'] = 'heuristic'
            res = _liveness_qwen(cleaned)
            if res is None:
                h['provider'] = 'heuristic-fallback'
                h['reason'] = f"heuristic({h.get('reason')}), qwen(unavailable)"
                h['frame_count'] = len(cleaned)
                return jsonify({'success': True, **h}), 200

            res['reason'] = f"heuristic({h.get('reason')}), qwen({res.get('reason')})"
            res['frame_count'] = len(cleaned)
            return jsonify({'success': True, **res})

        if provider == 'openai':
            h = _liveness_heuristic(cleaned)
            h['provider'] = 'heuristic'
            res = _liveness_openai(cleaned)
            if res is None:
                h['provider'] = 'heuristic-fallback'
                h['frame_count'] = len(cleaned)
                return jsonify({'success': True, **h})
            res['reason'] = f"heuristic({h.get('reason')}), openai({res.get('reason')})"
            return jsonify({'success': True, **res})

        res = _liveness_heuristic(cleaned)
        res['provider'] = 'heuristic'
        return jsonify({'success': True, **res})
    except Exception as e:
        logger.error(f"活体检测失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/api/visitor/upload', methods=['POST'])
def upload_visitor():
    """上传访客记录"""
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')
        visitor_type = data.get('visitor_type', 'stranger')
        member_name = data.get('member_name')
        confidence = data.get('confidence', 0.0)
        photo_data = data.get('photo_data')  # base64 编码的图片

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        try:
            vt = (visitor_type or '').strip().lower()
        except Exception:
            vt = ''
        if vt in ('family', 'member'):
            visitor_type = 'family'
        elif vt in ('stranger', 'unknown', 'unknown_visitor', 'visitor'):
            visitor_type = 'stranger'
        else:
            visitor_type = 'stranger'

        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        conn = auth['conn']

        cursor = conn.cursor()
        try:
            _cleanup_old_visitors(conn, days=7)
        except Exception:
            pass

        # 处理图片数据
        photo_rel_path = None
        if photo_data:
            filename = secure_filename(f"visitor_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg")
            photo_rel_path = f"visitors/{filename}"
            photo_abs_path = os.path.join(UPLOAD_DIR, photo_rel_path)
            try:
                # 解码并保存 base64 图片
                image_data = base64.b64decode(photo_data.split(',')[1] if ',' in photo_data else photo_data)
                os.makedirs(os.path.join(UPLOAD_DIR, 'visitors'), exist_ok=True)
                with open(photo_abs_path, 'wb') as f:
                    f.write(image_data)
            except Exception as e:
                logger.error(f"保存照片失败：{e}")

        # 插入访客记录
        cursor.execute('''
            INSERT INTO visitors (device_id, visitor_type, member_name, confidence, photo_path)
            VALUES (%s, %s, %s, %s, %s)
        ''', (device_id, visitor_type, member_name, confidence, photo_rel_path))

        visitor_id = cursor.lastrowid
        conn.commit()

        # 如果是陌生访客且停留时间过长，创建报警记录
        if visitor_type == 'stranger':
            cursor.execute('''
                INSERT INTO alarm_logs (device_id, visitor_id, reason)
                VALUES (%s, %s, %s)
            ''', (device_id, visitor_id, '陌生访客停留'))
            conn.commit()

        # 通过 Redis 推送实时通知
        try:
            redis_client.publish('visitor_notifications', json.dumps({
                'visitor_id': visitor_id,
                'visitor_type': visitor_type,
                'member_name': member_name,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            logger.warning(f"Redis 推送失败：{e}")

        return jsonify({'success': True, 'visitor_id': visitor_id})

    except Exception as e:
        logger.error(f"上传访客记录失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/visitor/<int:visitor_id>/delete', methods=['DELETE'])
@jwt_required()
def delete_visitor(visitor_id: int):
    try:
        user_id = int(get_jwt_identity())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('''
            SELECT v.id, v.device_id, v.photo_path
            FROM visitors v
            JOIN devices d ON v.device_id = d.device_id
            WHERE v.id = %s AND d.user_id = %s
        ''', (visitor_id, user_id))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'error': '访客记录不存在或无权删除'}), 404

        cursor2 = conn.cursor()
        cursor2.execute('DELETE FROM alarm_logs WHERE visitor_id = %s', (visitor_id,))
        cursor2.execute('DELETE FROM visitors WHERE id = %s', (visitor_id,))
        conn.commit()

        try:
            _safe_remove_upload(row.get('photo_path'))
        except Exception:
            pass

        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        logger.error(f"删除访客记录失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/visitor/list', methods=['GET'])
@jwt_required()
def get_visitor_list():
    """获取访客列表"""
    try:
        user_id = int(get_jwt_identity())
        family_id = request.args.get('family_id', type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        visitor_type = request.args.get('visitor_type')
        is_alert = request.args.get('is_alert', type=int)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        try:
            _cleanup_old_visitors(conn, days=7)
        except Exception:
            pass

        # 获取用户的家庭 ID（如果没有提供）
        if not family_id:
            cursor.execute('SELECT id FROM families WHERE owner_id = %s', (user_id,))
            result = cursor.fetchone()
            if result:
                family_id = result.get('id')

        if not family_id:
            return jsonify({
                'success': True,
                'data': {
                    'visitors': [],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': 0,
                        'pages': 0
                    }
                }
            })

        # 获取用户设备列表
        cursor.execute('SELECT device_id FROM devices WHERE user_id = %s', (user_id,))
        device_ids = [row.get('device_id') for row in (cursor.fetchall() or []) if row.get('device_id')]
        if not device_ids:
            return jsonify({
                'success': True,
                'data': {
                    'visitors': [],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': 0,
                        'pages': 0
                    }
                }
            })

        # 查询访客记录
        where_clause = '1=1'
        params = []

        if device_ids:
            where_clause += f' AND v.device_id IN ({",".join(["%s"] * len(device_ids))})'
            params.extend(device_ids)

        if visitor_type:
            where_clause += ' AND v.visitor_type = %s'
            params.append(visitor_type)

        # 注意：visitors 表没有 is_alert 字段，暂时移除这个过滤条件
        # if is_alert is not None:
        #     where_clause += ' AND is_alert = %s'
        #     params.append(is_alert)

        # 查询总数（使用别名 v）
        cursor.execute(f'SELECT COUNT(*) as total FROM visitors v WHERE {where_clause}', params)
        total = cursor.fetchone()['total'] or 0

        # 计算分页
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        offset = (page - 1) * per_page

        # 查询访客记录（visitors 表没有 family_id/is_alert 字段，需要从 devices 表关联）
        query = f'''
            SELECT v.id, v.device_id, v.visitor_type, v.member_name,
                   v.photo_path, v.confidence,
                   v.created_at, d.user_id, f.id as family_id
            FROM visitors v
            LEFT JOIN devices d ON v.device_id = d.device_id
            LEFT JOIN families f ON d.user_id = f.owner_id
            WHERE {where_clause}
            ORDER BY v.created_at DESC
            LIMIT %s OFFSET %s
        '''
        params.extend([per_page, offset])

        cursor.execute(query, params)
        visitors = cursor.fetchall()

        # 格式化返回数据
        visitor_list = []
        for v in visitors:
            visitor_list.append({
                'id': v['id'],
                'family_id': v['family_id'],
                'visitor_type': v['visitor_type'],
                'member_name': v['member_name'],
                'capture_image': v['photo_path'],
                'thumbnail': v['photo_path'],
                'confidence': float(v['confidence']) if v['confidence'] else None,
                'duration': 0,
                'is_alert': False,  # 默认值
                'alert_reason': None,
                'created_at': v['created_at'].strftime('%Y-%m-%d %H:%M:%S') if v['created_at'] else ''
            })

        return jsonify({
            'success': True,
            'data': {
                'visitors': visitor_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': total_pages
                }
            }
        })

    except Exception as e:
        logger.error(f"获取访客列表失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 远程控制 ====================

@app.route('/api/control/unlock', methods=['POST'])
@jwt_required()
def remote_unlock():
    """远程开门"""
    conn = None
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()

        # 验证设备属于当前用户
        cursor.execute('SELECT id FROM devices WHERE user_id = %s AND device_id = %s', (user_id, device_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': f'设备不存在或无权控制：{device_id}'}), 404

        # 创建远程开门命令
        cursor.execute('''
            INSERT INTO remote_commands (device_id, command_type, command_data)
            VALUES (%s, %s, %s)
        ''', (device_id, 'unlock', json.dumps({'user_id': user_id, 'timestamp': datetime.now().isoformat()})))

        command_id = cursor.lastrowid
        conn.commit()

        # 记录开门日志
        cursor.execute('''
            INSERT INTO access_logs (device_id, user_id, action)
            VALUES (%s, %s, %s)
        ''', (device_id, user_id, 'remote_unlock'))
        conn.commit()

        logger.info(f"远程开门命令已发送：设备 {device_id}")
        try:
            publish_command(device_id, {'id': command_id, 'type': 'unlock', 'data': {'user_id': user_id}})
        except Exception:
            pass

        return jsonify({'success': True, 'command_id': command_id, 'message': '开门命令已发送'})

    except Exception as e:
        logger.error(f"远程开门失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/control/alert', methods=['POST'])
@jwt_required()
def remote_alert():
    """远程警报"""
    conn = None
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')
        message = data.get('message', '警告！')

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM devices WHERE user_id = %s AND device_id = %s', (user_id, device_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': f'设备不存在或无权控制：{device_id}'}), 404

        # 创建警报命令
        cursor.execute('''
            INSERT INTO remote_commands (device_id, command_type, command_data)
            VALUES (%s, %s, %s)
        ''', (device_id, 'alert', json.dumps({'message': message, 'user_id': user_id})))

        command_id = cursor.lastrowid
        conn.commit()

        try:
            publish_command(device_id, {'id': command_id, 'type': 'alert', 'data': {'message': message, 'user_id': user_id}})
        except Exception:
            pass

        return jsonify({'success': True, 'command_id': command_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/control/speak', methods=['POST'])
@jwt_required()
def remote_speak():
    """远程对讲"""
    conn = None
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')
        message = data.get('message')

        if not device_id or not message:
            return jsonify({'success': False, 'error': '设备 ID 和消息必填'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM devices WHERE user_id = %s AND device_id = %s', (user_id, device_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': f'设备不存在或无权控制：{device_id}'}), 404

        cursor.execute('''
            INSERT INTO remote_commands (device_id, command_type, command_data)
            VALUES (%s, %s, %s)
        ''', (device_id, 'speak', json.dumps({'message': message, 'user_id': user_id})))

        command_id = cursor.lastrowid
        conn.commit()

        try:
            publish_command(device_id, {'id': command_id, 'type': 'speak', 'data': {'message': message, 'user_id': user_id}})
        except Exception:
            pass

        return jsonify({'success': True, 'command_id': command_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/control/snapshot', methods=['POST'])
@jwt_required()
def remote_snapshot():
    """远程抓拍"""
    conn = None
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM devices WHERE user_id = %s AND device_id = %s', (user_id, device_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': f'设备不存在或无权控制：{device_id}'}), 404

        cursor.execute('''
            INSERT INTO remote_commands (device_id, command_type, command_data)
            VALUES (%s, %s, %s)
        ''', (device_id, 'snapshot', json.dumps({'user_id': user_id})))

        command_id = cursor.lastrowid
        conn.commit()

        try:
            publish_command(device_id, {'id': command_id, 'type': 'snapshot', 'data': {'user_id': user_id}})
        except Exception:
            pass

        return jsonify({'success': True, 'command_id': command_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/control/restart', methods=['POST'])
@jwt_required()
def remote_restart():
    """远程重启系统（用于解除黑名单锁定）"""
    conn = None
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id')

        if not device_id:
            return jsonify({'success': False, 'error': '设备 ID 必填'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM devices WHERE user_id = %s AND device_id = %s', (user_id, device_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': f'设备不存在或无权控制：{device_id}'}), 404

        cursor.execute('''
            INSERT INTO remote_commands (device_id, command_type, command_data)
            VALUES (%s, %s, %s)
        ''', (device_id, 'restart', json.dumps({'user_id': user_id})))

        command_id = cursor.lastrowid
        conn.commit()

        try:
            publish_command(device_id, {'id': command_id, 'type': 'restart', 'data': {'user_id': user_id}})
        except Exception:
            pass

        return jsonify({'success': True, 'command_id': command_id})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 报警管理 ====================

@app.route('/api/alert/list', methods=['GET'])
@jwt_required()
def get_alert_list():
    """获取报警列表"""
    try:
        user_id = int(get_jwt_identity())
        limit = request.args.get('limit', 100, type=int)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()

        # 获取用户设备列表
        cursor.execute('SELECT device_id FROM devices WHERE user_id = %s', (user_id,))
        device_ids = [row['device_id'] for row in cursor.fetchall()]

        if not device_ids:
            return jsonify({'success': True, 'alerts': []})

        query = '''
            SELECT a.*, v.visitor_type, v.member_name
            FROM alarm_logs a
            LEFT JOIN visitors v ON a.visitor_id = v.id
            WHERE a.device_id IN ({})
            ORDER BY a.created_at DESC LIMIT %s
        '''.format(','.join(['%s'] * len(device_ids)))

        params = device_ids + [limit]
        cursor.execute(query, params)
        alerts = cursor.fetchall()

        return jsonify({'success': True, 'alerts': alerts})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/alert/handle', methods=['POST'])
@jwt_required()
def handle_alert():
    """处理报警"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        alert_id = data.get('alert_id')
        handled = data.get('handled', True)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE alarm_logs SET handled = %s WHERE id = %s
        ''', (handled, alert_id))

        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 统计接口 ====================

@app.route('/api/stats', methods=['GET'])
@jwt_required()
def get_statistics():
    """获取统计数据"""
    try:
        user_id = int(get_jwt_identity())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 获取用户设备列表
        cursor.execute('SELECT device_id FROM devices WHERE user_id = %s', (user_id,))
        device_ids = [row.get('device_id') for row in (cursor.fetchall() or []) if row.get('device_id')]

        # 初始化统计数据
        data = {
            'period': {
                'days': 7,
                'from': '',
                'to': ''
            },
            'summary': {
                'total_visitors': 0,
                'member_visits': 0,
                'stranger_visits': 0,
                'alert_count': 0,
                'today_visitors': 0
            },
            'daily_stats': []
        }

        if device_ids:
            # 今日访客数量
            cursor.execute('''
                SELECT COUNT(*) as c FROM visitors
                WHERE device_id IN ({}) AND DATE(created_at) = CURDATE()
            '''.format(','.join(['%s'] * len(device_ids))), device_ids)
            today_visitors = (cursor.fetchone() or {}).get('c') or 0

            # 总访客数量（7 天内）
            cursor.execute('''
                SELECT COUNT(*) as c FROM visitors
                WHERE device_id IN ({}) AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            '''.format(','.join(['%s'] * len(device_ids))), device_ids)
            total_visitors = (cursor.fetchone() or {}).get('c') or 0

            # 成员访客数量
            cursor.execute('''
                SELECT COUNT(*) as c FROM visitors
                WHERE device_id IN ({}) AND visitor_type = 'family'
            '''.format(','.join(['%s'] * len(device_ids))), device_ids)
            member_visits = (cursor.fetchone() or {}).get('c') or 0

            # 陌生访客数量
            cursor.execute('''
                SELECT COUNT(*) as c FROM visitors
                WHERE device_id IN ({}) AND visitor_type = 'stranger'
            '''.format(','.join(['%s'] * len(device_ids))), device_ids)
            stranger_visits = (cursor.fetchone() or {}).get('c') or 0

            # 报警数量
            cursor.execute('''
                SELECT COUNT(*) as c FROM alarm_logs
                WHERE device_id IN ({}) AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            '''.format(','.join(['%s'] * len(device_ids))), device_ids)
            alert_count = (cursor.fetchone() or {}).get('c') or 0

            data['summary'] = {
                'total_visitors': total_visitors,
                'member_visits': member_visits,
                'stranger_visits': stranger_visits,
                'alert_count': alert_count,
                'today_visitors': today_visitors
            }

        return jsonify({'success': True, 'data': data})

    except Exception as e:
        logger.error(f"统计接口错误：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ==================== 家庭成员管理 ====================

# 家庭成员表结构（不依赖 users 表，直接存储成员信息）
# CREATE TABLE IF NOT EXISTS members (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     family_id INT NOT NULL,
#     name VARCHAR(100) NOT NULL,
#     face_image LONGBLOB,  # 人脸照片数据
#     face_image_path VARCHAR(255),  # 人脸照片路径
#     is_active BOOLEAN DEFAULT TRUE,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     FOREIGN KEY (family_id) REFERENCES families(id)
# )

@app.route('/api/member/list', methods=['GET'])
@jwt_required()
def get_member_list():
    """获取家庭成员列表"""
    try:
        user_id = int(get_jwt_identity())
        family_id = request.args.get('family_id', type=int)

        if not family_id:
            # 获取用户的家庭 ID
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM families WHERE owner_id = %s', (user_id,))
            result = cursor.fetchone()
            if result:
                family_id = result[0]
            else:
                return jsonify({'success': False, 'error': '没有找到家庭'}), 404
            conn.close()

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查 members 表是否存在，不存在则使用 family_members 表
        try:
            cursor.execute("SELECT COUNT(*) FROM members")
            use_members_table = True
        except:
            use_members_table = False

        if use_members_table:
            # 使用新的 members 表（直接存储成员信息）
            cursor.execute('''
                SELECT id, family_id, name, face_image_path, is_active, created_at
                FROM members
                WHERE family_id = %s AND is_active = 1
            ''', (family_id,))
            members = cursor.fetchall()

            member_list = []
            for m in members:
                face_image_url = None
                rel_path = _to_upload_relpath(m.get('face_image_path'))
                if rel_path:
                    face_image_url = _build_upload_url(rel_path)

                member_list.append({
                    'id': m['id'],
                    'family_id': m['family_id'],
                    'name': m['name'] or '未命名',
                    'face_image': face_image_url,  # 返回图片 URL
                    'is_active': bool(m['is_active']),
                    'created_at': m['created_at'].strftime('%Y-%m-%d %H:%M:%S') if m['created_at'] else ''
                })
        else:
            # 使用旧的 family_members 表（关联 users 表）
            cursor.execute('''
                SELECT fm.id, fm.family_id, u.username as name, 1 as is_active, u.created_at
                FROM family_members fm
                JOIN users u ON fm.user_id = u.id
                WHERE fm.family_id = %s
            ''', (family_id,))
            members = cursor.fetchall()

            member_list = []
            for m in members:
                member_list.append({
                    'id': m['id'],
                    'family_id': m['family_id'],
                    'name': m['name'] or f"用户{m.get('id', '')}",
                    'face_image': None,
                    'is_active': True,
                    'created_at': m['created_at'].strftime('%Y-%m-%d %H:%M:%S') if m['created_at'] else ''
                })

        return jsonify({
            'success': True,
            'data': {
                'family_id': family_id,
                'members': member_list
            }
        })

    except Exception as e:
        logger.error(f"获取成员列表失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/device/members', methods=['GET'])
def get_device_members():
    try:
        device_id = request.headers.get('X-Device-Id') or request.args.get('device_id')
        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        conn = auth['conn']
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute('SELECT user_id FROM devices WHERE device_id = %s', (auth['device_id'],))
        row = cursor.fetchone()
        user_id = row.get('user_id') if row else None
        if not user_id:
            return jsonify({'success': True, 'data': {'family_id': None, 'members': []}})

        cursor.execute('SELECT id FROM families WHERE owner_id = %s', (user_id,))
        fam = cursor.fetchone()
        family_id = fam.get('id') if fam else None
        if not family_id:
            return jsonify({'success': True, 'data': {'family_id': None, 'members': []}})

        try:
            cursor.execute("SELECT COUNT(*) as c FROM members")
            use_members_table = True
        except Exception:
            use_members_table = False

        members = []
        if use_members_table:
            cursor.execute('''
                SELECT id, family_id, name, face_image_path, is_active, created_at
                FROM members
                WHERE family_id = %s AND is_active = 1
            ''', (family_id,))
            rows = cursor.fetchall() or []
            for m in rows:
                rel_path = _to_upload_relpath(m.get('face_image_path'))
                members.append({
                    'id': m.get('id'),
                    'name': (m.get('name') or '').strip() or '未命名',
                    'face_image': _build_upload_url(rel_path) if rel_path else None
                })

        return jsonify({'success': True, 'data': {'family_id': family_id, 'members': members}})

    except Exception as e:
        logger.error(f"设备成员同步失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/member/add', methods=['POST'])
@jwt_required()
def add_member():
    """添加家庭成员（支持上传人脸照片）"""
    try:
        user_id = int(get_jwt_identity())

        # 获取表单数据（支持 multipart/form-data）
        family_id = request.form.get('family_id', type=int)
        name = request.form.get('name', '').strip()

        # 获取上传的图片
        photo_file = request.files.get('photo')
        photo_data = None
        photo_rel_path = None

        if not family_id or not name:
            return jsonify({'success': False, 'error': '参数不完整：需要 family_id 和 name'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()

        # 检查家庭是否存在且属于当前用户
        cursor.execute('SELECT id FROM families WHERE id = %s AND owner_id = %s', (family_id, user_id))
        if not cursor.fetchone():
            cursor.execute('SELECT family_id FROM family_members WHERE family_id = %s AND user_id = %s', (family_id, user_id))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': '无权操作此家庭'}), 403

        # 处理上传的照片
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1] or '.jpg'
            ext = ext.lower()
            filename = secure_filename(f"member_{family_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}")
            photo_rel_path = f"members/{filename}"
            photo_abs_path = os.path.join(UPLOAD_DIR, photo_rel_path)

            # 创建目录
            member_upload_dir = os.path.join(UPLOAD_DIR, 'members')
            os.makedirs(member_upload_dir, exist_ok=True)

            # 保存文件
            photo_file.save(photo_abs_path)
            logger.info(f"成员照片已保存：{photo_abs_path}")

            # 读取图片为 base64 存储到数据库
            with open(photo_abs_path, 'rb') as f:
                photo_data = f.read()

        # 检查 members 表是否存在
        try:
            cursor.execute("SELECT COUNT(*) FROM members")
            use_members_table = True
        except:
            use_members_table = False

        if use_members_table:
            # 使用新的 members 表
            cursor.execute('''
                INSERT INTO members (family_id, name, face_image, face_image_path, is_active)
                VALUES (%s, %s, %s, %s, 1)
            ''', (family_id, name, photo_data, photo_rel_path))
            member_id = cursor.lastrowid

            conn.commit()

            face_image_url = None
            if photo_rel_path:
                face_image_url = _build_upload_url(photo_rel_path)

            return jsonify({
                'success': True,
                'data': {
                    'id': member_id,
                    'family_id': family_id,
                    'name': name,
                    'face_image': face_image_url,
                    'is_active': True,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }), 201
        else:
            # 使用旧的 family_members 表（创建用户并关联）
            # 查找是否已有同名用户
            cursor.execute('SELECT id FROM users WHERE username = %s', (name,))
            target_user = cursor.fetchone()

            if target_user:
                target_user_id = target_user[0]
                cursor.execute('SELECT id FROM family_members WHERE family_id = %s AND user_id = %s', (family_id, target_user_id))
                if cursor.fetchone():
                    return jsonify({'success': False, 'error': '该成员已存在'}), 400

                cursor.execute('INSERT INTO family_members (family_id, user_id) VALUES (%s, %s)', (family_id, target_user_id))
                member_id = cursor.lastrowid
            else:
                # 创建新用户
                import bcrypt
                default_password = '123456'
                hashed = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                cursor.execute(
                    'INSERT INTO users (username, password_hash, is_active) VALUES (%s, %s, 1)',
                    (name, hashed)
                )
                new_user_id = cursor.lastrowid

                cursor.execute('INSERT INTO family_members (family_id, user_id) VALUES (%s, %s)', (family_id, new_user_id))
                member_id = cursor.lastrowid

            conn.commit()

            return jsonify({
                'success': True,
                'data': {
                    'id': member_id,
                    'family_id': family_id,
                    'name': name,
                    'face_image': None,
                    'is_active': True,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }), 201

    except Exception as e:
        logger.error(f"添加成员失败：{e}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


@app.route('/api/blacklist/list', methods=['GET'])
@jwt_required()
def get_blacklist():
    try:
        user_id = int(get_jwt_identity())
        include_inactive = request.args.get('include_inactive', 0, type=int) == 1

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        if include_inactive:
            cursor.execute('SELECT id, name, photo_path, is_active, updated_at FROM blacklist_faces WHERE user_id=%s ORDER BY updated_at DESC', (user_id,))
        else:
            cursor.execute('SELECT id, name, photo_path, is_active, updated_at FROM blacklist_faces WHERE user_id=%s AND is_active=1 ORDER BY updated_at DESC', (user_id,))

        items = []
        for row in cursor.fetchall():
            photo_url = None
            rel = _to_upload_relpath(row.get('photo_path'))
            if rel:
                photo_url = _build_upload_url(rel)
            items.append({
                'id': row['id'],
                'name': row['name'],
                'photo': photo_url,
                'is_active': bool(row.get('is_active')),
                'updated_at': row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if row.get('updated_at') else ''
            })

        return jsonify({'success': True, 'data': {'items': items}})
    except Exception as e:
        logger.error(f"获取黑名单失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/blacklist/add', methods=['POST'])
@jwt_required()
def add_blacklist():
    try:
        user_id = int(get_jwt_identity())
        name = (request.form.get('name') or '').strip()
        photo_file = request.files.get('photo')

        if not name or not photo_file or not photo_file.filename:
            return jsonify({'success': False, 'error': 'name 与 photo 必填'}), 400

        ext = os.path.splitext(photo_file.filename)[1] or '.jpg'
        ext = ext.lower()
        filename = secure_filename(f"blacklist_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}")
        rel_path = f"blacklist/{filename}"
        abs_path = os.path.join(UPLOAD_DIR, rel_path)
        os.makedirs(os.path.join(UPLOAD_DIR, 'blacklist'), exist_ok=True)
        photo_file.save(abs_path)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO blacklist_faces (user_id, name, photo_path, is_active) VALUES (%s, %s, %s, 1)',
            (user_id, name, rel_path)
        )
        blacklist_id = cursor.lastrowid
        conn.commit()

        return jsonify({'success': True, 'data': {'id': blacklist_id, 'photo': _build_upload_url(rel_path)}}), 201
    except Exception as e:
        logger.error(f"添加黑名单失败：{e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/blacklist/<int:blacklist_id>', methods=['DELETE'])
@jwt_required()
def delete_blacklist(blacklist_id: int):
    try:
        user_id = int(get_jwt_identity())
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT id FROM blacklist_faces WHERE id=%s AND user_id=%s', (blacklist_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': '记录不存在'}), 404

        cursor2 = conn.cursor()
        cursor2.execute('UPDATE blacklist_faces SET is_active=0 WHERE id=%s', (blacklist_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除黑名单失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/device/blacklist/list', methods=['GET'])
def device_blacklist_list():
    try:
        device_id = request.headers.get('X-Device-Id') or request.args.get('device_id')
        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        since = request.args.get('since')
        conn = auth['conn']
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT user_id FROM devices WHERE device_id=%s', (auth['device_id'],))
        dev = cursor.fetchone()
        if not dev or not dev.get('user_id'):
            return jsonify({'success': True, 'data': {'items': []}})

        user_id = dev['user_id']
        params = [user_id]
        sql = 'SELECT id, name, photo_path, updated_at FROM blacklist_faces WHERE user_id=%s AND is_active=1'
        if since:
            sql += ' AND updated_at > %s'
            params.append(since)
        sql += ' ORDER BY updated_at ASC LIMIT 5000'
        cursor.execute(sql, params)

        items = []
        for row in cursor.fetchall():
            rel = _to_upload_relpath(row.get('photo_path'))
            photo_url = _build_upload_url(rel) if rel else None
            items.append({
                'id': row['id'],
                'name': row['name'],
                'photo': photo_url,
                'updated_at': row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if row.get('updated_at') else ''
            })

        return jsonify({'success': True, 'data': {'items': items}})
    except Exception as e:
        logger.error(f"设备获取黑名单失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/device/blacklist/event', methods=['POST'])
def device_blacklist_event():
    try:
        device_id = request.headers.get('X-Device-Id') or request.form.get('device_id')
        auth = _require_device_auth(device_id)
        if not auth.get('ok'):
            return jsonify({'success': False, 'error': auth.get('error')}), 401

        blacklist_id = request.form.get('blacklist_id', type=int)
        confidence = request.form.get('confidence', type=float) or 0.0
        location = request.form.get('location')
        photo_file = request.files.get('photo')
        video_file = request.files.get('video')

        conn = auth['conn']
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute('SELECT user_id FROM devices WHERE device_id=%s', (auth['device_id'],))
        dev = cursor.fetchone()
        user_id = dev.get('user_id') if dev else None

        os.makedirs(os.path.join(UPLOAD_DIR, 'blacklist_events'), exist_ok=True)

        photo_rel = None
        if photo_file and photo_file.filename:
            ext = os.path.splitext(photo_file.filename)[1] or '.jpg'
            ext = ext.lower()
            filename = secure_filename(f"blacklist_event_{auth['device_id']}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}")
            photo_rel = f"blacklist_events/{filename}"
            photo_file.save(os.path.join(UPLOAD_DIR, photo_rel))

        video_rel = None
        if video_file and video_file.filename:
            ext = os.path.splitext(video_file.filename)[1] or '.mp4'
            ext = ext.lower()
            filename = secure_filename(f"blacklist_video_{auth['device_id']}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}")
            video_rel = f"blacklist_events/{filename}"
            video_file.save(os.path.join(UPLOAD_DIR, video_rel))

        cursor2 = conn.cursor()
        cursor2.execute(
            'INSERT INTO blacklist_events (device_id, blacklist_id, confidence, photo_path, video_path, location) VALUES (%s,%s,%s,%s,%s,%s)',
            (auth['device_id'], blacklist_id, confidence, photo_rel, video_rel, location)
        )
        event_id = cursor2.lastrowid
        conn.commit()

        reason = '黑名单人员出现'
        if blacklist_id:
            cursor.execute('SELECT name FROM blacklist_faces WHERE id=%s', (blacklist_id,))
            row = cursor.fetchone()
            if row and row.get('name'):
                reason = f"黑名单人员出现：{row['name']}"

        cursor2.execute(
            'INSERT INTO alarm_logs (device_id, visitor_id, reason, photo_path, handled) VALUES (%s, NULL, %s, %s, 0)',
            (auth['device_id'], reason, photo_rel)
        )
        conn.commit()

        try:
            redis_client.publish('visitor_notifications', json.dumps({
                'type': 'blacklist',
                'event_id': event_id,
                'device_id': auth['device_id'],
                'user_id': user_id,
                'blacklist_id': blacklist_id,
                'confidence': confidence,
                'photo': _build_upload_url(photo_rel) if photo_rel else None,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception:
            pass

        return jsonify({'success': True, 'data': {'event_id': event_id}})
    except Exception as e:
        logger.error(f"黑名单事件上报失败：{e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/member/<int:member_id>/delete', methods=['DELETE'])
@jwt_required()
def delete_member(member_id):
    """删除家庭成员"""
    try:
        user_id = int(get_jwt_identity())

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查 members 表是否存在
        try:
            cursor.execute("SELECT COUNT(*) FROM members")
            use_members_table = True
        except:
            use_members_table = False

        if use_members_table:
            # 使用新的 members 表
            cursor.execute('SELECT family_id, face_image_path FROM members WHERE id = %s', (member_id,))
            member = cursor.fetchone()

            if not member:
                return jsonify({'success': False, 'error': '成员不存在'}), 404

            family_id = member['family_id']
            face_image_path = member.get('face_image_path')

            # 检查权限
            cursor.execute('SELECT id FROM families WHERE id = %s AND owner_id = %s', (family_id, user_id))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': '无权操作此家庭'}), 403

            cursor.execute('DELETE FROM members WHERE id = %s', (member_id,))
            try:
                rel = _to_upload_relpath(face_image_path)
                if rel:
                    abs_path = os.path.join(UPLOAD_DIR, rel)
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
            except Exception:
                pass
        else:
            # 使用旧的 family_members 表
            cursor.execute('SELECT family_id, user_id FROM family_members WHERE id = %s', (member_id,))
            member = cursor.fetchone()

            if not member:
                return jsonify({'success': False, 'error': '成员不存在'}), 404

            family_id = member['family_id']
            target_user_id = member['user_id']

            # 检查权限：只有家庭所有者可以删除成员
            cursor.execute('SELECT id FROM families WHERE id = %s AND owner_id = %s', (family_id, user_id))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': '无权操作此家庭'}), 403

            # 不能删除家庭所有者
            if target_user_id == user_id:
                return jsonify({'success': False, 'error': '不能删除家庭所有者'}), 400

            cursor.execute('DELETE FROM family_members WHERE id = %s', (member_id,))

        conn.commit()

        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        logger.error(f"删除成员失败：{e}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


# 新增：更新成员照片（用于人脸识别）
@app.route('/api/member/<int:member_id>/photo', methods=['PUT'])
@jwt_required()
def update_member_photo(member_id):
    """更新成员照片（上传人脸照片用于识别）"""
    try:
        user_id = int(get_jwt_identity())

        # 获取上传的照片
        photo_file = request.files.get('photo')

        if not photo_file or not photo_file.filename:
            return jsonify({'success': False, 'error': '请上传照片文件'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': '数据库连接失败'}), 500

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 检查 members 表是否存在
        try:
            cursor.execute("SELECT COUNT(*) FROM members")
            use_members_table = True
        except:
            use_members_table = False

        if not use_members_table:
            return jsonify({'success': False, 'error': '不支持照片更新，请升级数据库'}), 400

        # 获取成员信息
        cursor.execute('SELECT family_id FROM members WHERE id = %s', (member_id,))
        member = cursor.fetchone()

        if not member:
            return jsonify({'success': False, 'error': '成员不存在'}), 404

        family_id = member['family_id']

        # 检查权限
        cursor.execute('SELECT id FROM families WHERE id = %s AND owner_id = %s', (family_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'error': '无权操作此家庭'}), 403

        # 保存图片
        filename = f"member_{family_id}_{member_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
        filename = secure_filename(filename)
        photo_rel_path = f"members/{filename}"
        photo_abs_path = os.path.join(UPLOAD_DIR, photo_rel_path)

        member_upload_dir = os.path.join(UPLOAD_DIR, 'members')
        os.makedirs(member_upload_dir, exist_ok=True)

        photo_file.save(photo_abs_path)

        # 读取图片为 base64 存储到数据库
        with open(photo_abs_path, 'rb') as f:
            photo_data = f.read()

        # 更新数据库
        cursor.execute('''
            UPDATE members
            SET face_image = %s, face_image_path = %s
            WHERE id = %s
        ''', (photo_data, photo_rel_path, member_id))

        conn.commit()

        return jsonify({
            'success': True,
            'message': '照片已更新',
            'face_image': _build_upload_url(photo_rel_path),
            'face_image_path': photo_rel_path
        })

    except Exception as e:
        logger.error(f"更新照片失败：{e}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()


# ==================== WebSocket 通知 ====================

@app.route('/api/ws/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """获取通知（长轮询模式）"""
    try:
        user_id = int(get_jwt_identity())
        timeout = request.args.get('timeout', 30, type=int)

        # 使用 Redis 发布订阅获取实时通知
        pubsub = redis_client.pubsub()
        pubsub.subscribe('visitor_notifications')

        notifications = []
        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout:
            message = pubsub.get_message(timeout=1)
            if message and message['type'] == 'message':
                notifications.append(json.loads(message['data']))
                break

        pubsub.unsubscribe()

        return jsonify({'success': True, 'notifications': notifications})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 初始化 ====================

if __name__ == '__main__':
    logger.info("正在初始化数据库...")
    init_db()

    logger.info("Flask 服务器启动中...")
    # 允许端口重用，避免 Address already in use 错误
    from werkzeug.serving import is_running_from_reloader
    # 添加额外的 socket 选项
    import socket
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)
