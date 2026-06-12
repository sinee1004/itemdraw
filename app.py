from unicodedata import category

from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import random

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

    # 기존 DB 사용 중일 경우 quantity 컬럼 추가
    try:
        cur.execute("""
        ALTER TABLE entries
        ADD COLUMN quantity INTEGER DEFAULT 1
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

        # 기타 품목
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
                SELECT nickname,item_name,entry_number
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

            selected = random.sample(
                applicants,
                min(winner_count, len(applicants))
            )
           
            for winner in selected:

                cur.execute(
                    """
                    INSERT INTO winners
                    (nickname,item_name,entry_number)
                    VALUES (?,?,?)
                    """,
                    winner
                )

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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

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
            "etc_items": etc_items
        }
    )
@app.post("/apply")
async def apply(
    nickname: str = Form(...),
    item_name: str = Form(...),
    quantity: int = Form(1)
):

    conn = get_db()
    cur = conn.cursor()

    category = get_category(item_name)

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
        (nickname,item_name,entry_number,quantity)
        VALUES (?,?,?,?)
        """,
        (
            nickname,
            item_name,
            "",
            quantity
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
        "entry_number": entry_number
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
        return RedirectResponse("/login", status_code=303)

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

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "entries": entries,
            "items": items
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
    nickname: str = Form(...)
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, item_name, entry_number
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
                "entry_number": row[2]
            }
            for row in rows
        ]
    }
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