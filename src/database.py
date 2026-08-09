import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
DB_PATH = os.path.join(DB_DIR, 'reels.db')

# Timeout in seconds for SQLite connections (prevents "database is locked" errors)
DB_TIMEOUT = 10


def _get_connection():
    """
    Returns a new SQLite connection with WAL mode and busy timeout configured.
    WAL mode allows concurrent readers with a single writer.
    """
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                seo_title TEXT,
                description TEXT,
                hashtags TEXT,
                upload_time DATETIME,
                facebook_url TEXT,
                status TEXT DEFAULT 'pending',
                file_hash TEXT UNIQUE
            )
        ''')

        # Run migration to add attempts column if it doesn't exist
        try:
            cursor.execute('ALTER TABLE reels ADD COLUMN attempts INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Run migration to add media_type column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE reels ADD COLUMN media_type TEXT DEFAULT 'reel'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()


def is_duplicate(filename, file_hash=None):
    with _get_connection() as conn:
        cursor = conn.cursor()
        if file_hash:
            cursor.execute(
                'SELECT status FROM reels WHERE filename = ? OR file_hash = ?',
                (filename, file_hash)
            )
        else:
            cursor.execute(
                'SELECT status FROM reels WHERE filename = ?',
                (filename,)
            )

        rows = cursor.fetchall()

    for row in rows:
        status = row[0]
        if status in ('uploaded', 'failed'):
            return True
    return False


def insert_media(filename, file_hash=None, media_type='reel'):
    """
    Inserts a new media record with status 'pending'. Returns True on success,
    False if the file already exists (IntegrityError) or insert failed.
    """
    with _get_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reels (filename, file_hash, status, attempts, media_type)
                VALUES (?, ?, 'pending', 0, ?)
            ''', (filename, file_hash, media_type))
            conn.commit()
            return cursor.lastrowid is not None and cursor.lastrowid > 0
        except sqlite3.IntegrityError:
            return False


def update_reel_metadata(filename, seo_title, description, hashtags):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reels
            SET seo_title = ?, description = ?, hashtags = ?
            WHERE filename = ?
        ''', (seo_title, description, hashtags, filename))
        conn.commit()


def mark_reel_uploaded(filename, facebook_url):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reels
            SET status = 'uploaded', facebook_url = ?, upload_time = ?, attempts = 0
            WHERE filename = ?
        ''', (facebook_url, datetime.now().isoformat(), filename))
        conn.commit()


def mark_reel_failed(filename):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reels
            SET status = 'failed'
            WHERE filename = ?
        ''', (filename,))
        conn.commit()


def get_daily_upload_count(media_type='reel', date_str=None):
    """
    Returns the number of successful uploads for the given media type on a given date.
    If date_str is not provided, uses today's date in the system's local timezone.
    Pass an explicit date_str (e.g. '2026-07-02') for timezone-correct counting.
    """
    with _get_connection() as conn:
        cursor = conn.cursor()
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM reels
            WHERE status = 'uploaded' AND date(upload_time) = ? AND media_type = ?
        ''', (date_str, media_type))
        count = cursor.fetchone()[0]
    return count


def get_reel_status(filename, file_hash=None):
    with _get_connection() as conn:
        cursor = conn.cursor()
        if file_hash:
            cursor.execute(
                'SELECT status, attempts FROM reels WHERE filename = ? OR file_hash = ?',
                (filename, file_hash)
            )
        else:
            cursor.execute(
                'SELECT status, attempts FROM reels WHERE filename = ?',
                (filename,)
            )
        row = cursor.fetchone()

    if row:
        return row[0], row[1]
    return None, 0


def increment_attempts(filename):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE reels
            SET attempts = attempts + 1
            WHERE filename = ?
        ''', (filename,))
        cursor.execute(
            'SELECT attempts FROM reels WHERE filename = ?',
            (filename,)
        )
        result = cursor.fetchone()
        attempts = result[0] if result else 0
        conn.commit()
    return attempts


def reset_attempts(filename):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE reels SET attempts = 0 WHERE filename = ?',
            (filename,)
        )
        conn.commit()


init_db()
