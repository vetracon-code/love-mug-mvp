CREATE TABLE IF NOT EXISTS activation_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'unused',
    variant TEXT,
    token TEXT UNIQUE,
    created_at TEXT,
    activation_date TEXT,
    expiry_date TEXT,
    renewed_at TEXT,
    last_access TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant TEXT NOT NULL,
    body TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
