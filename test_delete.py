from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.id == 5).first()
if user:
    print(f"Deleting user 5... ({user.email})")
    try:
        db.delete(user)
        db.commit()
        print("Deleted!")
    except Exception as e:
        print("Error:", e)
else:
    print("User not found.")
