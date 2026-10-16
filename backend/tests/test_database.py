import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.deps import get_db
from app.main import root, health, health_db
from app.models import Customer, Product, Order, OrderItem
from app.schemas import CustomerRead, ProductRead, OrderRead, OrderItemRead


class TestDatabaseFoundation(unittest.TestCase):

    def test_settings_configuration(self):
        """Verify that Settings loads expected environment values and config keys."""
        self.assertEqual(settings.APP_NAME, "MetricMind API")
        self.assertEqual(settings.APP_VERSION, "0.1.0")
        self.assertIsNotNone(settings.DATABASE_URL)
        self.assertIn("metricmind", settings.DATABASE_URL)

    def test_sql_files_exist_and_contain_ddl(self):
        """Verify that db/schema.sql and db/seed.sql exist and contain required tables and data."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        schema_path = root_dir / "db" / "schema.sql"
        seed_path = root_dir / "db" / "seed.sql"

        self.assertTrue(schema_path.exists(), "db/schema.sql must exist")
        self.assertTrue(seed_path.exists(), "db/seed.sql must exist")

        schema_content = schema_path.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS customers", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS products", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS orders", schema_content)
        self.assertIn("CREATE TABLE IF NOT EXISTS order_items", schema_content)

        seed_content = seed_path.read_text(encoding="utf-8")
        self.assertIn("INSERT INTO customers", seed_content)
        self.assertIn("INSERT INTO products", seed_content)
        self.assertIn("INSERT INTO orders", seed_content)
        self.assertIn("INSERT INTO order_items", seed_content)

    def test_models_and_relationships_in_memory(self):
        """Verify SQLAlchemy 2.0 models, relations, and operations using an in-memory SQLite DB."""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # 1. Create Customer
            customer = Customer(
                first_name="Jane",
                last_name="Doe",
                email="jane.doe@example.com",
                city="Seattle",
                state="WA",
                country="United States",
            )
            session.add(customer)
            session.flush()

            # 2. Create Product
            product = Product(
                name="Mechanical Keyboard",
                category="Electronics",
                price=Decimal("129.99"),
                cost=Decimal("55.00"),
                stock_quantity=100,
            )
            session.add(product)
            session.flush()

            # 3. Create Order
            order = Order(
                customer_id=customer.id,
                status="completed",
                total_amount=Decimal("129.99"),
            )
            session.add(order)
            session.flush()

            # 4. Create Order Item
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=1,
                unit_price=Decimal("129.99"),
            )
            session.add(item)
            session.commit()

            # 5. Query and verify relationships
            retrieved = session.query(Order).filter_by(id=order.id).first()
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.customer.email, "jane.doe@example.com")
            self.assertEqual(len(retrieved.items), 1)
            self.assertEqual(retrieved.items[0].product.name, "Mechanical Keyboard")
            self.assertEqual(retrieved.items[0].unit_price, Decimal("129.99"))

            # Test Pydantic schema validation from ORM
            customer_schema = CustomerRead.model_validate(retrieved.customer)
            self.assertEqual(customer_schema.first_name, "Jane")
            self.assertEqual(customer_schema.email, "jane.doe@example.com")

            product_schema = ProductRead.model_validate(product)
            self.assertEqual(product_schema.name, "Mechanical Keyboard")
            self.assertEqual(product_schema.price, Decimal("129.99"))

    def test_get_db_generator_lifecycle(self):
        """Verify that get_db yields a session and reliably executes close() in finally."""
        gen = get_db()
        session = next(gen)
        self.assertIsNotNone(session)
        # Completing generator triggers finally block
        with self.assertRaises(StopIteration):
            next(gen)

    def test_api_root_and_health_endpoints(self):
        """Verify root and health handler responses."""
        self.assertEqual(root(), {"message": "MetricMind API is running"})
        self.assertEqual(health(), {"status": "healthy"})

    def test_api_health_db_success(self):
        """Verify /health/db returns connected status when session executes successfully."""
        mock_db = MagicMock()
        mock_db.execute.return_value = None
        result = health_db(db=mock_db)
        self.assertEqual(result, {"status": "healthy", "database": "connected"})
        mock_db.execute.assert_called_once()

    def test_api_health_db_failure(self):
        """Verify /health/db raises HTTPException 503 when database execution errors."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Connection refused")
        with self.assertRaises(HTTPException) as ctx:
            health_db(db=mock_db)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "Database connection failed")


if __name__ == "__main__":
    unittest.main()
