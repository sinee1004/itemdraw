from urllib.parse import unquote
from fastapi import Cookie
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from magicstone.magicstone_data import (
    STONE_DATA,
    GRADE_VALUE,
    SHAPE_NAMES
)

from magicstone.potential_utils import get_all

from database import get_db

router = APIRouter(prefix="/magicstone")


templates = Jinja2Templates(directory="templates")


@router.get("/")
async def index(
    request: Request,
    user: str = Cookie(None)
):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    conn = get_db()

    # 처음 사용하는 회원이면 설정 생성
    conn.execute("""
        INSERT OR IGNORE INTO magic_user_settings(nickname)
        VALUES(?)
    """, (nickname,))
    conn.commit()

    magic_stones = conn.execute("""
        SELECT *
        FROM magic_user_stones
        WHERE nickname=?
        ORDER BY id DESC
    """, (nickname,)).fetchall()

    setting = conn.execute("""
        SELECT *
        FROM magic_user_settings
        WHERE nickname=?
    """, (nickname,)).fetchone()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="magicstone.html",
        context={
            "stones": magic_stones,
            "setting": setting
        }
    )


@router.post("/stone/add")
async def add_stone(

    user: str = Cookie(None),

    name: str = Form(...),
    shape: str = Form(...),
    grade: str = Form(...),

    potential: str = Form(...),
    potential_value: float = Form(...)

):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    stone = STONE_DATA[name]

    value = GRADE_VALUE[stone["shape"]][grade]

    stat1 = stone["stat1"]
    value1 = value

    stat2 = stone["stat2"]
    value2 = value if stat2 else 0

    conn = get_db()

    # 최대 40개 제한
    count = conn.execute(
        "SELECT COUNT(*) FROM magic_user_stones WHERE nickname = ?",
        (nickname,)
    ).fetchone()[0]

    if count >= 25:
        conn.close()
        return RedirectResponse(
            "/magicstone?message=max25",
            status_code=303
        )

    conn.execute("""

        INSERT INTO magic_user_stones(

            nickname,

            name,
            shape,
            grade,

            stat1,
            value1,

            stat2,
            value2,

            potential,
            potential_value,

            owned

        )

        VALUES(

            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?

        )

    """, (

        nickname,

        name,
        shape,
        grade,

        stat1,
        value1,

        stat2,
        value2,

        potential,
        potential_value,

        1

    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/magicstone", status_code=303)

@router.get("/stone/delete/{stone_id}")
async def delete_stone(stone_id: int):

    conn = get_db()

    conn.execute(
        "DELETE FROM magic_user_stones WHERE id=?",
        (stone_id,)
    )

    conn.commit()
    conn.close()

    return RedirectResponse("/magicstone", status_code=303)




@router.get("/api/stone")

async def stone_info(

    name: str,
    grade: str

):

    stone = STONE_DATA[name]

    value = GRADE_VALUE[stone["shape"]][grade]

    return JSONResponse({

        "shape": stone["shape"],

        "stat1": stone["stat1"],
        "value1": value,

        "stat2": stone["stat2"],
        "value2": value if stone["stat2"] else 0

    })


@router.get("/api/shape")
async def shape_info(shape: str):

    return JSONResponse(
        SHAPE_NAMES[shape]
    )


@router.get("/api/potential/list")
async def potential_list():

    return JSONResponse(
        get_all()
    )

@router.post("/setting/save")
async def save_setting(

    user: str = Cookie(None),

    순격: float = Form(0),
    강습: float = Form(0),
    추상: float = Form(0),

    근성: float = Form(0),
    방감: float = Form(0),
    요새: float = Form(0)

):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    conn = get_db()

    conn.execute("""

        UPDATE magic_user_settings

        SET

            순격=?,
            강습=?,
            추상=?,

            근성=?,
            방감=?,
            요새=?

        WHERE nickname=?

    """, (

        순격,
        강습,
        추상,

        근성,
        방감,
        요새,

        nickname

    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/magicstone", status_code=303)