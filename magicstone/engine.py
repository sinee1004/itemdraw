from collections import defaultdict
from copy import deepcopy
from pathlib import Path

DEBUG = True
DEBUG_FILE = Path("engine_debug.txt")


def debug(msg="", enabled=False):

    if not enabled:
        return

    with DEBUG_FILE.open("a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

class MagicStone:

    def __init__(
        self,
        name,
        shape,
        grade,
        stat1,
        value1,
        stat2="",
        value2=0,
        potential="",
        potential_value=0,
    ):

        self.name = name
        self.shape = shape
        self.grade = grade

        self.stat1 = stat1
        self.value1 = value1

        self.stat2 = stat2
        self.value2 = value2

        self.potential = potential
        self.potential_value = potential_value


class Engine:

    def __init__(self, stones, setting=None):

        self.stones = deepcopy(stones)

        self.setting = setting

        self.shape_count = defaultdict(int)
        self.grade_count = defaultdict(int)
        self.potential_count = defaultdict(int)

    def count(self):

        self.shape_count.clear()
        self.grade_count.clear()
        self.potential_count.clear()

        for stone in self.stones:

            self.shape_count[stone.shape] += 1
            self.grade_count[stone.grade] += 1
            self.potential_count[stone.potential] += 1

    def apply_resonance(self, debug_mode=False):

        resonance = []

        for i, stone in enumerate(self.stones):

            if stone.potential == "잠재력공명":
                resonance.append((i, stone.potential_value))

        for index, value in resonance:

            for i, stone in enumerate(self.stones):

                if i == index:
                    continue

                if stone.potential == "잠재력공명":
                    continue

                stone.potential_value *= (
                    1 + value / 100
                )

                debug(
                    f"공명 적용 : {stone.name} | "
                    f"{stone.potential} -> "
                    f"{stone.potential_value:.2f}",
                    debug
                )

    def apply_mastery(self, stone):

        stat = {}

        if stone.stat1:
            stat[stone.stat1] = stone.value1

        if stone.stat2:
            stat[stone.stat2] = stone.value2

        if stone.potential.endswith("숙달"):

            target = stone.potential.replace("숙달", "").strip()

            # 기본속성이 없어도 숙달은 해당 능력치에 추가
            stat[target] = stat.get(target, 0) + stone.potential_value

        return stat

  

    def apply_amplify(self, result):

        final = result.copy()

        amplify = defaultdict(float)

        # 증폭 합산
        for stone in self.stones:

            if stone.potential.endswith("증폭"):

                stat = stone.potential.replace("증폭", "").strip()

                amplify[stat] += stone.potential_value

        

        # 한 번만 적용
        for stat, value in amplify.items():

            if stat in final:

                before = final[stat]

                final[stat] *= (1 + value / 100)

                

            else:

                print(f"[경고] '{stat}' 항목을 result에서 찾지 못했습니다.")

        return final

    def calculate(self, debug_mode=False):

        if debug_mode:
            DEBUG_FILE.write_text("", encoding="utf-8")

        self.count()

        self.apply_resonance(debug_mode)

        result = defaultdict(float)

        if self.setting:

            result["순격"] = self.setting["순격"]
            result["강습"] = self.setting["강습"]
            result["추상"] = self.setting["추상"]

            result["근성"] = self.setting["근성"]
            result["방감"] = self.setting["방감"]
            result["요새"] = self.setting["요새"]

        bonus = defaultdict(float)

        for stone in self.stones:

            stat = self.apply_mastery(stone)

            stat = self.apply_base_potential(
                stone,
                stat,
                debug_mode
            )
            

            for key, value in stat.items():

                if key.endswith("보너스%"):

                    bonus[key] += value

                else:

                    result[key] += value

        for target in [

            "순격",

            "강습",

            "추상"

        ]:

            key = target + "보너스%"

            if key in bonus:

                result[target] *= (

                    1 +

                    bonus[key] / 100

                )

        result = self.apply_amplify(result)

        
    
        debug("", debug_mode)
        debug("===================================", debug_mode)
        debug("선택된 매직스톤", debug_mode)
        debug("===================================", debug_mode)

        for stone in self.stones:
            debug(
                f"{stone.name} | "
                f"{stone.potential} {stone.potential_value:.2f}",
                debug_mode
            )

        debug("", debug_mode)
        debug("===================================", debug_mode)
        debug("최종 능력치", debug_mode)
        debug("===================================", debug_mode)

        for k, v in result.items():
            debug(f"{k} = {v:.2f}", debug_mode)

        return dict(result)
    
    def apply_base_potential(self, stone, stat, debug_mode=False):

        category = stone.potential
        before = stat.copy()

        if category == "매직스톤단련":

            for k in stat:

                stat[k] *= (

                    1 +

                    stone.potential_value / 100

                )

        elif category == "붉은빛집중":

            myth = self.grade_count["신화"]

            for k in stat:

                stat[k] *= (

                    1 +

                    (stone.potential_value / 100)

                    * myth

                )

        elif category == "만물조형":

            other = len(self.stones)

            other -= self.shape_count[stone.shape]

            for k in stat:

                stat[k] *= (

                    1 +

                    (stone.potential_value / 100)

                    * other

                )

        elif category == "인장동조":

            same = self.shape_count[stone.shape] - 1

            if same < 0:
                same = 0

            for k in stat:

                stat[k] *= (

                    1 +

                    (stone.potential_value / 100)

                    * same

                )

        elif category == "원근잠재력":

            same = self.potential_count[stone.potential] - 1

            if same < 0:

                same = 0

            for k in stat:

                stat[k] *= (

                    1 +

                    (stone.potential_value / 100)

                    * same

                )
        

        if before != stat:

            debug("", debug_mode)
            debug(f"[{stone.name}]", debug_mode)
            debug(f"잠재력 : {category}", debug_mode)

            debug("적용 전", debug_mode)
            for k, v in before.items():
                debug(f"    {k} = {v:.2f}", debug_mode)

            debug("적용 후", debug_mode)
            for k, v in stat.items():
                debug(f"    {k} = {v:.2f}", debug_mode)        
        return stat