#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 服务器模块
提供 RESTful API 接口，供手机 APP 调用
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional
from config.settings import NetworkConfig, Config

logger = logging.getLogger(__name__)


class APIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/api/visitors':
            self._get_visitors()
        elif self.path == '/api/logs':
            self._get_logs()
        elif self.path == '/api/status':
            self._get_status()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        """处理 POST 请求"""
        if self.path == '/api/visitor':
            self._add_visitor()
        elif self.path == '/api/member':
            self._add_member()
        else:
            self.send_error(404, 'Not Found')

    def _send_json_response(self, data: Dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _get_visitors(self):
        """获取访客记录"""
        visitors_file = Config.VISITOR_DATA_DIR + '/visitors.json'
        try:
            with open(visitors_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._send_json_response(data)
        except FileNotFoundError:
            self._send_json_response({'visitors': []})

    def _get_logs(self):
        """获取访问日志"""
        logs_file = Config.DATA_DIR + '/access_logs.json'
        try:
            with open(logs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._send_json_response(data)
        except FileNotFoundError:
            self._send_json_response({'logs': []})

    def _get_status(self):
        """获取系统状态"""
        status = {
            'status': 'online',
            'system': 'CLAUDE Smart Doorbell'
        }
        self._send_json_response(status)

    def _add_visitor(self):
        """添加访客记录"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        logger.info(f"收到访客数据：{data}")
        self._send_json_response({'status': 'success'})

    def _add_member(self):
        """添加家庭成员"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        logger.info(f"收到成员数据：{data}")
        self._send_json_response({'status': 'success'})

    def log_message(self, format, *args):
        """重写日志输出"""
        logger.info(f"API 请求：{args[0]}")


class APIServer:
    """API 服务器类"""

    def __init__(self, host: str = None, port: int = None):
        """
        初始化 API 服务器

        Args:
            host: 监听地址
            port: 监听端口
        """
        self.host = host or '0.0.0.0'
        self.port = port or NetworkConfig.SERVER_PORT
        self.server: Optional[HTTPServer] = None

        logger.info(f"APIServer 初始化完成 ({self.host}:{self.port})")

    def start(self):
        """启动服务器"""
        try:
            self.server = HTTPServer((self.host, self.port), APIHandler)
            logger.info(f"API 服务器已启动：http://{self.host}:{self.port}")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"API 服务器启动失败：{e}")

    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            logger.info("API 服务器已停止")


if __name__ == "__main__":
    # 测试
    server = APIServer()
    print("启动 API 服务器...")
    server.start()
