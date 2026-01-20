"""GET/POST /api/fbn/entry - Get or save FBN entry"""
from http.server import BaseHTTPRequestHandler
import json
import sys
import os
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api._utils import clean_nan
from web.services import fbn_service


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self._verify_auth():
            return

        # Parse path: /api/fbn/entry/{date}/{account}
        parsed = urlparse(self.path)
        path_parts = [unquote(p) for p in parsed.path.strip('/').split('/')]

        if len(path_parts) < 5:
            self.send_error_response(400, 'Date and account required')
            return

        date = path_parts[3]
        account = path_parts[4]

        try:
            entry = fbn_service.get_entry(date, account)
            self.send_json_response(clean_nan(entry) if entry else None)
        except Exception as e:
            self.send_error_response(500, str(e))

    def do_POST(self):
        if not self._verify_auth():
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode()) if content_length else {}

            fbn_service.save_entry(body)
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_error_response(500, str(e))

    def _verify_auth(self):
        auth = self.headers.get('Authorization', '')
        token = auth[7:] if auth.startswith('Bearer ') else None
        if not token:
            self.send_error_response(401, 'Not authenticated')
            return False

        from shared.supabase_client import verify_token
        if not verify_token(token):
            self.send_error_response(401, 'Invalid or expired token')
            return False
        return True

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_error_response(self, status, message):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'detail': message}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()
