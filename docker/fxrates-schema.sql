CREATE TABLE IF NOT EXISTS exchange_rates (
  date TEXT NOT NULL,
  currency TEXT NOT NULL,
  rate REAL NOT NULL,
  PRIMARY KEY (date, currency)
);
