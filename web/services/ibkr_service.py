import pandas as pd
import requests
import time
import xml.etree.ElementTree as ET
import math
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.db import ibkr_db
from shared.config import IBKR_TOKEN, QUERY_ID_DAILY, QUERY_ID_WEEKLY


def clean_nan(obj):
    """Replace NaN values with None for JSON serialization"""
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


# Target percentages for portfolio allocation
TARGET_PERCENT = {
    'GOOGL': 10.0, 'NVDA': 10.0, 'TSLA': 10.0,
    'ABBV': 5.0, 'AMD': 5.0, 'COIN': 5.0, 'COST': 5.0, 'DIS': 5.0,
    'GLD': 5.0, 'MSFT': 5.0, 'MSTR': 5.0, 'PLTR': 5.0,
    'AMZN': 2.5, 'IBIT': 2.5, 'LLY': 2.5, 'MRK': 2.5, 'NFLX': 2.5, 'ORCL': 2.5,
    'AVGO': 2.0, 'GLW': 2.0, 'INTC': 2.0, 'META': 2.0, 'SOFI': 2.0,
}


def fetch_all_trades():
    """Fetch all trades from database"""
    df = ibkr_db.fetch_all_trades_as_df()
    if df.empty:
        return []
    return df.to_dict(orient='records')


def fetch_market_prices():
    """Fetch latest market prices"""
    return ibkr_db.fetch_latest_market_prices()


def save_market_price(symbol, price, date_time):
    """Save market price to database"""
    return ibkr_db.save_market_price(symbol, price, date_time)


def save_trade(trade_data):
    """Save a trade to database, ignore if exists"""
    return ibkr_db.save_trade(trade_data)


def update_trade(trade_id, updates):
    """Update specific fields for a trade"""
    return ibkr_db.update_trade_fields(trade_id, updates)


def calculate_pnl(trades_df):
    """Calculate realized PnL and remaining quantity using FIFO method"""
    if trades_df.empty:
        return trades_df

    trades_df = trades_df.copy()
    trades_df['realized_pnl'] = 0.0
    trades_df['remaining_qty'] = 0.0

    inventory = {}

    for idx, row in trades_df.iterrows():
        symbol = row['symbol']
        qty = float(row['quantity']) if row['quantity'] else 0.0
        price = float(row['tradePrice']) if row['tradePrice'] else 0.0
        multiplier = float(row['multiplier']) if row['multiplier'] else 1.0

        if symbol not in inventory:
            inventory[symbol] = []

        if not inventory[symbol]:
            trades_df.at[idx, 'remaining_qty'] = qty
            inventory[symbol].append({'idx': idx, 'qty': qty, 'price': price})
            continue

        head = inventory[symbol][0]
        if (qty > 0 and head['qty'] > 0) or (qty < 0 and head['qty'] < 0):
            trades_df.at[idx, 'remaining_qty'] = qty
            inventory[symbol].append({'idx': idx, 'qty': qty, 'price': price})
        else:
            qty_to_process = qty
            total_pnl = 0.0

            while qty_to_process != 0 and inventory[symbol]:
                item = inventory[symbol][0]
                open_qty = item['qty']
                open_price = item['price']
                open_idx = item['idx']

                if abs(qty_to_process) >= abs(open_qty):
                    match_qty = -open_qty
                    term_pnl = -(price - open_price) * match_qty * multiplier
                    total_pnl += term_pnl
                    qty_to_process -= match_qty
                    trades_df.at[open_idx, 'remaining_qty'] = 0
                    inventory[symbol].pop(0)
                else:
                    term_pnl = -(price - open_price) * qty_to_process * multiplier
                    total_pnl += term_pnl
                    item['qty'] += qty_to_process
                    trades_df.at[open_idx, 'remaining_qty'] = item['qty']
                    qty_to_process = 0

            trades_df.at[idx, 'realized_pnl'] = total_pnl

            if qty_to_process != 0:
                trades_df.at[idx, 'remaining_qty'] = qty_to_process
                inventory[symbol].append({'idx': idx, 'qty': qty_to_process, 'price': price})

    return trades_df


def get_trades_with_calculations():
    """Get all trades with PnL calculations"""
    trades = fetch_all_trades()
    if not trades:
        return pd.DataFrame()

    df = pd.DataFrame(trades)
    df = df[df['symbol'] != 'USD.CAD']

    df = calculate_pnl(df)

    m = df['multiplier'].fillna(1.0)
    df['credit'] = df['remaining_qty'] * df['tradePrice'] * m * -1

    df['mtm_price'] = 0.0
    market_prices = fetch_market_prices()

    mask = ~df['putCall'].isin(['C', 'P'])
    df.loc[mask, 'mtm_price'] = df.loc[mask, 'symbol'].map(market_prices).fillna(0.0)
    df['mtm_value'] = df['mtm_price'] * df['remaining_qty']

    return df


def get_all_positions(sort_by='mtm', ascending=False):
    """Get aggregated positions by underlying symbol"""
    df = get_trades_with_calculations()
    if df.empty:
        return {'positions': [], 'totals': {}}

    groups = df.groupby('underlyingSymbol')
    positions = []

    for symbol, group in groups:
        stock_df = group[~group['putCall'].isin(['C', 'P'])]
        call_df = group[group['putCall'] == 'C']
        put_df = group[group['putCall'] == 'P']

        value = stock_df['credit'].sum() * -1
        mtm = stock_df['mtm_value'].sum()
        unrlzd_pnl = mtm - value

        s_qty = stock_df['remaining_qty'].sum()
        c_qty = call_df['remaining_qty'].sum()
        p_qty = put_df['remaining_qty'].sum()

        s_pnl = stock_df['realized_pnl'].sum()
        c_pnl = call_df['realized_pnl'].sum()
        p_pnl = put_df['realized_pnl'].sum()

        if any(x != 0 for x in [value, mtm, s_qty, c_qty, p_qty, s_pnl, c_pnl, p_pnl]):
            positions.append({
                'symbol': symbol,
                'value': value,
                'mtm': mtm,
                'unrlzd_pnl': unrlzd_pnl,
                's_qty': s_qty,
                'c_qty': c_qty,
                'p_qty': p_qty,
                's_pnl': s_pnl,
                'c_pnl': c_pnl,
                'p_pnl': p_pnl,
                'target_pct': TARGET_PERCENT.get(symbol, 0.0)
            })

    sort_key = sort_by if sort_by in ['value', 'mtm', 'symbol', 's_qty'] else 'mtm'
    reverse = not ascending
    positions.sort(key=lambda x: x[sort_key] if sort_key != 'symbol' else x['symbol'].lower(), reverse=reverse if sort_key != 'symbol' else not reverse)

    total_mtm = sum(p['mtm'] for p in positions)
    for p in positions:
        p['mtm_pct'] = (p['mtm'] / total_mtm * 100) if total_mtm != 0 else 0

    totals = {
        'value': sum(p['value'] for p in positions),
        'mtm': total_mtm,
        'unrlzd_pnl': sum(p['unrlzd_pnl'] for p in positions),
        's_qty': sum(p['s_qty'] for p in positions),
        'c_qty': sum(p['c_qty'] for p in positions),
        'p_qty': sum(p['p_qty'] for p in positions),
        's_pnl': sum(p['s_pnl'] for p in positions),
        'c_pnl': sum(p['c_pnl'] for p in positions),
        'p_pnl': sum(p['p_pnl'] for p in positions),
        'target_pct': sum(p['target_pct'] for p in positions)
    }

    return {'positions': positions, 'totals': totals}


def get_position_detail(symbol):
    """Get detailed position for a specific symbol"""
    df = get_trades_with_calculations()
    if df.empty:
        return None

    mask = (df['symbol'] == symbol) | (df['underlyingSymbol'] == symbol)
    subset = df[mask].copy()

    if subset.empty:
        return None

    subset['dateTime'] = pd.to_datetime(subset['dateTime'], errors='coerce')
    subset = subset.sort_values(by='dateTime', ascending=False)

    stock_df = subset[~subset['putCall'].isin(['C', 'P'])]
    call_df = subset[subset['putCall'] == 'C']
    put_df = subset[subset['putCall'] == 'P']

    stock_credit_sum = stock_df['credit'].sum()
    stock_rem_qty_sum = stock_df['remaining_qty'].sum()
    book_price = stock_credit_sum / stock_rem_qty_sum if stock_rem_qty_sum != 0 else 0

    summary = {
        'symbol': symbol,
        'book_price': book_price,
        'stock_qty': stock_rem_qty_sum,
        'call_qty': call_df['remaining_qty'].sum(),
        'put_qty': put_df['remaining_qty'].sum(),
        'stock_pnl': stock_df['realized_pnl'].sum(),
        'call_pnl': call_df['realized_pnl'].sum(),
        'put_pnl': put_df['realized_pnl'].sum(),
    }

    trades = []
    for _, row in subset.iterrows():
        trades.append({
            'tradeID': row['tradeID'],
            'dateTime': row['dateTime'].strftime('%Y-%m-%d %H:%M') if pd.notnull(row['dateTime']) else '',
            'description': row['description'],
            'putCall': row['putCall'],
            'quantity': row['quantity'],
            'tradePrice': row['tradePrice'],
            'ibCommission': row['ibCommission'],
            'openCloseIndicator': row['openCloseIndicator'],
            'realized_pnl': row.get('realized_pnl', 0),
            'remaining_qty': row.get('remaining_qty', 0),
            'credit': row.get('credit', 0),
            'delta': row.get('delta'),
            'und_price': row.get('und_price'),
        })

    return {'summary': summary, 'trades': trades}


def get_daily_stats():
    """Get daily PnL statistics"""
    df = get_trades_with_calculations()
    if df.empty:
        return []

    df['dateTime'] = pd.to_datetime(df['dateTime'])
    df['date_only'] = df['dateTime'].dt.normalize()
    daily_stats = df.groupby('date_only')['realized_pnl'].sum()

    if daily_stats.empty:
        return []

    min_date = daily_stats.index.min()
    max_date = daily_stats.index.max()
    all_days = pd.date_range(start=min_date, end=max_date, freq='D')
    daily_stats = daily_stats.reindex(all_days, fill_value=0.0)

    mask = (daily_stats.index.dayofweek < 5) | (daily_stats != 0)
    daily_stats = daily_stats[mask]

    result = []
    total = 0.0
    for date, pnl in daily_stats.items():
        total += pnl
        result.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%A'),
            'pnl': pnl
        })

    return {'stats': result, 'total': total}


def get_weekly_stats():
    """Get weekly PnL statistics"""
    df = get_trades_with_calculations()
    if df.empty:
        return []

    df['dateTime'] = pd.to_datetime(df['dateTime'])
    df.set_index('dateTime', inplace=True)
    weekly_stats = df['realized_pnl'].resample('W-FRI').sum()

    if weekly_stats.empty:
        return []

    result = []
    total = 0.0
    for date, pnl in weekly_stats.items():
        total += pnl
        result.append({
            'week_ending': date.strftime('%Y-%m-%d'),
            'pnl': pnl
        })

    return {'stats': result, 'total': total}


def import_trades(query_type='daily'):
    """Import trades from IBKR Flex Query"""
    query_id = QUERY_ID_DAILY if query_type == 'daily' else QUERY_ID_WEEKLY
    token = IBKR_TOKEN

    url_req = f"https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest?t={token}&q={query_id}&v=3"

    resp = requests.get(url_req)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    status = root.find('Status')

    if status is None or status.text != 'Success':
        err_code = root.find('ErrorCode')
        err_msg = root.find('ErrorMessage')
        raise Exception(f"Error: {err_code.text if err_code is not None else 'Unknown'} - {err_msg.text if err_msg is not None else 'Unknown'}")

    ref_code = root.find('ReferenceCode').text
    base_url = root.find('Url').text

    url_dl = f"{base_url}?q={ref_code}&t={token}&v=3"

    max_retries = 10
    for i in range(max_retries):
        time.sleep(2)
        resp_dl = requests.get(url_dl)
        if resp_dl.status_code == 200:
            if b'<FlexStatement' in resp_dl.content or b'<FlexQueryResponse' in resp_dl.content:
                return process_import_xml(resp_dl.content)

    raise Exception("Timeout waiting for report generation")


def process_import_xml(xml_content):
    """Process XML content from IBKR Flex Query"""
    root = ET.fromstring(xml_content)
    trades_list = [elem for elem in root.iter() if elem.tag.endswith('Trade') or elem.tag.endswith('TradeConfirm')]

    if not trades_list:
        return {'count': 0, 'message': 'No trades found in report'}

    count_new = 0
    for trade in trades_list:
        data = trade.attrib

        safe_float = lambda k: float(data[k]) if data.get(k) and data[k].strip() else None

        trade_price = safe_float('tradePrice') if 'tradePrice' in data else safe_float('price')
        ib_commission = safe_float('ibCommission') if 'ibCommission' in data else safe_float('commission')

        open_close = data.get('openCloseIndicator')
        if open_close is None and 'code' in data:
            c_val = data.get('code', '')
            if 'O' in c_val:
                open_close = 'O'
            elif 'C' in c_val:
                open_close = 'C'

        row = {
            'tradeID': data.get('tradeID'),
            'accountId': data.get('accountId'),
            'underlyingSymbol': data.get('underlyingSymbol'),
            'symbol': data.get('symbol'),
            'description': data.get('description'),
            'expiry': data.get('expiry'),
            'putCall': data.get('putCall'),
            'strike': safe_float('strike'),
            'dateTime': data.get('dateTime'),
            'quantity': safe_float('quantity'),
            'tradePrice': trade_price,
            'multiplier': safe_float('multiplier'),
            'ibCommission': ib_commission,
            'currency': data.get('currency'),
            'notes': data.get('notes'),
            'openCloseIndicator': open_close
        }

        if save_trade(row):
            count_new += 1

    return {'count': count_new, 'message': f'{count_new} new trades imported'}


def update_mtm_prices():
    """Update market prices using yahooquery"""
    df = get_trades_with_calculations()
    if df.empty:
        return {'count': 0, 'message': 'No trades to update'}

    mask = ~df['putCall'].isin(['C', 'P'])
    symbols = df.loc[mask, 'symbol'].unique().tolist()

    if not symbols:
        return {'count': 0, 'message': 'No stock positions found'}

    try:
        from yahooquery import Ticker
    except ImportError:
        raise Exception("yahooquery not installed. Install with: pip install yahooquery")

    t = Ticker(symbols, asynchronous=True)
    data = t.price

    if not isinstance(data, dict):
        raise Exception(f"Unexpected response from yahooquery")

    current_time = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0

    for sym, info in data.items():
        if isinstance(info, dict):
            price = info.get('regularMarketPrice') or info.get('regularMarketPreviousClose')
            if price is not None:
                save_market_price(sym, float(price), current_time)
                count += 1

    return {'count': count, 'message': f'Updated prices for {count} symbols'}
