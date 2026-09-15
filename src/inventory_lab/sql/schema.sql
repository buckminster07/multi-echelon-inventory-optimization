-- Synthetic single-SKU daily demand. Zero-demand days must be present.
CREATE TABLE demand (
 date TEXT NOT NULL,
 store_id INTEGER NOT NULL CHECK (store_id IN (1,2)),
 sku TEXT NOT NULL CHECK (sku = 'SKU-001'),
 quantity INTEGER NOT NULL CHECK (quantity >= 0),
 PRIMARY KEY (date, store_id, sku)
);
CREATE TABLE replenishment (
 order_id INTEGER PRIMARY KEY,
 node_id INTEGER NOT NULL CHECK (node_id IN (0,1,2)),
 order_date TEXT NOT NULL,
 receipt_date TEXT NOT NULL,
 quantity INTEGER NOT NULL CHECK (quantity > 0),
 CHECK (receipt_date >= order_date)
);
