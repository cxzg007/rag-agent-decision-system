import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models import Base
from app.db.session import engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("database tables created")


if __name__ == "__main__":
    main()
