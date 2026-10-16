-- ============================================================================
-- BASE SEED FIXTURE: Customer Support Ground Truth Universe
-- ============================================================================
-- This fixture populates the pristine initial database state.
-- Each trial running in the eval runner receives an ephemeral copy of this data.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. USERS
-- ----------------------------------------------------------------------------
-- Active customers for normal multi-step workflows:
INSERT INTO users (user_id, username, email, password, status, created_at, updated_at) VALUES 
('CUST-001', 'alice_smith', 'alice@example.com', 'hashed_pwd_1', 'active', 1700000000, 1700000000),
('CUST-002', 'bob_jones',   'bob@example.com',   'hashed_pwd_2', 'active', 1700000000, 1700000000),
('CUST-003', 'charlie_b',   'charlie@example.com', 'hashed_pwd_3', 'active', 1700000000, 1700000000),
-- Inactive/suspended user to test adversarial/policy refusal cases:
('CUST-999', 'bad_actor',   'suspended@example.com', 'hashed_pwd_9', 'inactive', 1700000000, 1700000000);

-- ----------------------------------------------------------------------------
-- 2. ORDERS (Designed to cover every policy transition boundary)
-- ----------------------------------------------------------------------------

-- ORD-101: Pending order. Total = $100.00 (10000 cents).
-- USE CASE: Valid for cancellation and shipping address update.
INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) VALUES
('ORD-101', 1728554400, 'CUST-001', 'pending', '123 Maple St, Seattle, WA 98101', 10000, NULL);

-- ORD-102: Shipped order. Total = $50.00 (5000 cents).
-- USE CASE: Invariant test. Policy forbids cancelling or address updates once shipped.
INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) VALUES
('ORD-102', 1728122400, 'CUST-001', 'shipped', '123 Maple St, Seattle, WA 98101', 5000, NULL);

-- ORD-103: Delivered recently (e.g. 14 days ago vs our frozen clock).
-- USE CASE: Valid for refund (within 30-day post-delivery policy window).
INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) VALUES
('ORD-103', 1727776800, 'CUST-002', 'delivered', '456 Oak Ave, Austin, TX 78701', 7500, '2026-10-01T12:00:00Z');

-- ORD-104: Delivered 75 days ago (expired refund window).
-- USE CASE: Policy refusal. Agent must explain it is past the 30-day refund window.
INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) VALUES
('ORD-104', 1722513600, 'CUST-002', 'delivered', '456 Oak Ave, Austin, TX 78701', 6000, '2026-08-01T12:00:00Z');

-- ORD-105: Delivered order with a pre-existing partial refund of $25.00.
-- USE CASE: Cumulative refund limit. Remaining refundable balance is exactly $25.00 (2500 cents).
INSERT INTO orders (order_id, created_at, user_id, status, shipping_address, total_amount_cents, delivered_at) VALUES
('ORD-105', 1728122400, 'CUST-003', 'delivered', '789 Pine Rd, Denver, CO 80201', 5000, '2026-10-05T12:00:00Z');

-- ----------------------------------------------------------------------------
-- 3. ORDER ITEMS
-- ----------------------------------------------------------------------------
INSERT INTO order_items (order_item_id, created_at, order_id, product_id, product_name, unit_price_cents, quantity) VALUES
('ITEM-101A', 1728554400, 'ORD-101', 'PROD-A', 'Mechanical Keyboard', 8000, 1),
('ITEM-101B', 1728554400, 'ORD-101', 'PROD-B', 'USB-C Cable', 2000, 1),
('ITEM-102A', 1728122400, 'ORD-102', 'PROD-C', 'Wireless Mouse', 5000, 1),
('ITEM-103A', 1727776800, 'ORD-103', 'PROD-D', 'Noise-Cancelling Headphones', 7500, 1),
('ITEM-104A', 1722513600, 'ORD-104', 'PROD-E', 'Desk Lamp', 6000, 1),
('ITEM-105A', 1728122400, 'ORD-105', 'PROD-F', 'Ergonomic Chair Cushion', 5000, 1);

-- ----------------------------------------------------------------------------
-- 4. REFUNDS
-- ----------------------------------------------------------------------------
-- Pre-existing refund on ORD-105: $25.00 out of $50.00 total.
INSERT INTO refunds (refund_id, order_id, amount_cents, reason, status, idempotency_key, created_at) VALUES
('REF-001', 'ORD-105', 2500, 'Item slightly scratched', 'approved', 'seed_idemp_key_001', 1728381600);
