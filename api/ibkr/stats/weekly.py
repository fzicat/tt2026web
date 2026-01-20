"""GET /api/ibkr/stats/weekly - Get weekly PnL statistics"""
from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from api._utils import clean_nan
from web.services import ibkr_service


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self._verify_auth():
            return

        try:
            result = ibkr_service.get_weekly_stats()
            self.send_json_response(clean_nan(result))
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
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()
