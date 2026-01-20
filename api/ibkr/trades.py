"""GET/PATCH /api/ibkr/trades - Get all trades or update a trade"""
from http.server import BaseHTTPRequestHandler
import json
import sys
import os
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api._utils import clean_nan
from web.services import ibkr_service


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self._verify_auth():
            return

        try:
            df = ibkr_service.get_trades_with_calculations()
            if df.empty:
                self.send_json_response([])
                return
            df['dateTime'] = df['dateTime'].astype(str)
            self.send_json_response(clean_nan(df.to_dict(orient='records')))
        except Exception as e:
            self.send_error_response(500, str(e))

    def do_PATCH(self):
        if not self._verify_auth():
            return

        # Extract trade_id from path (e.g., /api/ibkr/trades/123)
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 4:
            self.send_error_response(400, 'Trade ID required')
            return

        trade_id = path_parts[3]

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode()) if content_length else {}

            updates = {}
            if 'delta' in body and body['delta'] is not None:
                updates['delta'] = body['delta']
            if 'und_price' in body and body['und_price'] is not None:
                updates['und_price'] = body['und_price']

            if not updates:
                self.send_error_response(400, 'No fields to update')
                return

            success = ibkr_service.update_trade(trade_id, updates)
            if not success:
                self.send_error_response(404, f'Trade {trade_id} not found')
                return

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
        self.send_header('Access-Control-Allow-Methods', 'GET, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()
