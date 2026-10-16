import unittest
from decimal import Decimal
from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.engine.exceptions import (
    SQLSecurityError,
    SQLValidationError,
    SQLExecutionError,
)
from app.engine.validator import (
    remove_sql_comments,
    validate_safe_sql,
    extract_referenced_tables,
    extract_cte_names,
)
from app.engine.runner import execute_safe_sql
from app.main import execute_query
from app.models import Customer, Product, Order, OrderItem
from app.schemas.query import QueryExecuteRequest


class TestSafeSQLEngine(unittest.TestCase):

    def setUp(self):
        # Set up in-memory SQLite database populated with test records
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Seed minimal data
        c = Customer(first_name="Alice", last_name="Smith", email="alice@example.com")
        p = Product(name="Chair", category="Furniture", price=Decimal("150.00"), cost=Decimal("70.00"))
        self.session.add_all([c, p])
        self.session.flush()

        o = Order(customer_id=c.id, status="completed", total_amount=Decimal("150.00"))
        self.session.add(o)
        self.session.flush()

        item = OrderItem(order_id=o.id, product_id=p.id, quantity=1, unit_price=Decimal("150.00"))
        self.session.add(item)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    # 1. Comment Stripping Tests
    def test_remove_sql_comments(self):
        sql_with_line_comment = "SELECT * FROM customers -- this is a comment\nWHERE id = 1"
        cleaned_line = remove_sql_comments(sql_with_line_comment)
        self.assertEqual(
            " ".join(cleaned_line.split()),
            "SELECT * FROM customers WHERE id = 1",
        )

        sql_with_block_comment = "SELECT * FROM /* comment */ customers WHERE id = 1"
        cleaned_block = remove_sql_comments(sql_with_block_comment)
        self.assertEqual(
            " ".join(cleaned_block.split()),
            "SELECT * FROM customers WHERE id = 1",
        )

        sql_with_string_containing_dashes = "SELECT '-- not a comment' FROM customers"
        self.assertEqual(
            remove_sql_comments(sql_with_string_containing_dashes),
            "SELECT '-- not a comment' FROM customers",
        )

    # 2. Table and CTE Extraction Tests
    def test_table_extraction(self):
        sql = "SELECT c.name, o.id FROM customers c JOIN orders o ON c.id = o.customer_id"
        tables = extract_referenced_tables(sql)
        self.assertEqual(tables, {"customers", "orders"})

        sql_comma = "SELECT * FROM customers, orders, order_items WHERE customers.id = 1"
        tables_comma = extract_referenced_tables(sql_comma)
        self.assertEqual(tables_comma, {"customers", "orders", "order_items"})

    def test_cte_extraction(self):
        sql = "WITH regional_sales AS (SELECT * FROM orders), top_cust AS (SELECT * FROM customers) SELECT * FROM regional_sales"
        ctes = extract_cte_names(sql)
        self.assertEqual(ctes, {"regional_sales", "top_cust"})

    # 3. Validation Success Cases
    def test_valid_select_query(self):
        sql = "SELECT id, first_name, email FROM customers WHERE country = 'United States'"
        validated = validate_safe_sql(sql)
        self.assertTrue(validated.startswith("SELECT"))
        self.assertIn("LIMIT 100", validated)

    def test_valid_join_query(self):
        sql = """
        SELECT c.first_name, p.name, oi.quantity, oi.unit_price
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.status = 'completed'
        """
        validated = validate_safe_sql(sql)
        self.assertIn("JOIN order_items", validated)
        self.assertIn("LIMIT 100", validated)

    def test_valid_cte_query(self):
        sql = """
        WITH customer_totals AS (
            SELECT customer_id, SUM(total_amount) AS total_spent
            FROM orders
            GROUP BY customer_id
        )
        SELECT c.first_name, ct.total_spent
        FROM customers c
        JOIN customer_totals ct ON c.id = ct.customer_id
        """
        validated = validate_safe_sql(sql)
        self.assertTrue(validated.upper().startswith("WITH"))
        self.assertIn("LIMIT 100", validated)

    # 4. Security Guardrail Tests
    def test_reject_mutating_keywords(self):
        mutating_statements = [
            "DROP TABLE customers",
            "DELETE FROM orders WHERE id = 1",
            "UPDATE products SET price = 0",
            "INSERT INTO customers (first_name) VALUES ('Hacker')",
            "ALTER TABLE orders ADD COLUMN hack text",
            "TRUNCATE TABLE order_items",
            "CREATE TABLE evil (id int)",
            "GRANT ALL PRIVILEGES ON customers TO public",
        ]
        for stmt in mutating_statements:
            with self.subTest(statement=stmt):
                with self.assertRaises(SQLSecurityError):
                    validate_safe_sql(stmt)

    def test_reject_multiple_statements_semicolon(self):
        stacked_sql = "SELECT * FROM customers; DROP TABLE orders;"
        with self.assertRaises(SQLSecurityError):
            validate_safe_sql(stacked_sql)

    def test_reject_unapproved_tables(self):
        unapproved_queries = [
            "SELECT * FROM users",
            "SELECT * FROM pg_shadow",
            "SELECT * FROM accounts",
            "SELECT c.id, u.secret FROM customers c JOIN secrets u ON c.id = u.id",
        ]
        for query in unapproved_queries:
            with self.subTest(query=query):
                with self.assertRaises(SQLSecurityError):
                    validate_safe_sql(query)

    def test_reject_dangerous_system_functions(self):
        dangerous_queries = [
            "SELECT pg_sleep(5) FROM customers",
            "SELECT pg_read_file('/etc/passwd') FROM customers",
            "SELECT * FROM pg_catalog.pg_tables",
            "SELECT * FROM information_schema.tables",
        ]
        for query in dangerous_queries:
            with self.subTest(query=query):
                with self.assertRaises(SQLSecurityError):
                    validate_safe_sql(query)

    def test_reject_mutating_cte(self):
        sql = "WITH deleted AS (DELETE FROM customers RETURNING *) SELECT * FROM deleted"
        with self.assertRaises(SQLSecurityError):
            validate_safe_sql(sql)

    def test_reject_empty_query(self):
        with self.assertRaises(SQLValidationError):
            validate_safe_sql("")
        with self.assertRaises(SQLValidationError):
            validate_safe_sql("   -- just comment\n   /* block */  ")

    # 5. Row Limit Tests
    def test_limit_injection_and_clamping(self):
        # Injects default limit
        res1 = validate_safe_sql("SELECT * FROM customers")
        self.assertTrue(res1.endswith("LIMIT 100"))

        # Preserves limit within bounds
        res2 = validate_safe_sql("SELECT * FROM customers LIMIT 25")
        self.assertIn("LIMIT 25", res2)

        # Clamps limit exceeding max limit
        res3 = validate_safe_sql("SELECT * FROM customers LIMIT 50000")
        self.assertIn("LIMIT 100", res3)
        self.assertNotIn("LIMIT 50000", res3)

        # Clamps limit 500 to 100
        res4 = validate_safe_sql("SELECT * FROM customers LIMIT 500")
        self.assertIn("LIMIT 100", res4)
        self.assertNotIn("LIMIT 500", res4)

    # 6. Safe Execution Tests
    def test_execute_safe_sql_live_query(self):
        sql = "SELECT c.first_name, o.total_amount FROM customers c JOIN orders o ON c.id = o.customer_id"
        result = execute_safe_sql(self.session, sql)

        self.assertEqual(result.columns, ["first_name", "total_amount"])
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.rows[0]["first_name"], "Alice")
        self.assertEqual(result.rows[0]["total_amount"], 150.00)
        self.assertGreaterEqual(result.execution_time_ms, 0.0)
        self.assertIn("LIMIT 100", result.executed_query)

    def test_execute_safe_sql_syntax_error(self):
        # Query with valid table and keywords but malformed syntax
        bad_sql = "SELECT non_existent_col FROM customers WHERE ("
        with self.assertRaises(SQLExecutionError):
            execute_safe_sql(self.session, bad_sql)

    # 7. API Endpoint Tests
    def test_api_execute_query_success(self):
        req = QueryExecuteRequest(query="SELECT name, price FROM products", row_limit=10)
        resp = execute_query(request=req, db=self.session)

        self.assertTrue(resp.success)
        self.assertEqual(resp.columns, ["name", "price"])
        self.assertEqual(resp.row_count, 1)
        self.assertEqual(resp.rows[0]["name"], "Chair")
        self.assertEqual(resp.rows[0]["price"], 150.0)

    def test_api_execute_query_blocked_security(self):
        req = QueryExecuteRequest(query="DROP TABLE customers")
        with self.assertRaises(HTTPException) as ctx:
            execute_query(request=req, db=self.session)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Forbidden operation 'DROP'", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
