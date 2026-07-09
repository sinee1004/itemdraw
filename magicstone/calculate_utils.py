from magicstone.magicstone_data import STONE_DATA, GRADE_VALUE


def get_stone_info(name: str, grade: str):

    stone = STONE_DATA[name]

    value = GRADE_VALUE[stone["shape"]][grade]

    return {

        "name": name,

        "shape": stone["shape"],

        "grade": grade,

        "stat1": stone["stat1"],

        "value1": value,

        "stat2": stone["stat2"],

        "value2": value if stone["stat2"] else 0

    }


def get_all_names(shape):

    names = []

    for name, data in STONE_DATA.items():

        if data["shape"] == shape:

            names.append(name)

    return sorted(names)


def get_shapes():

    return [

        "원",
        "세모",
        "다이아",
        "육각",
        "별",
        "달"

    ]


def get_grades():

    return [

        "에픽",
        "전설",
        "신화"

    ]