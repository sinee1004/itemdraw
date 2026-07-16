
from collections import defaultdict
from magicstone.engine import Engine


class Optimizer:

    def __init__(self, stones):

        self.all_stones = stones

    

    def find_best(

        self,

        target1,
        target1_value,
        target2,

        setting=None

    ):

        self.setting = setting
        self.best_value = -1
        self.best_team = []

        self.condition_target = target1
        self.condition_value = target1_value
        self.target = target2
        self.checked = 0

        # 원본 스톤 목록 복원
        self.stones = list(self.all_stones)

        # 목표 능력치와 관련된 스톤만 추출
        self.stones = [
            stone
            for stone in self.stones
            if (
                self.is_target_related(stone, target1)
                or
                self.is_target_related(stone, target2)
            )
        ]

        best_stones = {}

        for stone in self.stones:

            key = (
                stone.name,
                stone.potential
            )

            if (
                key not in best_stones
                or stone.potential_value > best_stones[key].potential_value
            ):
                best_stones[key] = stone

        self.stones = list(best_stones.values())

        # 목표 능력치와 관련성이 높은 스톤부터 탐색
        self.stones.sort(

            key=lambda stone: (

                (
                    (stone.value1 if self.target in stone.stat1 else 0) +
                    (stone.value2 if self.target in stone.stat2 else 0)
                ),

                (
                    stone.potential_value
                    if self.target in stone.potential
                    else 0
                ),

                stone.value1 + stone.value2

            ),

            reverse=True

        )

        # Engine는 한 번만 생성
        self.engine = Engine([], self.setting)

        self.search(

            index=0,

            team=[],

            name_set=set(),

            shape_count={
                "원":0,
                "세모":0,
                "다이아":0,
                "육각":0,
                "별":0,
                "달":0
            },

            grade_count={
                "에픽":0,
                "전설":0,
                "신화":0
            },

            potential_count=defaultdict(int)

        )

        return self.best_value, self.best_team


    def find_all(self):

        result = {}

        for target in [

            "순격",
            "강습",
            "추상",
            "근성",
            "방감",
            "요새"

        ]:

            value, team = self.find_best(
                target,
                0,
                target
            )

            result[target] = {

                "value": value,

                "team": team

            }

        return result
    
    def search(

        self,

        index,

        team,

        name_set,

        shape_count,

        grade_count,

        potential_count

    ):

       # 5개 완성
        if len(team) == 5:

            self.checked += 1

            self.engine.set_team(

                team,

                shape_count,

                grade_count,

                potential_count

            )

            result = self.engine.calculate()

            condition = result.get(self.condition_target, 0)

            if condition < self.condition_value:
                return

            value = result.get(self.target, 0)

            if value > self.best_value:

                self.best_value = value
                self.best_team = team.copy()

            return
               

        # 남은 스톤으로 5개를 못 채우면 종료
        if len(self.stones) - index < 5 - len(team):
            return

        stone = self.stones[index]

        # 선택
        if (
            stone.name not in name_set
            and shape_count[stone.shape] < 3
        ):

            team.append(stone)
            name_set.add(stone.name)
            shape_count[stone.shape] += 1
            grade_count[stone.grade] += 1
            potential_count[stone.potential] += 1

            self.search(
                index + 1,
                team,
                name_set,
                shape_count,
                grade_count,
                potential_count
            )

            team.pop()
            name_set.remove(stone.name)
            shape_count[stone.shape] -= 1
            grade_count[stone.grade] -= 1
            potential_count[stone.potential] -= 1

        # 선택 안함
        self.search(
            index + 1,
            team,
            name_set,
            shape_count,
            grade_count,
            potential_count
        )

    def is_target_related(self, stone, target):

    # 공통 잠재력은 항상 계산 대상
        common = {
            "매직스톤단련",
            "붉은빛집중",
            "만물조형",
            "인장동조",
            "잠재력공명",
            "원근잠재력"
        }

        if stone.potential in common:
            return True

        if target in stone.stat1:
            return True

        if target in stone.stat2:
            return True

        if target in stone.potential:
            return True

        return False    