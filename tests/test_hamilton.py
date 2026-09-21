"""Hamilton 核心逻辑的单元测试，可用 `python -m pytest tests/` 运行。"""

from fractions import Fraction

from app.hamilton import (
    compare_growth,
    exact_decimal,
    fraction_str,
    hamilton_allocate,
    new_region_disturbance,
    population_paradox,
    scan_range,
)


def seats_of(populations, seats):
    return [row["seats"] for row in hamilton_allocate(populations, seats)["rows"]]


def test_builtin_example_paradox():
    # 内置示例：人口 44/43/7/6，总席位 10 -> 11 时丁区（索引 3）由 1 席降为 0 席
    allocations, paradoxes = scan_range([44, 43, 7, 6], 8, 14)
    assert len(paradoxes) == 1
    p = paradoxes[0]
    assert (p["from_seats"], p["to_seats"]) == (10, 11)
    assert p["losers"] == [{"index": 3, "before": 1, "after": 0}]
    assert [r["seats"] for r in allocations[10]["rows"]] == [4, 4, 1, 1]
    assert [r["seats"] for r in allocations[11]["rows"]] == [5, 5, 1, 0]


def test_classic_minimal_paradox():
    # 经典最小例子：人口 6/6/2，总席位 3 -> 4 时丙由 1 席降为 0 席
    assert seats_of([6, 6, 2], 3) == [1, 1, 1]
    assert seats_of([6, 6, 2], 4) == [2, 2, 0]
    _, paradoxes = scan_range([6, 6, 2], 3, 4)
    assert paradoxes[0]["losers"] == [{"index": 2, "before": 1, "after": 0}]


def test_tie_break_by_population():
    # 余数同为 1/2：人口 3 的地区优先于人口 1 的地区
    assert seats_of([6, 3, 1], 5) == [3, 2, 0]


def test_tie_break_by_input_order():
    # 余数与人口都相同：录入顺序较早者优先
    assert seats_of([3, 2, 2], 2) == [1, 1, 0]


def test_quota_and_remainder_are_exact_fractions():
    result = hamilton_allocate([44, 43, 7, 6], 10)
    rows = result["rows"]
    assert rows[0]["quota"] == Fraction(22, 5)
    assert rows[0]["remainder"] == Fraction(2, 5)
    assert rows[2]["remainder"] == Fraction(7, 10)
    assert result["remaining_seats"] == 2
    # 余数排名：丙(7/10) > 丁(3/5) > 甲(2/5) > 乙(3/10)
    assert [r["remainder_rank"] for r in rows] == [3, 4, 1, 2]


def test_seat_conservation():
    for s in range(1, 60):
        assert sum(seats_of([44, 43, 7, 6], s)) == s


def test_exact_decimal():
    assert exact_decimal(Fraction(1, 3)) == "0.333333"
    assert exact_decimal(Fraction(2, 7)) == "0.285714"
    assert exact_decimal(Fraction(1, 2)) == "0.5"
    assert exact_decimal(Fraction(22, 5)) == "4.4"
    assert exact_decimal(Fraction(121, 25)) == "4.84"
    assert exact_decimal(Fraction(4, 1)) == "4"


def test_fraction_str():
    assert fraction_str(Fraction(22, 5)) == "22/5"
    assert fraction_str(Fraction(4, 1)) == "4"


def test_compare_growth():
    # 交叉相乘比较：3/2 > 4/3；2/3 < 3/2；4/6 == 6/9
    assert compare_growth(3, 2, 4, 3) == 1
    assert compare_growth(2, 3, 3, 2) == -1
    assert compare_growth(4, 6, 6, 9) == 0
    # 大整数也不依赖浮点：(n+1)/n 与 n/(n-1) 在浮点下无法区分，但精确比较前者更小
    assert compare_growth(10**12 + 1, 10**12, 10**12, 10**12 - 1) == -1


def test_population_paradox_builtin_example():
    # 内置示例：固定总席位 10，乙区 31->36（增长比 36/31）高于丙区 14->16（8/7），
    # 但乙区 6 -> 5 减席，丙区 2 -> 3 增席
    result = population_paradox([11, 31, 14], [15, 36, 16], 10)
    assert [r["seats_before"] for r in result["rows"]] == [2, 6, 2]
    assert [r["seats_after"] for r in result["rows"]] == [2, 5, 3]
    assert [r["delta"] for r in result["rows"]] == [0, -1, 1]
    assert result["rows"][1]["growth"] == Fraction(36, 31)
    assert result["rows"][2]["growth"] == Fraction(8, 7)
    assert len(result["anomalies"]) == 1
    anomaly = result["anomalies"][0]
    assert anomaly["loser"] == 1
    assert anomaly["gainer"] == 2
    # 交叉相乘证据：36×14 = 504 > 496 = 16×31
    assert anomaly["cross_loser"] == 504
    assert anomaly["cross_gainer"] == 496


def test_population_paradox_no_anomaly_when_growth_order_matches():
    # 席位易手但减席地区增长比更低：不构成人口悖论
    result = population_paradox([10, 22, 22], [14, 31, 30], 9)
    assert [r["seats_before"] for r in result["rows"]] == [1, 4, 4]
    assert [r["seats_after"] for r in result["rows"]] == [2, 4, 3]
    assert result["anomalies"] == []


def test_population_paradox_growth_tie_is_not_anomaly():
    # 增长比相同（不是严格更高）时不记录异常
    result = population_paradox([10, 20, 20], [11, 22, 21], 9)
    for anomaly in result["anomalies"]:
        li, gi = anomaly["loser"], anomaly["gainer"]
        rows = result["rows"]
        assert rows[li]["growth"] > rows[gi]["growth"]


def test_population_paradox_seat_conservation():
    for s in range(1, 30):
        result = population_paradox([11, 31, 14], [15, 36, 16], s)
        assert sum(r["seats_before"] for r in result["rows"]) == s
        assert sum(r["seats_after"] for r in result["rows"]) == s


def test_new_region_disturbance_builtin_example():
    # 内置示例：人口 45/35/20，基准 8 席 -> [4, 3, 1]；并入人口 15 的新地区、
    # 新增 1 席（总 9 席）后变为 [3, 3, 2] + 新地区 1 席：
    # 甲区减席、丙区增席，原地区之间同时出现减席与增席，构成扰动事件
    result = new_region_disturbance([45, 35, 20], 8, 15, 1, 10)
    assert [r["seats"] for r in result["baseline"]["rows"]] == [4, 3, 1]
    first = result["scenarios"][0]
    assert first["added_seats"] == 1
    assert first["seats_total"] == 9
    assert [r["seats"] for r in first["merged"]["rows"]] == [3, 3, 2, 1]
    assert first["deltas"] == [-1, 0, 1]
    assert first["losers"] == [0]
    assert first["gainers"] == [2]
    assert first["disturbance"] is True
    assert [d["added_seats"] for d in result["disturbances"]] == [1]


def test_new_region_disturbance_requires_both_directions():
    # 人口 50/30/20，基准 10 席 -> [5, 3, 2]；并入人口 25 的新地区：
    # 新增 1 席时甲区 5 -> 4，但席位流向新地区而非原地区，无原地区增席，不构成扰动
    result = new_region_disturbance([50, 30, 20], 10, 25, 1, 2)
    sc1, sc2 = result["scenarios"]
    assert [r["seats"] for r in sc1["merged"]["rows"]] == [4, 3, 2, 2]
    assert sc1["deltas"] == [-1, 0, 0]
    assert sc1["disturbance"] is False
    assert sc2["deltas"] == [0, 0, 0]
    assert sc2["disturbance"] is False
    assert result["disturbances"] == []


def test_new_region_disturbance_seat_conservation_and_flag():
    result = new_region_disturbance([45, 35, 20], 8, 15, 1, 20)
    for sc in result["scenarios"]:
        assert sum(r["seats"] for r in sc["merged"]["rows"]) == 8 + sc["added_seats"]
        # 扰动标记当且仅当原地区之间同时存在减席与增席
        assert sc["disturbance"] == (bool(sc["losers"]) and bool(sc["gainers"]))
        assert sc["losers"] == [i for i, d in enumerate(sc["deltas"]) if d < 0]
        assert sc["gainers"] == [i for i, d in enumerate(sc["deltas"]) if d > 0]


def test_new_region_disturbance_baseline_unchanged_by_scan():
    # 基准分配只依赖原地区人口与基准席位，与扫描区间无关
    base = new_region_disturbance([45, 35, 20], 8, 15, 3, 7)["baseline"]
    assert [r["seats"] for r in base["rows"]] == [4, 3, 1]
    assert [r["quota"] for r in base["rows"]] == [
        Fraction(18, 5),
        Fraction(14, 5),
        Fraction(8, 5),
    ]
