-- Orders database for the synthetic shop "Mộc An Home".
-- Used by the Order Ops agent from milestone 2 (via an MCP server).

CREATE TABLE customers (
    id            SERIAL PRIMARY KEY,
    code          TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    phone         TEXT NOT NULL,
    email         TEXT NOT NULL,
    province      TEXT NOT NULL,
    tier          TEXT NOT NULL CHECK (tier IN ('Thường', 'Bạc', 'Vàng', 'Kim Cương')),
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE products (
    id            SERIAL PRIMARY KEY,
    sku           TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price_vnd     INTEGER NOT NULL CHECK (price_vnd > 0)
);

CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    status          TEXT NOT NULL CHECK (status IN ('cho_xac_nhan', 'dang_dong_goi', 'dang_giao', 'da_giao', 'da_huy', 'tra_hang')),
    payment_method  TEXT NOT NULL,
    shipping_fee    INTEGER NOT NULL,
    total_vnd       INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    delivered_at    TIMESTAMPTZ
);

CREATE TABLE order_items (
    order_id      INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX orders_customer_idx ON orders(customer_id);
CREATE INDEX orders_created_idx ON orders(created_at);
