#!/usr/bin/env python3
import uuid
from datetime import datetime
import sqlite3

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("Sharvari@123")
except ImportError:
    import hashlib
    hashed_password = hashlib.sha256("Sharvari@123".encode()).hexdigest()

conn = sqlite3.connect("dvc.db")
cursor = conn.cursor()

cursor.execute("SELECT id FROM users WHERE email = ?", ("sharvari.jiwtode@delphianalytics.in",))
existing = cursor.fetchone()

if existing:
    print(f"User already exists with ID: {existing[0]}")
    cursor.execute("UPDATE users SET role = 'admin', is_active = 1, name = 'Sharvari Jiwtode' WHERE email = ?", ("sharvari.jiwtode@delphianalytics.in",))
    print("Updated existing user to admin role")
else:
    user_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO users (id, email, name, hashed_password, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, "sharvari.jiwtode@delphianalytics.in", "Sharvari Jiwtode", hashed_password, "admin", 1, datetime.utcnow()))
    print(f"Created admin user:")
    print(f"  Email: sharvari.jiwtode@delphianalytics.in")
    print(f"  Password: Sharvari@123")
    print(f"  Role: admin")

conn.commit()
conn.close()
print("\n✓ Admin user ready!")
