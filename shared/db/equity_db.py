"""Equity database operations using Supabase."""
import pandas as pd
from shared.supabase_client import get_client


def save_equity_entry(entry_data: dict) -> bool:
    """
    Saves a single equity entry.
    entry_data: dict containing column names and values
    """
    client = get_client()

    # Remove 'id' if present since it's auto-generated
    data = {k: v for k, v in entry_data.items() if k != 'id'}

    try:
        response = client.table('equity').insert(data).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error saving equity entry: {e}")
        return False


def fetch_equity_data() -> pd.DataFrame:
    """
    Fetches all equity data, sorted by date descending.
    """
    client = get_client()

    try:
        response = client.table('equity').select('*').order('date', desc=True).execute()
        if not response.data:
            return pd.DataFrame()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Error fetching equity data: {e}")
        return pd.DataFrame()


def update_equity_entry(entry_id: int, entry_data: dict) -> bool:
    """
    Updates an existing equity entry by ID.
    entry_id: the ID of the entry to update
    entry_data: dict containing column names and values to update
    """
    client = get_client()

    # Remove 'id' from update data if present
    data = {k: v for k, v in entry_data.items() if k != 'id'}

    try:
        response = client.table('equity').update(data).eq('id', entry_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating equity entry: {e}")
        return False


def save_equity_entries(entries_list: list) -> bool:
    """
    Bulk insert multiple equity entries in a single transaction.
    entries_list: list of dicts, each containing column names and values
    """
    if not entries_list:
        return True

    client = get_client()

    # Remove 'id' from all entries
    data = [{k: v for k, v in entry.items() if k != 'id'} for entry in entries_list]

    try:
        response = client.table('equity').insert(data).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error saving equity entries: {e}")
        return False


def delete_equity_entry(entry_id: int) -> bool:
    """
    Delete a single equity entry by ID.
    """
    client = get_client()

    try:
        response = client.table('equity').delete().eq('id', entry_id).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error deleting equity entry: {e}")
        return False
