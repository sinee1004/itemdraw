from unicodedata import category
from urllib import request
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import random
import hashlib
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import Form
from typing import List, Optional


app = FastAPI()
from fastapi.staticfiles import StaticFiles

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
templates = Jinja2Templates(directory="templates")

ADMIN_PASSWORD = "1234"



def get_db():
    return sqlite3.connect("itemdraw.db")


def init_db():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        contribution_points INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT,
        category TEXT,
        winner_count INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        item_name TEXT,
        entry_number TEXT,
        quantity INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS winners(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        item_name TEXT,
        entry_number TEXT
    )
    """)
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
    # 기존 DB 사용 중일 경우 quantity 컬럼 추가
    try:
        cur.execute("""
        ALTER TABLE entries
        ADD COLUMN quantity INTEGER DEFAULT 1
        """)
    except:
        pass

    try:
        cur.execute("""
        ALTER TABLE entries
        ADD COLUMN contribution_used INTEGER DEFAULT 0
        """)
    except:
        pass

    try:
        cur.execute("""
        ALTER TABLE users
        ADD COLUMN reserved_points INTEGER DEFAULT 0
        """)
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
    SELECT item_name, category, winner_count
    FROM items
    """)

    items = cur.fetchall()

    for item_name, category, winner_count in items:

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
                winner_count
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
                    contribution_used
                FROM entries
                WHERE item_name=?
                ORDER BY contribution_used DESC
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

            # 기여도 높은 순으로 정렬
            applicants = sorted(
                applicants,
                key=lambda x: x[3],
                reverse=True
            )

            selected = []

            remaining = applicants

            # winner_count만큼 반복
            while len(selected) < winner_count and remaining:

                highest = remaining[0][3]

                # 현재 최고 기여도 그룹
                same_score = [
                    a for a in remaining
                    if a[3] == highest
                ]

                random.shuffle(same_score)

                need = winner_count - len(selected)

                selected.extend(same_score[:need])

                # 뽑힌 사람 제거
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

    cur.execute("DELETE FROM entries")

    conn.commit()
    conn.close()

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

@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user: str = Cookie(None)
):

    conn = get_db()
    cur = conn.cursor()

    # 품목 목록
    cur.execute("""
    SELECT
        i.item_name,
        i.category,
        COUNT(e.id)
    FROM items i
    LEFT JOIN entries e
        ON i.item_name = e.item_name
    GROUP BY i.item_name, i.category
    ORDER BY i.category
    """)

    items = cur.fetchall()

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

    # 현재 로그인한 사용자의 기여도 조회
    contribution_points = 0
    used_points = 0
    available_points = 0

    if user:
        decoded_user = unquote(user)

        # 총 기여도
        cur.execute("""
        SELECT contribution_points
        FROM users
        WHERE nickname=?
        """, (decoded_user,))

        point_row = cur.fetchone()

        if point_row:
            contribution_points = point_row[0]

        # 입찰에 사용 중인 기여도
        cur.execute("""
        SELECT COALESCE(SUM(contribution_used), 0)
        FROM entries
        WHERE nickname=?
        """, (decoded_user,))

        used_points = cur.fetchone()[0]

        # 남은 사용 가능 기여도
        available_points = contribution_points - used_points

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
            "available_points": available_points
        }
    )


@app.post("/apply")
async def apply(
    item_name: str = Form(...),
    quantity: int = Form(1),
    contribution_used: int = Form(0),   # ⭐ 다시 추가
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
    cur.execute("""
    SELECT contribution_points
    FROM users
    WHERE nickname=?
    """, (nickname,))

    row = cur.fetchone()
    current_points = row[0] if row else 0

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
            contribution_used
        )
        VALUES (?,?,?,?,?)
        """,
        (
            nickname,
            item_name,
            "",
            quantity,
            contribution_used
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
    winner_count: int = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO items
        (item_name,category,winner_count)
        VALUES (?,?,?)
        """,
        (item_name, category, winner_count)
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
        "DELETE FROM items WHERE id=?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
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

    cur.execute("""
    SELECT id,nickname,item_name,entry_number
    FROM entries
    ORDER BY nickname ASC, item_name ASC
    """)
    entries = cur.fetchall()

    cur.execute("""
    SELECT id,item_name,category,winner_count
    FROM items
    """)
    items = cur.fetchall()
    # 회원 목록 (기여도 관리용)
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
        SELECT status, end_time
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
             "users": users,          # ⭐ 이 줄 추가
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
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id,item_name,category,winner_count
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
        context={"item": item}
    )
@app.post("/update_item")
async def update_item(
    item_id: int = Form(...),
    item_name: str = Form(...),
    category: str = Form(...),
    winner_count: int = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE items
        SET item_name=?,
            category=?,
            winner_count=?
        WHERE id=?
        """,
        (
            item_name,
            category,
            winner_count,
            item_id
        )
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=303
    )
@app.get("/reset_all")
async def reset_all(
    admin: str = Cookie(None)
):

    if admin != "yes":
        return RedirectResponse(
            "/login",
            status_code=303
        )

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

    return RedirectResponse(
        "/admin",
        status_code=303
    )
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
    points: int = Form(...),
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

    for user_id in user_ids:
        cur.execute(
            """
            UPDATE users
            SET contribution_points = contribution_points + ?
            WHERE id = ?
            """,
            (points, user_id)
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
    auto_reveal: int = Form(...)
):
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

    return RedirectResponse(
        "/admin",
        status_code=303
    )


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
        created_at
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

    cur.execute("""
        UPDATE users
        SET contribution_points = contribution_points + 10
    """)

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/member_admin",
        status_code=303
    )