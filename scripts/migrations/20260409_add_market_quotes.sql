CREATE TABLE IF NOT EXISTS market_quotes (
    contract_key TEXT PRIMARY KEY,
    instrument_type TEXT NOT NULL,
    source TEXT NOT NULL,
    symbol TEXT,
    underlying_symbol TEXT,
    expiry TEXT,
    put_call TEXT,
    strike NUMERIC,
    multiplier NUMERIC,
    conid TEXT,
    bid NUMERIC,
    ask NUMERIC,
    last NUMERIC,
    close NUMERIC,
    mark NUMERIC,
    status TEXT,
    quote_time TIMESTAMPTZ,
    raw_payload JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE market_quotes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "auth_all_market_quotes" ON market_quotes
    FOR ALL USING (auth.role() = 'authenticated');

CREATE INDEX IF NOT EXISTS idx_market_quotes_symbol ON market_quotes(symbol);
CREATE INDEX IF NOT EXISTS idx_market_quotes_underlying_symbol ON market_quotes(underlying_symbol);
CREATE INDEX IF NOT EXISTS idx_market_quotes_quote_time ON market_quotes(quote_time);
CREATE INDEX IF NOT EXISTS idx_market_quotes_instrument_type ON market_quotes(instrument_type);
