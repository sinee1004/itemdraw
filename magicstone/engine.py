from collections import defaultdict

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

        self.stones = list(stones)

        self.setting = setting

        self.shape_count = defaultdict(int)
        self.grade_count = defaultdict(int)
        self.potential_count = defaultdict(int)

    
            
    def set_team(self, stones, shape_count, grade_count, potential_count):

        self.stones = stones

        self.shape_count = shape_count
        self.grade_count = grade_count
        self.potential_count = potential_count

    def apply_resonance(self):

        resonance = []

        for i, stone in enumerate(self.stones):

            if stone.potential == "잠재력공명":
                resonance.append((i, stone.potential_value))

        bonus = [1.0] * len(self.stones)

        for index, value in resonance:

            rate = 1 + value / 100

            for i, stone in enumerate(self.stones):

                if i == index:
                    continue

                if stone.potential == "잠재력공명":
                    continue

                bonus[i] *= rate

        return bonus

                

    def apply_mastery(self, stone):

        stat = {}

        if stone.stat1:
            stat[stone.stat1] = stone.value1

        if stone.stat2:
            stat[stone.stat2] = stone.value2

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

                

                final[stat] *= (1 + value / 100)

                

            else:

                continue

        return final

    def calculate(self):

        resonance_bonus = self.apply_resonance()

        result = defaultdict(float)

        if self.setting:

            result["순격"] = self.setting["순격"]
            result["강습"] = self.setting["강습"]
            result["추상"] = self.setting["추상"]

            result["근성"] = self.setting["근성"]
            result["방감"] = self.setting["방감"]
            result["요새"] = self.setting["요새"]

        bonus = defaultdict(float)

        for i, stone in enumerate(self.stones):

            # 기본속성만
            stat = self.apply_mastery(stone)

            rate = resonance_bonus[i]

            if rate != 1:

                for k in stat:
                    stat[k] *= rate

            # 단련, 붉은빛집중 등은 기본속성만 적용
            stat = self.apply_base_potential(
                stone,
                stat
            )

            # 기본속성 합산
            for key, value in stat.items():

                if key.endswith("보너스%"):

                    bonus[key] += value

                else:

                    result[key] += value

            # ==========================
            # 숙달은 마지막에 그대로 더한다
            # ==========================
            if stone.potential.endswith("숙달"):

                target = stone.potential.replace("숙달", "").strip()

                mastery = stone.potential_value

                # 잠재력공명만 적용
                if rate != 1:
                    mastery *= rate

                result[target] += mastery

        # %보너스 적용
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

        # 증폭
        result = self.apply_amplify(result)

        return dict(result)
    
    def apply_base_potential(self, stone, stat):

        category = stone.potential
        

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
        

        

                    
        return stat