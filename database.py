import sqlite3
import os

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                country_code TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                selected_country TEXT,
                waiting_for_contact BOOLEAN DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, full_name, phone, country_code):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, full_name, phone, country_code)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, phone, country_code))
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    def set_user_country(self, user_id, country_code):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_sessions (user_id, selected_country, waiting_for_contact)
            VALUES (?, ?, 1)
        ''', (user_id, country_code))
        self.conn.commit()
    
    def is_waiting_for_contact(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT waiting_for_contact, selected_country FROM user_sessions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, None)
    
    def complete_registration(self, user_id, phone):
        cursor = self.conn.cursor()
        cursor.execute('SELECT selected_country FROM user_sessions WHERE user_id = ?', (user_id,))
        session = cursor.fetchone()
        
        if session:
            country_code = session[0]
            cursor.execute('UPDATE users SET phone = ?, country_code = ? WHERE user_id = ?', 
                         (phone, country_code, user_id))
            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            self.conn.commit()
            return country_code
        return None
    
    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]
    
    def get_users_by_country(self, country_code):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE country_code = ?', (country_code,))
        return [row[0] for row in cursor.fetchall()]
    
    def is_admin(self, user_id):
        from config import ADMIN_IDS
        return user_id in ADMIN_IDS
