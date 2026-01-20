"""Supabase client singleton and authentication helpers."""
from supabase import create_client, Client
from shared.config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None
_user_session = None


def get_client() -> Client:
    """Get the Supabase client singleton (uses service role key)."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def login(email: str, password: str) -> dict:
    """Authenticate user with email and password."""
    global _user_session
    client = get_client()
    response = client.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    _user_session = response.session
    return {"access_token": response.session.access_token, "user": response.user}


def logout():
    """Sign out the current user."""
    global _user_session
    client = get_client()
    client.auth.sign_out()
    _user_session = None


def get_session():
    """Get the current user session."""
    return _user_session


def is_authenticated() -> bool:
    """Check if a user is currently authenticated."""
    return _user_session is not None


def verify_token(token: str) -> dict | None:
    """Verify a JWT token and return user info if valid."""
    client = get_client()
    try:
        response = client.auth.get_user(token)
        return {"user": response.user}
    except Exception:
        return None
