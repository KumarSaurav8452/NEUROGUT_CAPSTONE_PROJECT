"""
NEUROGUT -- Database Initialization & Seed Data
=================================================
Creates all tables and seeds demo hospital + 3 users (admin, clinician, researcher).
"""

import bcrypt

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
