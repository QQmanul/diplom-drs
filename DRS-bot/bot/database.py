import sqlite3
import json
from datetime import datetime
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        """Initialize database with required tables"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                token TEXT,
                role TEXT,
                full_name TEXT
            )
        ''')
        self.conn.commit()

    def save_user_auth(self, telegram_id: int, user_id: int, token: str, role: str, full_name: str):
        """Save or update user authentication data"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users (telegram_id, user_id, token, role, full_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, user_id, token, role, full_name))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving user auth: {e}")
            return False

    def get_user_auth(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user authentication data"""
        try:
            self.cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            row = self.cursor.fetchone()
            if row:
                return {
                    'telegram_id': row[0],
                    'user_id': row[1],
                    'token': row[2],
                    'role': row[3],
                    'full_name': row[4]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user auth: {e}")
            return None

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        self.cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'telegram_id': row[0],
                'user_id': row[1],
                'token': row[2],
                'role': row[3],
                'full_name': row[4]
            }
        return None

    def delete_user_auth(self, telegram_id: int) -> bool:
        """Delete user authentication data"""
        try:
            self.cursor.execute('DELETE FROM users WHERE telegram_id = ?', (telegram_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting user auth: {e}")
            return False

    def close(self):
        self.conn.close() 