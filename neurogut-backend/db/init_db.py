"""
NEUROGUT -- Database Initialization & Seed Data
=================================================
Creates all tables and seeds demo hospital + 3 users (admin, clinician, researcher).
v4.0: Adds migration for status, invite_token_hash, invite_expires_at columns.
"""

import bcrypt
from sqlalchemy import text, inspect

from db.database import engine, SessionLocal, Base
from db.models import Hospital, User


def _hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("[DB] All tables created.")


def migrate_v4():
    """
    v4.0 migration:
      1. Add status, invite_token_hash, invite_expires_at columns if missing.
      2. Make password_hash nullable (SQLite requires table rebuild for this).
    """
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return  # Table doesn't exist yet; create_all will handle it

    existing_cols = {col["name"] for col in insp.get_columns("users")}

    # --- Step 1: Add missing columns ---
    col_migrations = []
    if "status" not in existing_cols:
        col_migrations.append(
            "ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
        )
    if "invite_token_hash" not in existing_cols:
        col_migrations.append(
            "ALTER TABLE users ADD COLUMN invite_token_hash TEXT"
        )
    if "invite_expires_at" not in existing_cols:
        col_migrations.append(
            "ALTER TABLE users ADD COLUMN invite_expires_at DATETIME"
        )

    if col_migrations:
        with engine.begin() as conn:
            for sql in col_migrations:
                conn.execute(text(sql))
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE users SET status = 'active' WHERE status IS NULL OR status = ''"
            ))
        print(f"[DB] v4.0 migration: {len(col_migrations)} columns added.")

    # --- Step 2: Rebuild table to make password_hash nullable ---
    # Check if password_hash is currently NOT NULL in the actual table DDL.
    # SQLite inspect doesn't reliably report nullable, so we check the raw SQL.
    needs_rebuild = False
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ))
        ddl = result.scalar() or ""
        # If password_hash TEXT NOT NULL is in the DDL, we need to rebuild
        if "password_hash" in ddl and "NOT NULL" in ddl:
            # More precise check: find 'password_hash' followed by NOT NULL
            import re
            if re.search(r"password_hash\s+\w+\s+NOT\s+NULL", ddl, re.IGNORECASE):
                needs_rebuild = True

    if needs_rebuild:
        print("[DB] v4.0 migration: rebuilding users table (password_hash → nullable)...")
        with engine.begin() as conn:
            # Get current column list from the refreshed inspect
            insp2 = inspect(engine)
            cols = [col["name"] for col in insp2.get_columns("users")]
            col_list = ", ".join(cols)

            conn.execute(text("ALTER TABLE users RENAME TO users_old"))
            # Recreate table from model definition (has nullable password_hash)
            from db.models import User
            User.__table__.create(bind=engine, checkfirst=False)
            conn.execute(text(f"INSERT INTO users ({col_list}) SELECT {col_list} FROM users_old"))
            conn.execute(text("DROP TABLE users_old"))
        print("[DB] v4.0 migration: users table rebuilt successfully.")
    else:
        print("[DB] v4.0: password_hash already nullable — no rebuild needed.")



def seed_demo_data():
    """Seed a demo hospital and 3 users if they don't exist."""
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(Hospital).filter_by(subdomain="demo").first()
        if existing:
            print("[DB] Demo data already exists, skipping seed.")
            return

        # Create demo hospital
        hospital = Hospital(
            id="h-demo-001",
            name="NEUROGUT Demo Hospital",
            subdomain="demo",
            logo_url="",
            settings_json={"notifications": True, "risk_threshold": 0.5},
        )
        db.add(hospital)
        db.flush()

        # Create 3 demo users
        users = [
            User(
                id="u-admin-001",
                hospital_id=hospital.id,
                email="admin@neurogut.demo",
                password_hash=_hash_password("admin123"),
                role="admin",
                full_name="Dr. Admin Kumar",
                is_active=True,
            ),
            User(
                id="u-clinician-001",
                hospital_id=hospital.id,
                email="clinician@neurogut.demo",
                password_hash=_hash_password("clinician123"),
                role="clinician",
                full_name="Dr. Priya Sharma",
                is_active=True,
            ),
            User(
                id="u-researcher-001",
                hospital_id=hospital.id,
                email="researcher@neurogut.demo",
                password_hash=_hash_password("researcher123"),
                role="researcher",
                full_name="Dr. Rahul Mehta",
                is_active=True,
            ),
        ]
        db.add_all(users)
        db.commit()
        print("[DB] Demo hospital + 3 users seeded.")
        print("     admin@neurogut.demo / admin123")
        print("     clinician@neurogut.demo / clinician123")
        print("     researcher@neurogut.demo / researcher123")

    except Exception as e:
        db.rollback()
        print(f"[DB] Seed error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_demo_data()
