from urllib.parse import unquote
from fastapi import Cookie
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi import Form

from database import get_db

from magicstone.engine import MagicStone
from magicstone.optimizer import Optimizer

router = APIRouter(prefix="/magicstone")

templates = Jinja2Templates(directory="templates")

# 현재 계산 중인 사용자
RUNNING_USERS = set()


@router.post("/calculate")
async def calculate(

    request: Request,

    mode: str = Form(...),

    target2: str = Form(...),

    target1: str = Form(""),
    target1_value: float = Form(0),

    user: str = Cookie(None)

):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    if nickname in RUNNING_USERS:
        return HTMLResponse("""
        <script>
            alert("이미 최적 조합 계산이 진행 중입니다.");
            location.href="/magicstone";
        </script>
        """)

    RUNNING_USERS.add(nickname)

    try:

        # 단일 목표 계산
        if mode == "single":

            target1 = target2
            target1_value = 0

        conn = get_db()

        rows = conn.execute("""

            SELECT *
            FROM magic_user_stones
            WHERE nickname=?

        """, (nickname,)).fetchall()

        setting = conn.execute("""

            SELECT *
            FROM magic_user_settings
            WHERE nickname=?

        """, (nickname,)).fetchone()

        conn.close()

        stones = []

        for row in rows:

            owned = row["owned"] if row["owned"] else 1

            for _ in range(owned):

                stones.append(

                    MagicStone(

                        name=row["name"],

                        shape=row["shape"],
                        grade=row["grade"],

                        stat1=row["stat1"],
                        value1=row["value1"],

                        stat2=row["stat2"],
                        value2=row["value2"],

                        potential=row["potential"],
                        potential_value=row["potential_value"]

                    )

                )

        optimizer = Optimizer(stones)

        best_value, best_team = optimizer.find_best(
            target1,
            target1_value,
            target2,
            setting
        )

        return templates.TemplateResponse(

            request=request,

            name="magicstone_result.html",

            context={

                "target": target2,
                "condition_target": target1,
                "condition_value": target1_value,
                "value": round(best_value, 2),
                "team": best_team

            }

        )

    finally:

        RUNNING_USERS.discard(nickname)


@router.get("/calculate")
async def calculate_all():

    return RedirectResponse("/magicstone", status_code=302)