from fastapi import APIRouter

from magicstone import stones
from magicstone import calculate

router = APIRouter()

router.include_router(stones.router)
router.include_router(calculate.router)