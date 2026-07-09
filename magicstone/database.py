import sqlite3
import os

DB_FOLDER = "database"
DB_NAME = "magicstone.db"
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)


def init_db():

    os.makedirs(DB_FOLDER, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    # ==========================
    # 매직스톤
    # ==========================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS stones(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,
            shape TEXT NOT NULL,
            grade TEXT NOT NULL,

            stat1 TEXT NOT NULL,
            value1 REAL NOT NULL,

            stat2 TEXT,
            value2 REAL,

            potential TEXT NOT NULL,
            potential_value REAL NOT NULL,

            owned INTEGER DEFAULT 1

        )

    """)

    # ==========================
    # 캐릭터 기본 능력치
    # ==========================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS settings(

            id INTEGER PRIMARY KEY,

            순격 REAL DEFAULT 0,
            강습 REAL DEFAULT 0,
            추상 REAL DEFAULT 0,

            근성 REAL DEFAULT 0,
            방감 REAL DEFAULT 0,
            요새 REAL DEFAULT 0

        )

    """)

    # 최초 1회 생성
    cursor.execute("""

        INSERT OR IGNORE INTO settings(

            id

        )

        VALUES(

            1

        )

    """)

    conn.commit()

    conn.close()


def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn