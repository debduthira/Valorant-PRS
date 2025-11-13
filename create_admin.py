import psycopg2
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

username = input("Enter admin username: ").strip()
password = input("Enter admin password: ").strip()

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

query = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')"

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(query, (username, hashed))
        conn.commit()
        print(f"✅ Admin '{username}' created successfully!")
