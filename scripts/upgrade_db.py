import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import Base
from app.db.session import engine


def add_column_if_missing(table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns(table)}
    if column in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    print(f"added column {table}.{column}")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    add_column_if_missing("chat_tasks", "task_type", "VARCHAR(64)")
    add_column_if_missing("chat_tasks", "citations", "JSONB")
    add_column_if_missing("chat_tasks", "reflections", "JSONB")
    print("database schema is up to date")


if __name__ == "__main__":
    main()
