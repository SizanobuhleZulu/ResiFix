# database.py
import sqlite3
import os
from config import Config

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    Config.DATABASE_NAME
)


def get_db():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with all tables"""
    conn = get_db()
    cursor = conn.cursor()

    # ===== USERS TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            block TEXT,
            room_number TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ===== ISSUES TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            issue_type TEXT,
            priority TEXT,
            status TEXT DEFAULT 'Open',
            block TEXT NOT NULL,
            room_number TEXT NOT NULL,
            image_path TEXT,
            image_damage_detected INTEGER DEFAULT 0,
            is_anonymous INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # ===== PROPOSALS TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            block TEXT NOT NULL,
            issues_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            generated_by TEXT DEFAULT 'LLM',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ===== VOTES TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            vote_type TEXT NOT NULL,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proposal_id) REFERENCES proposals(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # ===== NOTIFICATIONS TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ===== RATINGS TABLE =====
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            overall_rating INTEGER NOT NULL,
            ease_of_reporting INTEGER DEFAULT 0,
            ai_helpfulness INTEGER DEFAULT 0,
            response_satisfaction INTEGER DEFAULT 0,
            safety_advice_clarity INTEGER DEFAULT 0,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")