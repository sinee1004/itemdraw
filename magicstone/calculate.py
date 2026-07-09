from urllib.parse import unquote
from fastapi import Cookie
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from database import get_db

from magicstone.engine import Engine, MagicStone
from magicstone.optimizer import Optimizer

router = APIRouter(prefix="/magicstone")

templates = Jinja2Templates(directory="templates")

# 현재 계산 중인 사용자
RUNNING_USERS = set()


@router.get("/calculate/{target}")
async def calculate(

    request: Request,
    target: str,
    user: str = Cookie(None)

):

    if not user:
        return RedirectResponse("/", status_code=303)

    nickname = unquote(user)

    # 이미 계산 중인 경우
    if nickname in RUNNING_USERS:
        return HTMLResponse("""
        <script>
            alert("이미 최적 조합 계산이 진행 중입니다.");
            location.href="/magicstone";
        </script>
        """)

    RUNNING_USERS.add(nickname)

    try:

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
            target,
            setting
        )

        return templates.TemplateResponse(

            request=request,

            name="magicstone_result.html",

            context={

                "target": target,
                "value": round(best_value, 2),
                "team": best_team

            }

        )

    finally:
        # 계산 종료 시 반드시 해제
        RUNNING_USERS.discard(nickname)


@router.get("/calculate")
async def calculate_all():

    return RedirectResponse("/magicstone/calculate/순격", status_code=302)