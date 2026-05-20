import sqlite3
import bcrypt
import os
import sys

if getattr(sys, 'frozen', False):
    _DIR = os.path.dirname(sys.executable)
else:
    _DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(_DIR, 'users.db')


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        conn.commit()


def signup(username: str, password: str) -> tuple:
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(password) < 4:
        return False, "Password must be at least 4 characters"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, pw_hash)
            )
        return True, "Account created"
    except sqlite3.IntegrityError:
        return False, "Username already taken"


def login(username: str, password: str) -> tuple:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT password_hash FROM users WHERE username = ?', (username,)
        ).fetchone()
    if not row:
        return False, "User not found"
    if bcrypt.checkpw(password.encode(), row[0].encode()):
        return True, "Login successful"
    return False, "Incorrect password"
