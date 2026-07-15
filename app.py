from urllib.parse import quote, unquote
from fastapi import UploadFile, File
import shutil
from fastapi import FastAPI, Request, Form, Cookie, Query, Response
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    FileResponse,
    JSONResponse
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import sqlite3
import random
import hashlib
import json
import os

from database import get_db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional

# 라우터
from routers import magicstone

# FastAPI 생성
app = FastAPI()


# 라우터 등록
app.include_router(magicstone.router)

# 정적 파일
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# 템플릿
templates = Jinja2Templates(directory="templates")

# 관리자 비밀번호
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "4470")






def init_db():

    conn = get_db()
    cur = conn.cursor()

    # =========================
    # 회원
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,

        role TEXT DEFAULT 'member',

        contribution_points INTEGER DEFAULT 0,

        equipment_ticket INTEGER DEFAULT 0,
        emblem_ticket INTEGER DEFAULT 0,

        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =========================
    # 아이템
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT,
        category TEXT,
        item_quantity INTEGER DEFAULT 1
    )
    """)

    # =========================
    # 아이템 마스터
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_master(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        item_name TEXT NOT NULL
    )
    """)

    # =========================
    # 신청
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        item_name TEXT,
        entry_number TEXT,
        quantity INTEGER DEFAULT 1,
        contribution_used INTEGER DEFAULT 0,
        ticket_type TEXT DEFAULT ''
    )
    """)

    # =========================
    # 당첨자
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS winners(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        item_name TEXT,
        entry_number TEXT
    )
    """)

    # =========================
    # 경매 설정
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS auction_settings(
        id INTEGER PRIMARY KEY,
        status TEXT DEFAULT 'stopped',
        auto_reveal INTEGER DEFAULT 1,
        reveal_minutes INTEGER DEFAULT 10,
        start_time TEXT,
        end_time TEXT
    )
    """)

    cur.execute("""
    INSERT OR IGNORE INTO auction_settings(
        id,
        status,
        auto_reveal,
        reveal_minutes
    )
    VALUES(
        1,
        'stopped',
        1,
        10
    )
    """)

    # =========================
    # 오늘의 행운 출석
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_lucky(
        lucky_date TEXT PRIMARY KEY,
        nickname TEXT NOT NULL
    )
    """)

    # =========================
    # 기여도 변동 로그
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contribution_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =========================
    # 매직스톤
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS magic_user_stones(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nickname TEXT NOT NULL,

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

    # =========================
    # 매직스톤 기본 능력치
    # =========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS magic_user_settings(

        nickname TEXT PRIMARY KEY,

        순격 REAL DEFAULT 0,
        강습 REAL DEFAULT 0,
        추상 REAL DEFAULT 0,

        근성 REAL DEFAULT 0,
        방감 REAL DEFAULT 0,
        요새 REAL DEFAULT 0

    )
    """)

    # =====================================
    # 기존 DB 자동 업데이트 (Render 포함)
    # =====================================

    migrations = [

        # users
        "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'member'",
        "ALTER TABLE users ADD COLUMN reserved_points INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_attendance TEXT",
        "ALTER TABLE users ADD COLUMN equipment_ticket INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN emblem_ticket INTEGER DEFAULT 0",

        # entries
        "ALTER TABLE entries ADD COLUMN quantity INTEGER DEFAULT 1",
        "ALTER TABLE entries ADD COLUMN contribution_used INTEGER DEFAULT 0",
        "ALTER TABLE entries ADD COLUMN ticket_type TEXT DEFAULT ''",

        # items
        "ALTER TABLE items ADD COLUMN item_quantity INTEGER DEFAULT 1",
    ]

    for sql in migrations:
        try:
            cur.execute(sql)
        except:
            pass

    conn.commit()
    conn.close()


init_db()




def get_category(item_name):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT category FROM items WHERE item_name=?",
        (item_name,)
    )

    row = cur.fetchone()

    conn.close()

    return row[0] if row else ""

def round_robin_distribution(applicants, total_qty):

    result = {}

    for nickname, qty in applicants:
        result[nickname] = 0

    remaining = {
        nickname: qty
        for nickname, qty in applicants
    }

    while total_qty > 0:

        distributed = False

        for nickname in remaining:

            if remaining[nickname] > 0 and total_qty > 0:

                result[nickname] += 1
                remaining[nickname] -= 1
                total_qty -= 1

                distributed = True

        if not distributed:
            break

    return result


def run_draw():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM winners")

    cur.execute("""
    SELECT item_name, category, item_quantity
    FROM items
    """)

    items = cur.fetchall()

    for item_name, category, item_quantity in items:

        # 기타  품목
        if category == "기타":

            cur.execute(
                """
                SELECT nickname, quantity
                FROM entries
                WHERE item_name=?
                """,
                (item_name,)
            )

            applicants = cur.fetchall()

            if not applicants:

                cur.execute(
                    """
                    INSERT INTO winners
                    (nickname,item_name,entry_number)
                    VALUES (?,?,?)
                    """,
                    ("유찰", item_name, "-")
                )

                continue

            distributed = round_robin_distribution(
                applicants,
                item_quantity
            )

            for nickname, qty in distributed.items():

                if qty <= 0:
                    continue

                cur.execute(
                    """
                    INSERT INTO winners
                    (nickname,item_name,entry_number)
                    VALUES (?,?,?)
                    """,
                    (
                        nickname,
                        item_name,
                        f"{qty}개 지급"
                    )
                )

        # 장비 / 악세 / 엠블럼
        else:

            cur.execute(
                """
                SELECT
                    nickname,
                    item_name,
                    entry_number,
                    contribution_used,
                    ticket_type
                FROM entries
                WHERE item_name=?
                """,
                (item_name,)
            )

            applicants = cur.fetchall()

            if not applicants:

                cur.execute(
                    """
                    INSERT INTO winners
                    (nickname,item_name,entry_number)
                    VALUES (?,?,?)
                    """,
                    ("유찰", item_name, "-")
                )

                continue

            # ==========================
            # 강화입찰권 신청자 우선
            # ==========================

            ticket_users = []

            point_users = []

            for a in applicants:

                if a[4] != "":
                    ticket_users.append(a)

                else:
                    point_users.append(a)

            # 강화입찰권 사용자가 있으면
            if ticket_users:

                random.shuffle(ticket_users)

                selected = ticket_users[:item_quantity]

                for winner in selected:

                    cur.execute(
                        """
                        INSERT INTO winners
                        (nickname,item_name,entry_number)
                        VALUES (?,?,?)
                        """,
                        (
                            winner[0],
                            winner[1],
                            winner[2]
                        )
                    )

                    # 당첨자만 티켓 차감
                    if winner[4] == "equipment":

                        cur.execute("""
                        UPDATE users
                        SET equipment_ticket =
                            MAX(0, equipment_ticket-1)
                        WHERE nickname=?
                        """,
                        (winner[0],))

                    elif winner[4] == "emblem":

                        cur.execute("""
                        UPDATE users
                        SET emblem_ticket =
                            MAX(0, emblem_ticket-1)
                        WHERE nickname=?
                        """,
                        (winner[0],))

                continue

            # ==========================
            # 기존 기여도 추첨
            # ==========================

            applicants = point_users

            # 기여도 높은 순으로 정렬
            applicants = sorted(
                applicants,
                key=lambda x: x[3],
                reverse=True
            )

            selected = []

            remaining = applicants

            while len(selected) < item_quantity and remaining:

                highest = remaining[0][3]

                same_score = [
                    a for a in remaining
                    if a[3] == highest
                ]

                random.shuffle(same_score)

                need = item_quantity - len(selected)

                selected.extend(same_score[:need])

                selected_names = {
                    (x[0], x[2]) for x in same_score[:need]
                }

                remaining = [
                    a for a in remaining
                    if (a[0], a[2]) not in selected_names
                ]

            # 당첨자 저장 + 기여도 차감
            for winner in selected:

                cur.execute(
                    """
                    INSERT INTO winners
                    (nickname,item_name,entry_number)
                    VALUES (?,?,?)
                    """,
                    (
                        winner[0],
                        winner[1],
                        winner[2]
                    )
                )

                cur.execute(
                    """
                    UPDATE users
                    SET contribution_points =
                        MAX(0, contribution_points - ?)
                    WHERE nickname=?
                    """,
                    (
                        winner[3],
                        winner[0]
                    )
                )

                if winner[3] > 0:
                    add_contribution_log(
                        cur,
                        winner[0],
                        -winner[3],
                        f"{winner[1]} 당첨"
                    )        

    # 신청내역 삭제
    cur.execute("DELETE FROM entries")

    conn.commit()
    conn.close()                

def add_contribution_log(cur, nickname, amount, reason):

    cur.execute(
        """
        INSERT INTO contribution_logs
        (nickname, amount, reason)
        VALUES (?,?,?)
        """,
        (
            nickname,
            amount,
            reason
        )
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page():

    return """
    <html>
    <body>
    <h2>관리자 로그인</h2>

    <form action="/login" method="post">
    비밀번호
    <input type="password" name="password">
    <button type="submit">로그인</button>
    </form>

    </body>
    </html>
    """


@app.post("/login")
async def login(password: str = Form(...)):

    if password == ADMIN_PASSWORD:

        response = RedirectResponse(
            "/admin",
            status_code=303
        )

        response.set_cookie(
            key="admin",
            value="yes"
        )

        return response

    return HTMLResponse(
        "<h2>비밀번호가 틀렸습니다.</h2>"
    )


@app.get("/logout")
async def logout():

    response = RedirectResponse(
        "/login",
        status_code=303
    )

    response.delete_cookie("admin")

    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>회원가입</title>
    </head>
    <body>
        <h2>회원가입</h2>

        <form action="/register" method="post">

            <p>닉네임</p>
            <input
                type="text"
                name="nickname"
                required>

            <p>비밀번호</p>
            <input
                type="password"
                name="password"
                required>

            <br><br>

            <button type="submit">
                회원가입
            </button>

        </form>

        <br>

        <a href="/user_login">
            로그인
        </a>

    </body>
    </html>
    """


@app.post("/register")
async def register(
    nickname: str = Form(...),
    password: str = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    # 닉네임 중복 확인
    cur.execute(
        "SELECT id FROM users WHERE nickname=?",
        (nickname,)
    )

    if cur.fetchone():
        conn.close()
        return HTMLResponse(
            "<h3>이미 사용중인 닉네임입니다.</h3>"
        )

    # 비밀번호 해시
    password_hash = hashlib.sha256(
        password.encode()
    ).hexdigest()

    # 회원 저장
    cur.execute(
        """
        INSERT INTO users
        (
            nickname,
            password
        )
        VALUES
        (?,?)
        """,
        (
            nickname,
            password_hash
        )
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/user_login",
        status_code=303
    )

@app.get("/user_login", response_class=HTMLResponse)
async def user_login_page():
    return """
    <h2>회원 로그인</h2>

    <form action="/user_login" method="post">
        <p>닉네임</p>
        <input type="text" name="nickname" required>

        <p>비밀번호</p>
        <input type="password" name="password" required>

        <br><br>

        <button type="submit">로그인</button>
    </form>

    <br>

    <a href="/register">회원가입</a>
    """


@app.post("/user_login")
async def user_login(
    nickname: str = Form(...),
    password: str = Form(...)
):

    password_hash = hashlib.sha256(
        password.encode()
    ).hexdigest()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, nickname
        FROM users
        WHERE nickname=?
        AND password=?
        """,
        (
            nickname,
            password_hash
        )
    )

    user = cur.fetchone()

    conn.close()

    if not user:
        return HTMLResponse(
            "<h3>닉네임 또는 비밀번호가 올바르지 않습니다.</h3>"
        )

    response = RedirectResponse(
        "/",
        status_code=303
    )

    response.set_cookie(
        key="user",
        value=quote(nickname),   # ✅ 한글 안전하게 저장
        httponly=True
    )

    return response


@app.get("/user_logout")
async def user_logout():

    response = RedirectResponse(
        "/",
        status_code=303
    )

    response.delete_cookie("user")

    return response

@app.get("/attendance")
async def attendance(
    user: str = Cookie(None)
):
    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    conn = get_db()
    cur = conn.cursor()

    today = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d")

    # 오늘 이미 출석했는지 확인
    cur.execute("""
    SELECT last_attendance
    FROM users
    WHERE nickname=?
    """, (nickname,))

    row = cur.fetchone()

    if row and row[0] == today:
        conn.close()
        return RedirectResponse("/?attendance=already", status_code=303)

    # 오늘 행운 당첨자가 있는지 확인
    cur.execute("""
    SELECT nickname
    FROM daily_lucky
    WHERE lucky_date=?
    """, (today,))

    lucky = cur.fetchone()

    # 기본 지급 포인트
    point = 1
    attendance_result = "success"

    # 아직 당첨자가 없으면 7% 확률
    if not lucky:
        if random.randint(1, 100) <= 7:

            point = 3
            attendance_result = "lucky"

            cur.execute("""
            INSERT INTO daily_lucky(
                lucky_date,
                nickname
            )
            VALUES(?,?)
            """, (
                today,
                nickname
            ))

    if point == 3:
        add_contribution_log(
            cur,
            nickname,
            3,
            "행운 출석"
        )
    else:
        add_contribution_log(
            cur,
            nickname,
            1,
            "출석체크"
        )       

    # 출석 처리
    cur.execute("""
    UPDATE users
    SET
        contribution_points = contribution_points + ?,
        last_attendance = ?
    WHERE nickname=?
    """, (
        point,
        today,
        nickname
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        f"/?attendance={attendance_result}",
        status_code=303
    )

@app.head("/")
async def head_root():
    return Response(status_code=200)

@app.head("/admin")
async def head_admin():
    return Response(status_code=200)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    attendance: str = Query(None),
    user: str = Cookie(None)
):

    conn = get_db()
    cur = conn.cursor()

    today = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d")

    # 품목 목록
    cur.execute("""
    SELECT
        i.item_name,
        i.category,
        COUNT(e.id) AS entry_count,
        i.item_quantity
    FROM items i
    LEFT JOIN entries e
        ON i.item_name = e.item_name
    GROUP BY
        i.item_name,
        i.category,
        i.item_quantity
    ORDER BY i.category
    """)

    items = cur.fetchall()

    # ⭐ 경매 상태 조회
    cur.execute("""
    SELECT status, end_time
    FROM auction_settings
    WHERE id=1
    """)

    auction = cur.fetchone()

    auction_status = "stopped"
    auction_end_time = ""

    if auction:
        auction_status = auction[0]
        auction_end_time = auction[1] or ""
        print(auction_status)
        print(auction_end_time)

    # 당첨 결과
    cur.execute("""
    SELECT
        w.nickname,
        w.item_name,
        w.entry_number,
        i.category
    FROM winners w
    LEFT JOIN items i
        ON w.item_name = i.item_name
    ORDER BY w.item_name ASC, w.nickname ASC
    """)

    rows = cur.fetchall()

    # 오늘의 행운 출석 당첨자 조회
    cur.execute("""
    SELECT nickname
    FROM daily_lucky
    WHERE lucky_date=?
    """, (today,))

    row = cur.fetchone()

    lucky_user = row[0] if row else None

    # 현재 로그인한 사용자의 정보 조회
    contribution_points = 0
    used_points = 0
    available_points = 0
    attendance_done = False
    role = "member"

    equipment_ticket = 0
    emblem_ticket = 0

    if user:

        decoded_user = unquote(user)

        # 총 기여도 + 권한 + 강화입찰권
        cur.execute("""
        SELECT
            contribution_points,
            role,
            equipment_ticket,
            emblem_ticket
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        point_row = cur.fetchone()

        if point_row:
            contribution_points = point_row[0]
            role = point_row[1] or "member"
            equipment_ticket = point_row[2]
            emblem_ticket = point_row[3]

        # 입찰에 사용 중인 기여도
        cur.execute("""
        SELECT COALESCE(SUM(contribution_used), 0)
        FROM entries
        WHERE nickname=?
        """, (decoded_user,))

        used_points = cur.fetchone()[0]

        # 남은 사용 가능 기여도
        available_points = contribution_points - used_points

        # 오늘 출석 여부
        cur.execute("""
        SELECT last_attendance
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        if row and row[0] == today:
            attendance_done = True

    equipment = []
    accessory = []
    emblem = []
    etc_items = []

    current_item = None
    seq = 1

    for nickname, item_name, result, category in rows:

        if current_item != item_name:
            current_item = item_name
            seq = 1

        if nickname == "유찰":

            row_data = (
                "유찰",
                item_name,
                "-"
            )

        else:

            if category == "기타" and "개 지급" in result:

                qty = int(
                    result.replace("개 지급", "").strip()
                )

                numbers = []

                for _ in range(qty):
                    numbers.append(f"{seq}번")
                    seq += 1

                display_result = ", ".join(numbers)

            else:

                display_result = "당첨"

            row_data = (
                nickname,
                item_name,
                display_result
            )

        if category == "장비":
            equipment.append(row_data)

        elif category == "악세사리":
            accessory.append(row_data)

        elif category == "엠블럼":
            emblem.append(row_data)

        elif category == "기타":
            etc_items.append(row_data)

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "items": items,
            "equipment": equipment,
            "accessory": accessory,
            "emblem": emblem,
            "etc_items": etc_items,
            "user": unquote(user) if user else None,
            "contribution_points": contribution_points,
            "used_points": used_points,
            "available_points": available_points,
            "equipment_ticket": equipment_ticket,
            "emblem_ticket": emblem_ticket,
            "attendance": attendance,
            "attendance_done": attendance_done,
            "auction_status": auction_status,
            "auction_end_time": auction_end_time,
            "lucky_user": lucky_user,
            "role": role
        }
    )


@app.post("/apply")
async def apply(
    item_name: str = Form(...),
    quantity: int = Form(1),

    bid_type: str = Form("point"),   # point / ticket

    contribution_used: int = Form(0),

    user: str = Cookie(None)
):
    if not user:
        return {
            "success": False,
            "message": "로그인이 필요합니다."
        }

    nickname = unquote(user)


    conn = get_db()
    cur = conn.cursor()

    # ⭐ 경매 진행 여부 확인
    cur.execute("""
    SELECT status
    FROM auction_settings
    WHERE id=1
    """)

    auction = cur.fetchone()

    if not auction or auction[0] != "running":
        conn.close()
        return {
            "success": False,
            "message": "현재는 경매 대기중입니다."
        }


    cur.execute("""
    SELECT
        contribution_points,
        equipment_ticket,
        emblem_ticket
    FROM users
    WHERE nickname=?
    """, (nickname,))

    row = cur.fetchone()

    current_points = row[0] if row else 0
    equipment_ticket = row[1] if row else 0
    emblem_ticket = row[2] if row else 0

    # 이미 입찰에 사용한 포인트 합계
    cur.execute("""
    SELECT COALESCE(SUM(contribution_used), 0)
    FROM entries
    WHERE nickname=?
    """, (nickname,))

    used_points = cur.fetchone()[0]

    available_points = current_points - used_points

        # ⭐ 카테고리별 자동 기여도 계산
    category = get_category(item_name)
    ticket_type = ""

    if bid_type == "ticket":

        if category == "장비" or category == "악세사리":

            if equipment_ticket <= 0:

                conn.close()

                return {
                    "success": False,
                    "message": "장비/악세 강화입찰권이 없습니다."
                }

            ticket_type = "equipment"
            contribution_used = 0

        elif category == "엠블럼":

            if emblem_ticket <= 0:

                conn.close()

                return {
                    "success": False,
                    "message": "엠블럼 강화입찰권이 없습니다."
                }

            ticket_type = "emblem"
            contribution_used = 0

        else:

            conn.close()

            return {
                "success": False,
                "message": "기타 품목은 강화입찰권을 사용할 수 없습니다."
            }

        # =========================
        # 강화입찰권 중복 사용 방지
        # =========================
        cur.execute("""
        SELECT COUNT(*)
        FROM entries
        WHERE nickname=?
        AND ticket_type=?
        """,
        (
            nickname,
            ticket_type
        ))

        already_ticket = cur.fetchone()[0]

        if already_ticket > 0:

            conn.close()

            if ticket_type == "equipment":

                return {
                    "success": False,
                    "message": "장비/악세 강화입찰권은 한 번에 1개만 사용할 수 있습니다."
                }

            return {
                "success": False,
                "message": "엠블럼 강화입찰권은 한 번에 1개만 사용할 수 있습니다."
            }

    else:

        ticket_type = ""

    if category == "기타":
        contribution_used = 0


    if quantity < 1:
        conn.close()
        return {
            "success": False,
            "message": "수량은 1개 이상이어야 합니다."
        }

    if category != "기타" and contribution_used < 0:
        conn.close()
        return {
            "success": False,
            "message": "기여도는 0점 이상 입력해야 합니다."
        }

    if category == "장비" and contribution_used > 10:
        conn.close()
        return {
            "success": False,
            "message": "장비는 최대 10점까지 입찰 가능합니다."
        }

    if category == "악세사리" and contribution_used > 10:
        conn.close()
        return {
            "success": False,
            "message": "악세사리는 최대 10점까지 입찰 가능합니다."
        }

    if category == "엠블럼" and contribution_used > 5:
        conn.close()
        return {
            "success": False,
            "message": "엠블럼은 최대 5점까지 입찰 가능합니다."
        }

    if category != "기타" and contribution_used > available_points:
        conn.close()
        return {
            "success": False,
            "message": f"남은 기여도는 {available_points}점입니다."
        }
        
        

    # 동일 품목 중복 신청 방지
    cur.execute(
        """
        SELECT COUNT(*)
        FROM entries
        WHERE nickname=?
        AND item_name=?
        """,
        (nickname, item_name)
    )

    already = cur.fetchone()[0]

    if already > 0:

        conn.close()

        return {
            "success": False,
            "message": "이미 신청한 품목입니다."
        }

    cur.execute(
        "SELECT item_name FROM entries WHERE nickname=?",
        (nickname,)
    )

    rows = cur.fetchall()

    equip = 0
    accessory = 0
    emblem = 0
    etc = 0

    for row in rows:

        cat = get_category(row[0])

        if cat == "장비":
            equip += 1

        elif cat == "악세사리":
            accessory += 1

        elif cat == "엠블럼":
            emblem += 1

        elif cat == "기타":
            etc += 1

    if category == "장비" and equip >= 1:
        conn.close()
        return {
            "success": False,
            "message": "장비는 1개만 신청 가능합니다."
        }

    if category == "악세사리" and accessory >= 1:
        conn.close()
        return {
            "success": False,
            "message": "악세사리는 1개만 신청 가능합니다."
        }

    if category == "엠블럼" and emblem >= 2:
        conn.close()
        return {
            "success": False,
            "message": "엠블럼은 2개만 신청 가능합니다."
        }

    if category == "기타" and etc >= 3:
        conn.close()
        return {
            "success": False,
            "message": "기타 품목은 3개만 신청 가능합니다."
        }

    cur.execute(
        """
        INSERT INTO entries
        (
            nickname,
            item_name,
            entry_number,
            quantity,
            contribution_used,
            ticket_type
        )
        VALUES (?,?,?,?,?,?)
        """,
        (
            nickname,
            item_name,
            "",
            quantity,
            contribution_used,
            ticket_type
        )
    )

    entry_id = cur.lastrowid

    entry_number = f"A-{entry_id:04d}"

    cur.execute(
        """
        UPDATE entries
        SET entry_number=?
        WHERE id=?
        """,
        (entry_number, entry_id)
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "entry_number": entry_number,
        "used_point": contribution_used
    }


@app.post("/add_item")
async def add_item(
    item_name: str = Form(...),
    category: str = Form(...),
    item_quantity: int = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO items
        (item_name, category, item_quantity)
        VALUES (?, ?, ?)
        """,
        (item_name, category, item_quantity)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=303
    )


@app.get("/delete_item/{item_id}")
async def delete_item(
    item_id: int,
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        if not row or row[0] != "auction":
            conn.close()
            return RedirectResponse("/", status_code=303)

        conn.close()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM items WHERE id=?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    if admin == "yes":
        return RedirectResponse(
            "/admin",
            status_code=303
        )

    return RedirectResponse(
        "/auction",
        status_code=303
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin(
    request: Request,
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    conn = get_db()
    cur = conn.cursor()

    # =========================
    # 신청자 목록
    # =========================
    cur.execute("""
    SELECT
        id,
        nickname,
        item_name,
        entry_number,
        contribution_used
    FROM entries
    ORDER BY item_name ASC,
             contribution_used DESC,
             nickname ASC
    """)
    entries = cur.fetchall()

    # =========================
    # 등록 품목
    # =========================
    cur.execute("""
    SELECT
        id,
        item_name,
        category,
        item_quantity
    FROM items
    """)
    items = cur.fetchall()

    # =========================
    # 아이템 마스터
    # =========================
    cur.execute("""
    SELECT
        id,
        category,
        item_name
    FROM item_master
    ORDER BY
        category ASC,
        item_name ASC
    """)
    master_items = cur.fetchall()

    # =========================
    # 회원 목록
    # =========================
    cur.execute("""
    SELECT
        id,
        nickname,
        contribution_points
    FROM users
    ORDER BY nickname ASC
    """)
    users = cur.fetchall()

    auction_status = "종료"
    auction_end_time = ""

    try:

        cur.execute("""
        SELECT
            status,
            end_time
        FROM auction_settings
        WHERE id=1
        """)

        row = cur.fetchone()

        if row:

            status = row[0]
            auction_end_time = row[1] or ""

            if (
                status == "running"
                and auction_end_time
            ):

                end_dt = datetime.strptime(
                    auction_end_time,
                    "%Y-%m-%d %H:%M:%S"
                )

                now_dt = datetime.now(
                    ZoneInfo("Asia/Seoul")
                ).replace(tzinfo=None)

                if now_dt >= end_dt:

                    print("AUTO REVEAL START")

                    run_draw()

                    cur.execute("""
                    UPDATE auction_settings
                    SET status='revealed'
                    WHERE id=1
                    """)

                    conn.commit()

                    auction_status = "개찰완료"

                else:

                    auction_status = "진행중"

            elif status == "revealed":

                auction_status = "개찰완료"

            else:

                auction_status = "종료"

            print(
                "auction_end_time =",
                auction_end_time
            )

    except Exception as e:

        print("ADMIN ERROR =", e)

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "entries": entries,
            "items": items,
            "master_items": master_items,
            "users": users,
            "auction_status": auction_status,
            "auction_end_time": auction_end_time
        }
    )


@app.get("/auction", response_class=HTMLResponse)
async def auction(
    request: Request,
    user: str = Cookie(None)
):

    if not user:
        return RedirectResponse(
            "/user_login",
            status_code=303
        )

    conn = get_db()
    cur = conn.cursor()

    decoded_user = unquote(user)

    # 권한 확인
    cur.execute("""
    SELECT role
    FROM users
    WHERE nickname=?
    """, (decoded_user,))

    row = cur.fetchone()

    if not row or row[0] != "auction":
        conn.close()
        return RedirectResponse(
            "/",
            status_code=303
        )

    # =========================
    # 등록 품목
    # =========================
    cur.execute("""
    SELECT
        id,
        item_name,
        category,
        item_quantity
    FROM items
    """)
    items = cur.fetchall()

    # =========================
    # 아이템 마스터
    # =========================
    cur.execute("""
    SELECT
        id,
        category,
        item_name
    FROM item_master
    ORDER BY
        category ASC,
        item_name ASC
    """)
    master_items = cur.fetchall()

    auction_status = "종료"
    auction_end_time = ""

    try:

        cur.execute("""
        SELECT
            status,
            end_time
        FROM auction_settings
        WHERE id=1
        """)

        auction = cur.fetchone()

        if auction:

            status = auction[0]
            auction_end_time = auction[1] or ""

            if status == "running":
                auction_status = "진행중"

            elif status == "revealed":
                auction_status = "개찰완료"

    except:
        pass

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="auction.html",
        context={
            "items": items,
            "master_items": master_items,
            "auction_status": auction_status,
            "auction_end_time": auction_end_time
        }
    )


@app.get("/draw")
async def draw(
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    run_draw()

    return RedirectResponse(
        "/results",
        status_code=303
    )

@app.get("/results", response_class=HTMLResponse)
async def results(request: Request):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        w.nickname,
        w.item_name,
        w.entry_number,
        i.category
    FROM winners w
    LEFT JOIN items i
        ON w.item_name = i.item_name
    ORDER BY w.item_name ASC, w.nickname ASC
    """)

    rows = cur.fetchall()

    equipment = []
    accessory = []
    emblem = []
    etc_items = []

    current_item = None
    seq = 1

    for nickname, item_name, result, category in rows:

        if current_item != item_name:
            current_item = item_name
            seq = 1

        if nickname == "유찰":

            row_data = (
                "유찰",
                item_name,
                "-"
            )

        else:

            if category == "기타" and "개 지급" in result:

                qty = int(
                    result.replace("개 지급", "").strip()
                )

                numbers = []

                for _ in range(qty):
                    numbers.append(f"{seq}번")
                    seq += 1

                display_result = ", ".join(numbers)

            else:

                display_result = "당첨"

            row_data = (
                nickname,
                item_name,
                display_result
            )

        if category == "장비":
            equipment.append(row_data)

        elif category == "악세사리":
            accessory.append(row_data)

        elif category == "엠블럼":
            emblem.append(row_data)

        elif category == "기타":
            etc_items.append(row_data)

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "equipment": equipment,
            "accessory": accessory,
            "emblem": emblem,
            "etc_items": etc_items
        }
    )

@app.get("/edit_item/{item_id}", response_class=HTMLResponse)
async def edit_item_page(
    request: Request,
    item_id: int,
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        if not row or row[0] != "auction":
            conn.close()
            return RedirectResponse("/", status_code=303)

        conn.close()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            item_name,
            category,
            item_quantity
        FROM items
        WHERE id=?
        """,
        (item_id,)
    )

    item = cur.fetchone()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="edit_item.html",
        context={
            "item": item
        }
    )

@app.post("/update_item")
async def update_item(
    item_id: int = Form(...),
    item_name: str = Form(...),
    category: str = Form(...),
    item_quantity: int = Form(...),
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        conn.close()

        if not row or row[0] != "auction":
            return RedirectResponse("/", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE items
        SET
            item_name=?,
            category=?,
            item_quantity=?
        WHERE id=?
        """,
        (
            item_name,
            category,
            item_quantity,
            item_id
        )
    )

    conn.commit()
    conn.close()

    if admin == "yes":
        return RedirectResponse(
            "/admin",
            status_code=303
        )

    return RedirectResponse(
        "/auction",
        status_code=303
    )

@app.get("/reset_all")
async def reset_all(
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        conn.close()

        if not row or row[0] != "auction":
            return RedirectResponse("/", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    # 신청자 삭제
    cur.execute("DELETE FROM entries")

    # 당첨 결과 삭제
    cur.execute("DELETE FROM winners")

    # 품목 삭제
    cur.execute("DELETE FROM items")

    conn.commit()
    conn.close()

    if admin == "yes":
        return RedirectResponse("/admin", status_code=303)

    return RedirectResponse("/auction", status_code=303)

@app.post("/my_entries")
async def my_entries(
    user: str = Cookie(None)
):

    if not user:
        return {"entries": []}

    nickname = unquote(user)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            item_name,
            entry_number,
            contribution_used
        FROM entries
        WHERE nickname=?
        ORDER BY id DESC
        """,
        (nickname,)
    )

    rows = cur.fetchall()

    conn.close()

    return {
        "entries": [
            {
                "id": row[0],
                "item_name": row[1],
                "entry_number": row[2],
                "contribution_used": row[3]
            }
            for row in rows
        ]
    }

@app.post("/give_contribution")
async def give_contribution(
    user_ids: Optional[List[int]] = Form(None),
    points: int = Form(0),
    action: str = Form("give"),
    admin: str = Cookie(None)
):
    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    # 선택된 회원이 없으면 그냥 돌아가기
    if not user_ids:
        return RedirectResponse(
            "/member_admin",
            status_code=303
        )

    conn = get_db()
    cur = conn.cursor()

    # ==========================
    # 기여도 지급
    # ==========================
    if action == "give":

        for user_id in user_ids:

            # 닉네임 조회
            cur.execute(
                """
                SELECT nickname
                FROM users
                WHERE id=?
                """,
                (user_id,)
            )

            row = cur.fetchone()

            if not row:
                continue

            nickname = row[0]

            # 기여도 지급
            cur.execute(
                """
                UPDATE users
                SET contribution_points =
                    MAX(0, contribution_points + ?)
                WHERE id = ?
                """,
                (points, user_id)
            )

            # 로그 저장
            add_contribution_log(
                cur,
                nickname,
                points,
                "관리자 지급"
            )

    # ==========================
    # 경매관리자 지정
    # ==========================
    elif action == "auction":

        cur.executemany(
            """
            UPDATE users
            SET role='auction'
            WHERE id=?
            """,
            [(uid,) for uid in user_ids]
        )

    # ==========================
    # 일반회원 변경
    # ==========================
    elif action == "member":

        cur.executemany(
            """
            UPDATE users
            SET role='member'
            WHERE id=?
            """,
            [(uid,) for uid in user_ids]
        )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/member_admin",
        status_code=303
    )

@app.post("/cancel_entry")
async def cancel_entry(
    entry_id: int = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM entries WHERE id=?",
        (entry_id,)
    )

    conn.commit()
    conn.close()

    return {"success": True}

@app.post("/delete_entry/{entry_id}")
async def delete_entry(
    entry_id: int,
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM entries WHERE id=?",
        (entry_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=303
    )
@app.post("/start_auction")
async def start_auction(
    reveal_minutes: int = Form(...),
    auto_reveal: int = Form(...),
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        conn.close()

        if not row or row[0] != "auction":
            return RedirectResponse("/", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    start_time = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    if auto_reveal == 1:

        end_time = start_time + timedelta(
            minutes=reveal_minutes
        )

        end_time_str = end_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    else:

        end_time_str = None

    cur.execute(
        """
        UPDATE auction_settings
        SET
            status=?,
            auto_reveal=?,
            reveal_minutes=?,
            start_time=?,
            end_time=?
        WHERE id=1
        """,
        (
            "running",
            auto_reveal,
            reveal_minutes,
            start_time.isoformat(),
            end_time_str
        )
    )

    conn.commit()
    conn.close()

    # 어디서 실행했는지에 따라 돌아갈 페이지
    if admin == "yes":
        return RedirectResponse("/admin", status_code=303)

    return RedirectResponse("/auction", status_code=303)


@app.post("/reveal_auction")
async def reveal_auction():

    run_draw()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE auction_settings
        SET status='revealed'
        WHERE id=1
        """
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/results",
        status_code=303
    )


@app.post("/stop_auction")
async def stop_auction():

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE auction_settings
        SET status='stopped',
            end_time=null
        WHERE id=1
        """
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=303
    )



@app.get("/member_admin", response_class=HTMLResponse)
async def member_admin(
    request: Request,
    admin: str = Cookie(None)
):
    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        nickname,
        contribution_points,
        created_at,
        role
    FROM users
    ORDER BY nickname ASC
    """)

    users = cur.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="member_admin.html",
        context={
            "users": users
        }
    )

@app.post("/delete_user")
async def delete_user(
    user_id: int = Form(...),
    admin: str = Cookie(None)
):
    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    # 닉네임 조회
    cur.execute(
        "SELECT nickname FROM users WHERE id=?",
        (user_id,)
    )

    row = cur.fetchone()

    if row:
        nickname = row[0]

        # 신청 내역 삭제
        cur.execute(
            "DELETE FROM entries WHERE nickname=?",
            (nickname,)
        )

        # 당첨 내역 삭제
        cur.execute(
            "DELETE FROM winners WHERE nickname=?",
            (nickname,)
        )

        # 회원삭제
        cur.execute(
            "DELETE FROM users WHERE id=?",
            (user_id,)
        )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/member_admin",
        status_code=303
    )

@app.post("/reset_contribution")
async def reset_contribution(
    admin: str = Cookie(None)
):
    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET contribution_points = 0
    """)

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/member_admin",
        status_code=303
    )

@app.get("/download_db")
async def download_db(admin: str = Cookie(None)):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    return FileResponse(
        path="itemdraw.db",
        filename="itemdraw.db",
        media_type="application/octet-stream"
    )

@app.post("/weekly_contribution")
async def weekly_contribution(
    admin: str = Cookie(None)
):
    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    conn = get_db()
    cur = conn.cursor()

    # 전체 회원 조회
    cur.execute("""
        SELECT nickname
        FROM users
    """)

    users = cur.fetchall()

    # 회원별 지급 + 로그 저장
    for row in users:

        nickname = row["nickname"]

        cur.execute("""
            UPDATE users
            SET contribution_points = contribution_points + 10
            WHERE nickname=?
        """, (nickname,))

        add_contribution_log(
            cur,
            nickname,
            10,
            "주간 기여도 지급"
        )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/member_admin",
        status_code=303
    )

@app.post("/restore_db")
async def restore_db(
    file: UploadFile = File(...),
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

    # 기존 DB 백업
    shutil.copy(
        "itemdraw.db",
        "itemdraw_before_restore.db"
    )

    # DB 복원
    with open("itemdraw.db", "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ⭐ DB 연결 종료 후 최신 구조로 자동 업데이트
    init_db()

    return RedirectResponse(
        "/admin",
        status_code=303
    )

@app.get("/countdown")
async def countdown():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT status, end_time
        FROM auction_settings
        WHERE id=1
    """)

    row = cur.fetchone()

    conn.close()

    if not row or row[0] != "running":
        return {
            "running": False
        }

    end = datetime.strptime(
        row[1],
        "%Y-%m-%d %H:%M:%S"
    ).replace(
        tzinfo=ZoneInfo("Asia/Seoul")
    )

    now = datetime.now(
        ZoneInfo("Asia/Seoul")
    )

    diff = int((end - now).total_seconds())

    if diff < 0:
        diff = 0

    return {
        "running": True,
        "minutes": diff // 60,
        "seconds": diff % 60
    }

@app.get("/item_counts")
async def item_counts():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        i.item_name,
        i.category,
        i.item_quantity,
        COUNT(e.id) AS entry_count
    FROM items i
    LEFT JOIN entries e
        ON i.item_name = e.item_name
    GROUP BY
        i.item_name,
        i.category,
        i.item_quantity
    ORDER BY i.category
    """)

    rows = cur.fetchall()

    conn.close()

    return [
        {
            "item_name": row[0],
            "category": row[1],
            "item_quantity": row[2],
            "entry_count": row[3]
        }
        for row in rows
    ]

@app.get("/master", response_class=HTMLResponse)
async def master(
    request: Request,
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        category,
        item_name
    FROM item_master
    ORDER BY category,item_name
    """)

    master_items = cur.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="master.html",
        context={
            "master_items": master_items
        }
    )

@app.post("/add_master_item")
async def add_master_item(

    category: str = Form(...),
    item_name: str = Form(...),

    admin: str = Cookie(None)

):

    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO item_master
    (
        category,
        item_name
    )
    VALUES
    (?,?)
    """,
    (
        category,
        item_name
    ))

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/master",
        status_code=303
    )

@app.get("/delete_master_item/{item_id}")
async def delete_master_item(

    item_id: int,

    admin: str = Cookie(None)

):

    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM item_master WHERE id=?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/master",
        status_code=303
    )

@app.post("/add_items")
async def add_items(
    items: str = Form(...),
    admin: str = Cookie(None),
    user: str = Cookie(None)
):

    # 관리자 또는 경매관리자만 가능
    if admin != "yes":

        if not user:
            return RedirectResponse("/", status_code=303)

        conn = get_db()
        cur = conn.cursor()

        decoded_user = unquote(user)

        cur.execute("""
        SELECT role
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        row = cur.fetchone()

        conn.close()

        if not row or row[0] != "auction":
            return RedirectResponse("/", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    item_list = json.loads(items)

    for row in item_list:

        category = row["category"]
        item_name = row["item_name"]
        qty = int(row["qty"])

        # 장비 / 악세
        if category in ["장비", "악세사리"]:

            for i in range(1, qty + 1):

                cur.execute(
                    """
                    INSERT INTO items
                    (
                        item_name,
                        category,
                        item_quantity
                    )
                    VALUES
                    (?,?,1)
                    """,
                    (
                        f"{item_name} {i}",
                        category
                    )
                )

        # 엠블럼 / 기타
        else:

            cur.execute(
                """
                INSERT INTO items
                (
                    item_name,
                    category,
                    item_quantity
                )
                VALUES
                (?,?,?)
                """,
                (
                    item_name,
                    category,
                    qty
                )
            )

    conn.commit()
    conn.close()

    if admin == "yes":
        return RedirectResponse("/admin", status_code=303)

    return RedirectResponse("/auction", status_code=303)

@app.post("/exchange_ticket")
async def exchange_ticket(
    ticket_type: str = Form(...),
    user: str = Cookie(None)
):

    if not user:
        return JSONResponse({
            "success": False,
            "message": "로그인이 필요합니다."
        })

    nickname = unquote(user)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT
        contribution_points,
        equipment_ticket,
        emblem_ticket
    FROM users
    WHERE nickname=?
    """, (nickname,))

    row = cur.fetchone()

    if not row:
        conn.close()
        return JSONResponse({
            "success": False,
            "message": "회원 정보를 찾을 수 없습니다."
        })

    points = row[0]

    if ticket_type == "equipment":

        if points < 20:
            conn.close()
            return JSONResponse({
                "success": False,
                "message": "기여도 20점이 필요합니다."
            })

        cur.execute("""
        UPDATE users
        SET
            contribution_points = contribution_points - 20,
            equipment_ticket = equipment_ticket + 1
        WHERE nickname=?
        """, (nickname,))

        # 로그 저장
        add_contribution_log(
            cur,
            nickname,
            -20,
            "장비/악세 강화입찰권 교환"
        )

    elif ticket_type == "emblem":

        if points < 10:
            conn.close()
            return JSONResponse({
                "success": False,
                "message": "기여도 10점이 필요합니다."
            })

        cur.execute("""
        UPDATE users
        SET
            contribution_points = contribution_points - 10,
            emblem_ticket = emblem_ticket + 1
        WHERE nickname=?
        """, (nickname,))

        # 로그 저장
        add_contribution_log(
            cur,
            nickname,
            -10,
            "엠블럼 강화입찰권 교환"
        )

    else:

        conn.close()

        return JSONResponse({
            "success": False,
            "message": "잘못된 요청입니다."
        })

    conn.commit()
    conn.close()

    return JSONResponse({
        "success": True,
        "message": "강화입찰권으로 교환되었습니다."
    })

@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request, user: str = Cookie(None)):

    if not user:
        return RedirectResponse("/user_login", status_code=303)

    nickname = unquote(user)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT contribution_points
        FROM users
        WHERE nickname=?
    """, (nickname,))

    member = cursor.fetchone()

    if not member:
        conn.close()
        return RedirectResponse("/", status_code=303)

    cursor.execute("""
        SELECT COALESCE(SUM(contribution_used),0)
        FROM entries
        WHERE nickname=?
    """, (nickname,))

    used = cursor.fetchone()[0]

    cursor.execute("""
        SELECT amount, reason, created_at
        FROM contribution_logs
        WHERE nickname=?
        ORDER BY id DESC
        LIMIT 30
    """, (nickname,))

    logs = cursor.fetchall()

    conn.close()

    total = member["contribution_points"]
    available = total - used

    return templates.TemplateResponse(
        request=request,
        name="mypage.html",
        context={
            "user": nickname,
            "total": total,
            "used": used,
            "available": available,
            "logs": logs
        }
    )