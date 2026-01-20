import pandas as pd
import math
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.db import fbn_db


def clean_nan(obj):
    """Replace NaN values with None for JSON serialization"""
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


# Account definitions
ACCOUNTS = [
    {'name': 'MARGE', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'REER', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'CRI', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'REEE', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'CELI', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'MM MARGE', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'MM CELI', 'portfolio': 'Personnel', 'currency': 'CAD'},
    {'name': 'GFZ CAD', 'portfolio': 'Gestion FZ', 'currency': 'CAD'},
    {'name': 'GFZ USD', 'portfolio': 'Gestion FZ', 'currency': 'USD'},
]


def fetch_fbn_data():
    """Fetch all FBN data from database"""
    return fbn_db.fetch_fbn_data()


def get_fbn_dataframe():
    """Get FBN data as DataFrame with currency conversion applied"""
    df = fetch_fbn_data()
    if df.empty:
        return pd.DataFrame()

    df['date'] = pd.to_datetime(df['date'])

    # Apply currency conversion (USD -> CAD)
    cols_to_convert = ['investment', 'deposit', 'asset', 'fee', 'dividend',
                       'interest', 'tax', 'other', 'cash', 'distribution']
    mask = df['currency'] == 'USD'

    for col in cols_to_convert:
        if col in df.columns:
            df.loc[mask, col] = df.loc[mask, col] * df.loc[mask, 'rate']

    return df


def get_monthly_stats():
    """Get monthly aggregated stats with PnL calculation"""
    df = get_fbn_dataframe()
    if df.empty:
        return {'stats': [], 'totals': {}}

    # Group by date and aggregate
    monthly_groups = df.groupby('date')

    agg_data = []
    for date, group in monthly_groups:
        agg_data.append({
            'date': date,
            'deposit': group['deposit'].sum(),
            'asset': group['asset'].sum(),
            'fee': group['fee'].sum()
        })

    monthly_df = pd.DataFrame(agg_data)
    monthly_df = monthly_df.sort_values('date')

    # Calculate PnL: pnl = asset - deposit - prev_asset
    monthly_df['prev_asset'] = monthly_df['asset'].shift(1).fillna(0.0)
    monthly_df['pnl'] = monthly_df['asset'] - monthly_df['deposit'] - monthly_df['prev_asset']

    # Calculate percentage: pct = (pnl / prev_asset) * 100
    monthly_df['pct'] = monthly_df.apply(
        lambda row: (row['pnl'] / row['prev_asset']) * 100 if row['prev_asset'] != 0 else 0.0,
        axis=1
    )

    # Convert to list of dicts
    stats = []
    for _, row in monthly_df.iterrows():
        stats.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'deposit': row['deposit'],
            'asset': row['asset'],
            'fee': row['fee'],
            'pnl': row['pnl'],
            'pct': row['pct']
        })

    # Calculate totals
    totals = {
        'deposit': monthly_df['deposit'].sum(),
        'asset': monthly_df.iloc[-1]['asset'] if not monthly_df.empty else 0,
        'fee': monthly_df['fee'].sum(),
        'pnl': monthly_df['pnl'].sum()
    }

    return {'stats': stats, 'totals': totals}


def get_yearly_stats():
    """Get yearly aggregated stats with PnL calculation"""
    df = get_fbn_dataframe()
    if df.empty:
        return {'stats': [], 'totals': {}}

    # First aggregate monthly, then by year
    monthly_groups = df.groupby('date')
    monthly_data = []
    for date, group in monthly_groups:
        monthly_data.append({
            'date': date,
            'deposit': group['deposit'].sum(),
            'asset': group['asset'].sum(),
            'fee': group['fee'].sum()
        })

    monthly_df = pd.DataFrame(monthly_data)
    monthly_df['year'] = monthly_df['date'].dt.year

    # Group by year
    yearly_groups = monthly_df.groupby('year')
    yearly_agg = []

    for year, group in yearly_groups:
        yearly_agg.append({
            'year': int(year),
            'deposit': group['deposit'].sum(),
            'asset': group.iloc[-1]['asset'],  # Last asset value of the year
            'fee': group['fee'].sum()
        })

    yearly_df = pd.DataFrame(yearly_agg)
    yearly_df = yearly_df.sort_values('year')

    # Calculate PnL
    yearly_df['prev_asset'] = yearly_df['asset'].shift(1).fillna(0.0)
    yearly_df['pnl'] = yearly_df['asset'] - yearly_df['deposit'] - yearly_df['prev_asset']
    yearly_df['pct'] = yearly_df.apply(
        lambda row: (row['pnl'] / row['prev_asset']) * 100 if row['prev_asset'] != 0 else 0.0,
        axis=1
    )

    stats = []
    for _, row in yearly_df.iterrows():
        stats.append({
            'year': int(row['year']),
            'deposit': row['deposit'],
            'asset': row['asset'],
            'fee': row['fee'],
            'pnl': row['pnl'],
            'pct': row['pct']
        })

    totals = {
        'deposit': yearly_df['deposit'].sum(),
        'asset': yearly_df.iloc[-1]['asset'] if not yearly_df.empty else 0,
        'fee': yearly_df['fee'].sum(),
        'pnl': yearly_df['pnl'].sum()
    }

    return {'stats': stats, 'totals': totals}


def get_monthly_matrix():
    """Get monthly assets matrix (dates x accounts)"""
    df = get_fbn_dataframe()
    if df.empty:
        return {'dates': [], 'accounts': [], 'data': []}

    # Pivot table: dates as rows, accounts as columns, asset as values
    pivot_df = df.pivot_table(index='date', columns='account', values='asset', aggfunc='sum')
    pivot_df = pivot_df.sort_index()

    # Order columns by account definition
    ordered_accounts = [acc['name'] for acc in ACCOUNTS if acc['name'] in pivot_df.columns]
    extra_accounts = [col for col in pivot_df.columns if col not in ordered_accounts]
    final_accounts = ordered_accounts + extra_accounts
    pivot_df = pivot_df[final_accounts]

    # Build response
    data = []
    for date, row in pivot_df.iterrows():
        row_data = {'date': date.strftime('%Y-%m-%d')}
        total = 0
        for acc in final_accounts:
            val = row[acc]
            if pd.notna(val):
                row_data[acc] = val
                total += val
            else:
                row_data[acc] = None
        row_data['total'] = total
        data.append(row_data)

    return {'accounts': final_accounts, 'data': data}


def get_yearly_matrix():
    """Get yearly assets matrix (years x accounts)"""
    df = get_fbn_dataframe()
    if df.empty:
        return {'years': [], 'accounts': [], 'data': []}

    # Get last entry per year per account
    df['year'] = df['date'].dt.year
    df = df.sort_values('date')
    yearly_last = df.groupby(['year', 'account']).last().reset_index()

    # Pivot table
    pivot_df = yearly_last.pivot_table(index='year', columns='account', values='asset', aggfunc='sum')
    pivot_df = pivot_df.sort_index()

    # Order columns
    ordered_accounts = [acc['name'] for acc in ACCOUNTS if acc['name'] in pivot_df.columns]
    extra_accounts = [col for col in pivot_df.columns if col not in ordered_accounts]
    final_accounts = ordered_accounts + extra_accounts
    pivot_df = pivot_df[final_accounts]

    # Build response
    data = []
    for year, row in pivot_df.iterrows():
        row_data = {'year': int(year)}
        total = 0
        for acc in final_accounts:
            val = row[acc]
            if pd.notna(val):
                row_data[acc] = val
                total += val
            else:
                row_data[acc] = None
        row_data['total'] = total
        data.append(row_data)

    return {'accounts': final_accounts, 'data': data}


def get_accounts():
    """Get list of all accounts"""
    return ACCOUNTS


def get_entry(date: str, account: str):
    """Get a specific entry by date and account"""
    df = fetch_fbn_data()
    if df.empty:
        return None

    # Filter by date and account
    mask = (df['date'].astype(str) == date) & (df['account'] == account)
    filtered = df[mask]

    if filtered.empty:
        return None

    return filtered.iloc[0].to_dict()


def save_entry(entry: dict):
    """Save an account entry (upsert)"""
    return fbn_db.save_account_entry(entry)
