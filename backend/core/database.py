"""SQLite Database layer for persistent storage, caches, and daily histories."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from .config import Config, DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cur = conn.cursor()

        # User settings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Weather cache table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weather_cache (
                location_key TEXT PRIMARY KEY,
                county TEXT NOT NULL,
                town TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Dining recommendations table (Module 2)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dining_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT NOT NULL,
                meal_period TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                radius INTEGER NOT NULL,
                places_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Recipe batches table (Module 3 - Every 2 hours)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recipe_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                recipes_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Module 3: Permanent Favorite Recipes (我的最愛，永久保留，不隨隔日歷史清理刪除)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS favorite_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_key TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                recipe_json TEXT NOT NULL,
                source_label TEXT NOT NULL DEFAULT '',
                saved_at TEXT NOT NULL
            )
        """)

        # Module 3: Custom Ingredient-Based Recipe Generations (輸入食材產出食譜紀錄)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS custom_recipe_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredients_input TEXT NOT NULL,
                ingredients_json TEXT NOT NULL,
                servings TEXT NOT NULL DEFAULT '2 人份',
                preference TEXT NOT NULL DEFAULT '',
                recipes_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Schedule execution log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cron_logs (
                job_key TEXT PRIMARY KEY,
                last_run_date TEXT NOT NULL,
                last_run_slot TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Module 4: Smart Shopping List (待買清單)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shopping_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity_note TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                auto_categorized INTEGER NOT NULL DEFAULT 1,
                location TEXT NOT NULL DEFAULT '全聯',
                urgency TEXT NOT NULL DEFAULT 'normal',
                urgency_rank INTEGER NOT NULL DEFAULT 2,
                source_recipe TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Module 4: Smart Shopping History (已購買歸檔與歷史紀錄)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shopping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity_note TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '全聯',
                urgency TEXT NOT NULL DEFAULT 'normal',
                price REAL,
                purchased_date TEXT NOT NULL,
                purchased_at TEXT NOT NULL
            )
        """)

        # Module 4: Custom & Remembered Shopping Locations (自訂地點清單與記憶功能)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shopping_locations (
                name TEXT PRIMARY KEY,
                is_online INTEGER NOT NULL DEFAULT 0,
                search_url_template TEXT NOT NULL DEFAULT '',
                is_pinned INTEGER NOT NULL DEFAULT 1,
                usage_count INTEGER NOT NULL DEFAULT 1,
                last_used_at TEXT NOT NULL
            )
        """)

        # Initialize default settings if missing
        now = datetime.now().isoformat()
        defaults = {
            "county": Config.DEFAULT_COUNTY,
            "town": Config.DEFAULT_TOWN,
            "lat": str(Config.DEFAULT_LAT),
            "lng": str(Config.DEFAULT_LNG),
            "radius": str(Config.DEFAULT_RADIUS_METERS),
        }
        for k, v in defaults.items():
            cur.execute(
                "INSERT OR IGNORE INTO user_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (k, v, now),
            )


def get_settings() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM user_settings").fetchall()
        res = {r["key"]: r["value"] for r in rows}
        return {
            "county": res.get("county", Config.DEFAULT_COUNTY),
            "town": res.get("town", Config.DEFAULT_TOWN),
            "lat": float(res.get("lat", Config.DEFAULT_LAT)),
            "lng": float(res.get("lng", Config.DEFAULT_LNG)),
            "radius": int(res.get("radius", Config.DEFAULT_RADIUS_METERS)),
        }


def update_settings(new_settings: dict) -> dict:
    now = datetime.now().isoformat()
    with get_db() as conn:
        for k in ("county", "town", "lat", "lng", "radius"):
            if k in new_settings and new_settings[k] is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO user_settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (k, str(new_settings[k]), now),
                )
    return get_settings()


def cleanup_previous_days(today_str: str) -> dict:
    """Cleanup history before today_str (runs automatically at 00:00 / 05:59 or on date rollover)."""
    with get_db() as conn:
        c1 = conn.execute("DELETE FROM recipe_batches WHERE date_str < ?", (today_str,)).rowcount
        c2 = conn.execute("DELETE FROM dining_recommendations WHERE date_str < ?", (today_str,)).rowcount
        return {"deleted_recipe_batches": c1, "deleted_dining_batches": c2, "kept_from_date": today_str}
