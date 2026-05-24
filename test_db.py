from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
users = db.query(User).all()
print("Users:", [{"id": u.id, "email": u.email, "is_active": u.is_active} for u in users])
