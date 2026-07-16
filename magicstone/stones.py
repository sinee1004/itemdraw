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

ALLOWED_POTENTIALS = {

    "순격숙달",
    "강습숙달",
    "추상숙달",
    "근성숙달",
    "방감숙달",
    "요새숙달",

    "순격증폭",
    "강습증폭",
    "추상증폭",
    "근성증폭",
    "방감증폭",
    "요새증폭",

    "매직스톤단련",
    "붉은빛집중",
    "만물조형",
    "인장동조",
    "잠재력공명",
    "원근잠재력",

}

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
        ORDER BY
            CASE shape
                WHEN '원' THEN 1
                WHEN '세모' THEN 2
                WHEN '다이아' THEN 3
                WHEN '육각' THEN 4
                WHEN '별' THEN 5
                WHEN '달' THEN 6
                ELSE 99
            END,
            name,
            CASE grade
                WHEN '신화' THEN 1
                WHEN '전설' THEN 2
                WHEN '에픽' THEN 3
                ELSE 99
            END,
            potential,
            potential_value DESC
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

    # 계산기에 사용하는 잠재력인지 확인
    if potential not in ALLOWED_POTENTIALS:

        conn.close()

        return RedirectResponse(
            "/magicstone?message=invalid_potential",
            status_code=303
        )

    # 같은 모양 + 같은 등급 + 같은 잠재력 조회
    rows = conn.execute("""

        SELECT id, potential_value

        FROM magic_user_stones

        WHERE nickname=?
        AND name=?
        AND shape=?
        AND grade=?
        AND potential=?

        ORDER BY potential_value DESC

    """, (

        nickname,
        name,
        shape,
        grade,
        potential

    )).fetchall()

    # 이미 2개 이상 보유한 경우
    if len(rows) >= 1:

        # 기존보다 낮거나 같으면 등록 불가
        if potential_value <= rows[0]["potential_value"]:

            conn.close()

            return RedirectResponse(
                "/magicstone?message=lower_value",
                status_code=303
            )

        # 2번째를 제외한 나머지는 모두 삭제
        

        conn.execute(
            "DELETE FROM magic_user_stones WHERE id=?",
            (rows[0]["id"],)
        )

    # 현재 보유 개수 확인
    count = conn.execute(
        "SELECT COUNT(*) FROM magic_user_stones WHERE nickname=?",
        (nickname,)
    ).fetchone()[0]

    # 교체가 아닌 일반 등록만 100개 제한
    if len(rows) < 2 and count >= 100:

        conn.close()

        return RedirectResponse(
            "/magicstone?message=max100",
            status_code=303
        )

    # 새 매직스톤 저장
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

@router.get("/stone/cleanup")
async def cleanup_stones(user: str = Cookie(None)):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    conn = get_db()

    rows = conn.execute("""

        SELECT id,
               name,
               shape,
               grade,
               potential,
               potential_value

        FROM magic_user_stones

        WHERE nickname=?

        ORDER BY
            name,            
            shape,
            grade,
            potential,
            potential_value DESC

    """, (nickname,)).fetchall()

    groups = {}

    delete_ids = []

    for row in rows:

        key = (
            row["name"],
            row["shape"],
            row["grade"],
            row["potential"]
        )

        groups.setdefault(key, []).append(row)

    for stones in groups.values():

        if len(stones) > 1:

            for stone in stones[1:]:

                delete_ids.append(stone["id"])

    for stone_id in delete_ids:

        conn.execute(
            "DELETE FROM magic_user_stones WHERE id=?",
            (stone_id,)
        )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/magicstone?message=cleanup",
        status_code=303
    )


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