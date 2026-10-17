import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import check_database, engine

try:
    check_database()
    print("PostgreSQL: Online (SELECT 1 passed)")
except SQLAlchemyError:
    print("PostgreSQL: Offline. Check .env, credentials and database service.", file=sys.stderr)
    sys.exit(1)
finally:
    engine.dispose()
