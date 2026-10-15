PRAGMA foreign_keys = ON;

CREATE TABLE users(
    user_id TEXT PRIMARY KEY NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (STRFTIME('%s','now')),
    updated_at INTEGER NOT NULL DEFAULT (STRFTIME('%s','now')),
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Enums --
    CHECK (status IN ('active','inactive','deleted'))
);
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE UNIQUE INDEX idx_users_username ON users(username);

CREATE TABLE orders(
    order_id TEXT PRIMARY KEY NOT NULL,
    created_at INTEGER NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    shipping_address TEXT NOT NULL,
    total_amount_cents INTEGER NOT NULL CHECK (total_amount_cents >= 0),
    delivered_at TEXT
);

CREATE TABLE order_items(
    order_item_id TEXT PRIMARY KEY NOT NULL,
    created_at INTEGER NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0)
);

CREATE TABLE refunds(
    refund_id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('approved', 'rejected')),
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE audit_log(
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('MUTATION_EXECUTED', 'MUTATION_BLOCKED', 'AUTH_VERIFIED', 'INVARIANT_BREACH')),
    tool_name TEXT NOT NULL,
    user_id TEXT REFERENCES users(user_id),
    order_id TEXT REFERENCES orders(order_id),
    idempotency_key TEXT,
    status_code TEXT NOT NULL,
    details_json TEXT NOT NULL,
    timestamp INTEGER NOT NULL
);

