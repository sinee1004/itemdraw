from itertools import combinations

from magicstone.engine import Engine


class Optimizer:

    def __init__(self, stones):

        self.stones = stones

    def is_valid(self, team):

        names = set()

        shape_count = {

            "원": 0,
            "세모": 0,
            "다이아": 0,
            "육각": 0,
            "별": 0,
            "달": 0

        }

        for stone in team:

            # 동일 이름 착용 불가
            if stone.name in names:
                return False

            names.add(stone.name)

            shape_count[stone.shape] += 1

        # 모양별 최대 착용 개수

        if shape_count["원"] > 3:
            return False

        if shape_count["세모"] > 3:
            return False

        if shape_count["다이아"] > 3:
            return False

        if shape_count["육각"] > 3:
            return False

        if shape_count["별"] > 3:
            return False

        if shape_count["달"] > 3:
            return False

        return True

    def find_best(self, target, setting=None):

        self.setting = setting
        self.best_value = -1
        self.best_team = []
        self.target = target
        self.checked = 0

        # 목표 능력치와 관련된 스톤만 추출
        self.stones = [
            stone
            for stone in self.stones
            if self.is_target_related(stone, target)
        ]

        

        

        self.search(

            index=0,

            team=[],

            name_set=set(),

            shape_count={

                "원": 0,
                "세모": 0,
                "다이아": 0,
                "육각": 0,
                "별": 0,
                "달": 0

            }

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

            value, team = self.find_best(target)

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

        shape_count

    ):

       # 5개 완성
        if len(team) == 5:

            self.checked += 1

            engine = Engine(team, self.setting)

            result = engine.calculate()

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

            self.search(
                index + 1,
                team,
                name_set,
                shape_count
            )

            team.pop()
            name_set.remove(stone.name)
            shape_count[stone.shape] -= 1

        # 선택 안함
        self.search(
            index + 1,
            team,
            name_set,
            shape_count
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