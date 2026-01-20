"""FBN database operations using Supabase."""
import pandas as pd
from shared.supabase_client import get_client


def fetch_fbn_data() -> pd.DataFrame:
    """
    Retrieves all data from the fbn table.
    Returns a pandas DataFrame.
    """
    client = get_client()

    try:
        response = client.table('fbn').select('*').execute()
        if not response.data:
            return pd.DataFrame()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Error fetching fbn data: {e}")
        return pd.DataFrame()


def save_account_entry(entry: dict) -> bool:
    """
    Saves a single account entry to the database.
    Uses upsert on (date, account) unique constraint.
    """
    client = get_client()

    # Remove 'id' if present since it's auto-generated
    data = {k: v for k, v in entry.items() if k != 'id'}

    try:
        # First try to delete existing entry (to match SQLite behavior)
        client.table('fbn').delete().eq('date', data['date']).eq('account', data['account']).execute()

        # Then insert new entry
        response = client.table('fbn').insert(data).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error saving account entry: {e}")
        raise e
