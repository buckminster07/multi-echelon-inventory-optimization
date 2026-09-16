PRAGMA foreign_keys = ON;
CREATE TABLE nodes(node_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
 kind TEXT CHECK(kind IN ('warehouse','store')), parent_id INTEGER REFERENCES nodes(node_id),
 holding_cost REAL NOT NULL CHECK(holding_cost>0));
CREATE TABLE skus(sku TEXT PRIMARY KEY, label TEXT NOT NULL,
 cost_multiplier REAL NOT NULL CHECK(cost_multiplier>0), shortage_penalty REAL NOT NULL CHECK(shortage_penalty>0));
CREATE TABLE demand(date TEXT NOT NULL, node_id INTEGER REFERENCES nodes(node_id),
 sku TEXT REFERENCES skus(sku), quantity INTEGER CHECK(quantity>=0), PRIMARY KEY(date,node_id,sku));
CREATE TABLE receipts(receipt_id INTEGER PRIMARY KEY, node_id INTEGER REFERENCES nodes(node_id),
 sku TEXT REFERENCES skus(sku), dispatch_date TEXT NOT NULL, receipt_date TEXT NOT NULL,
 quantity INTEGER CHECK(quantity>0), CHECK(receipt_date>dispatch_date));
