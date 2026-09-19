# ============================================================
# database.py
# ------------------------------------------------------------
# This file sets up the connection to our SQLite database.
# It also gives us a "session" tool that other files will use
# to read and write data.
#
# Right now this points to SQLite (a single file on your laptop).
# Later, when we move to a server, we only change DATABASE_URL
# in config.py — this file stays the same.
# ============================================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings


# --- 1. Create the engine ---
# The engine is SQLAlchemy's way of talking to the database.
# connect_args is needed only for SQLite (it has a threading quirk).
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,  # set to True if you want to see every SQL query in the terminal
)


# --- 2. Create a session factory ---
# A "session" is a short conversation with the database.
# Each API request will get its own session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --- 3. Create the Base class ---
# Every database table (User, Property, etc.) will inherit from this.
# It's how SQLAlchemy knows which classes represent tables.
Base = declarative_base()


# --- 4. Dependency for FastAPI routes ---
# This function gives a database session to a route,
# then automatically closes it when the request is done.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()