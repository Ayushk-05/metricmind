-- MetricMind Seed Data
-- Provides realistic sample records for business analytics questions and tests.

-- 1. Seed Customers
INSERT INTO customers (id, first_name, last_name, email, city, state, country, created_at) VALUES
(1, 'Alice', 'Smith', 'alice.smith@example.com', 'Seattle', 'WA', 'United States', '2026-01-15 08:30:00+00'),
(2, 'Bob', 'Johnson', 'bob.johnson@example.com', 'Austin', 'TX', 'United States', '2026-01-20 10:15:00+00'),
(3, 'Carla', 'Mendoza', 'carla.mendoza@example.com', 'San Francisco', 'CA', 'United States', '2026-02-05 14:00:00+00'),
(4, 'David', 'Kim', 'david.kim@example.com', 'Chicago', 'IL', 'United States', '2026-02-18 09:45:00+00'),
(5, 'Emma', 'Wilson', 'emma.wilson@example.com', 'New York', 'NY', 'United States', '2026-03-01 11:20:00+00'),
(6, 'Fiona', 'Gallagher', 'fiona.g@example.co.uk', 'London', 'Greater London', 'United Kingdom', '2026-03-12 16:10:00+00'),
(7, 'George', 'Chen', 'george.chen@example.ca', 'Toronto', 'ON', 'Canada', '2026-03-25 13:05:00+00'),
(8, 'Hanna', 'Schmidt', 'hanna.schmidt@example.de', 'Berlin', 'Berlin', 'Germany', '2026-04-02 08:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- 2. Seed Products
INSERT INTO products (id, name, category, price, cost, stock_quantity, created_at) VALUES
(1, 'Ergonomic Desk Chair', 'Office Furniture', 299.99, 140.00, 45, '2026-01-01 00:00:00+00'),
(2, 'Standing Desk Converter', 'Office Furniture', 199.50, 95.00, 30, '2026-01-01 00:00:00+00'),
(3, 'Wireless Noise-Canceling Headphones', 'Electronics', 249.99, 110.00, 80, '2026-01-01 00:00:00+00'),
(4, 'Ultra-Wide Monitor 34-inch', 'Electronics', 499.00, 275.00, 25, '2026-01-01 00:00:00+00'),
(5, 'Mechanical Keyboard', 'Electronics', 129.99, 55.00, 110, '2026-01-01 00:00:00+00'),
(6, 'Precision Wireless Mouse', 'Electronics', 79.99, 32.00, 95, '2026-01-01 00:00:00+00'),
(7, 'Analytics Cloud Subscription (Annual)', 'Software', 599.00, 60.00, 9999, '2026-01-01 00:00:00+00'),
(8, 'Developer Pro Tool Suite', 'Software', 349.00, 35.00, 9999, '2026-01-01 00:00:00+00'),
(9, 'USB-C Multi-Port Hub', 'Accessories', 49.99, 18.00, 150, '2026-01-01 00:00:00+00'),
(10, 'Aluminum Laptop Stand', 'Accessories', 39.99, 14.00, 120, '2026-01-01 00:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- 3. Seed Orders
INSERT INTO orders (id, customer_id, order_date, status, total_amount, created_at) VALUES
(1, 1, '2026-02-10 10:30:00+00', 'completed', 748.99, '2026-02-10 10:30:00+00'),
(2, 2, '2026-02-15 14:20:00+00', 'completed', 299.99, '2026-02-15 14:20:00+00'),
(3, 3, '2026-02-28 09:15:00+00', 'completed', 628.99, '2026-02-28 09:15:00+00'),
(4, 4, '2026-03-05 11:45:00+00', 'completed', 199.50, '2026-03-05 11:45:00+00'),
(5, 5, '2026-03-12 16:00:00+00', 'completed', 848.99, '2026-03-12 16:00:00+00'),
(6, 1, '2026-03-20 13:10:00+00', 'completed', 349.00, '2026-03-20 13:10:00+00'),
(7, 6, '2026-04-01 15:30:00+00', 'completed', 599.00, '2026-04-01 15:30:00+00'),
(8, 7, '2026-04-10 10:00:00+00', 'shipped', 259.97, '2026-04-10 10:00:00+00'),
(9, 8, '2026-04-15 12:20:00+00', 'pending', 499.00, '2026-04-15 12:20:00+00'),
(10, 2, '2026-04-18 17:40:00+00', 'cancelled', 79.99, '2026-04-18 17:40:00+00')
ON CONFLICT (id) DO NOTHING;

-- 4. Seed Order Items
INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
-- Order 1: Alice (Ultra-Wide Monitor + Noise-Canceling Headphones)
(1, 1, 4, 1, 499.00),
(2, 1, 3, 1, 249.99),
-- Order 2: Bob (Ergonomic Chair)
(3, 2, 1, 1, 299.99),
-- Order 3: Carla (Ultra-Wide Monitor + Mechanical Keyboard)
(4, 3, 4, 1, 499.00),
(5, 3, 5, 1, 129.99),
-- Order 4: David (Standing Desk Converter)
(6, 4, 2, 1, 199.50),
-- Order 5: Emma (Ultra-Wide Monitor + Wireless Headphones + USB-C Hub x2)
(7, 5, 4, 1, 499.00),
(8, 5, 3, 1, 249.99),
(9, 5, 9, 2, 49.99),
-- Order 6: Alice (Developer Pro Suite)
(10, 6, 8, 1, 349.00),
-- Order 7: Fiona (Analytics Cloud Subscription)
(11, 7, 7, 1, 599.00),
-- Order 8: George (Keyboard + Mouse + Laptop Stand)
(12, 8, 5, 1, 129.99),
(13, 8, 6, 1, 79.99),
(14, 8, 10, 1, 39.99),
-- Order 9: Hanna (Ultra-Wide Monitor)
(15, 9, 4, 1, 499.00),
-- Order 10: Bob (Precision Wireless Mouse - cancelled)
(16, 10, 6, 1, 79.99)
ON CONFLICT (id) DO NOTHING;

-- Synchronize sequence values after manual ID inserts
SELECT setval(pg_get_serial_sequence('customers', 'id'), COALESCE(MAX(id), 1)) FROM customers;
SELECT setval(pg_get_serial_sequence('products', 'id'), COALESCE(MAX(id), 1)) FROM products;
SELECT setval(pg_get_serial_sequence('orders', 'id'), COALESCE(MAX(id), 1)) FROM orders;
SELECT setval(pg_get_serial_sequence('order_items', 'id'), COALESCE(MAX(id), 1)) FROM order_items;
