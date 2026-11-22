import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("healthcare.db")

conn.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
""")

email = input("Enter admin email: ").strip().lower()
password = getpass("Create admin password: ")

if not email or len(password) < 8:
    print("Enter a valid email and password of at least 8 characters.")
else:
    conn.execute("""
        INSERT INTO admins (email, password)
        VALUES (?, ?)
        ON CONFLICT(email)
        DO UPDATE SET password = excluded.password
    """, (email, generate_password_hash(password)))

    conn.commit()
    print("Admin account created successfully!")

conn.close()