"""Shared utilities for Vercel serverless functions."""
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.supabase_client import verify_token


def get_auth_header(request):
    """Extract Authorization header from request."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def verify_auth(request):
    """Verify the JWT token from the request. Returns user info or None."""
    token = get_auth_header(request)
    if not token:
        return None
    return verify_token(token)


def json_response(data, status=200):
    """Create a JSON response."""
    from http.server import BaseHTTPRequestHandler

    class Response:
        def __init__(self, body, status_code, headers):
            self.body = body
            self.status_code = status_code
            self.headers = headers

    return Response(
        body=json.dumps(data),
        status_code=status,
        headers={'Content-Type': 'application/json'}
    )


def error_response(message, status=500):
    """Create an error JSON response."""
    return json_response({'detail': message}, status)


def unauthorized_response():
    """Create a 401 Unauthorized response."""
    return error_response('Not authenticated', 401)


def clean_nan(obj):
    """Replace NaN values with None for JSON serialization."""
    import math

    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    return obj
