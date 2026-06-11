"""
storage/database.py — Database manager
SQLite-based persistence for all agent activity
"""

from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from loguru import logger
from .models import Base

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "agent.db"


class DatabaseManager:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or f"sqlite:///{DB_PATH}"
        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
        self._SessionFactory = sessionmaker(bind=self.engine)
        self._init_db()

    def _init_db(self):
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized at {DB_PATH}")

    @contextmanager
    def session(self) -> Session:
        session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        return self._SessionFactory()

    def health_check(self) -> bool:
        try:
            with self.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"DB health check failed: {e}")
            return False


# Singleton
db = DatabaseManager()
