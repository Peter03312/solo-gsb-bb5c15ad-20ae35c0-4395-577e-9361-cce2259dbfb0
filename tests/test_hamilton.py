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
    # 内置示例：原地区 111/197/319、基准 9 席（2、3、4），新增地区人口 132，
    # 扫描新增席位 1~5；仅新增 2 席（总席位 11）时甲区减席、丙区增席
    result = new_region_disturbance([111, 197, 319], 9, 132, 1, 5)
    assert [r["seats"] for r in result["baseline"]["rows"]] == [2, 3, 4]

    by_extra = {e["extra_seats"]: e for e in result["results"]}
    # 新增 1 席：甲区减席但无原地区增席（新地区直接得 2 席），不是扰动
    assert by_extra[1]["is_disturbance"] is False
    assert [x["delta"] for x in by_extra[1]["deltas"]] == [-1, 0, 0]
    assert by_extra[1]["new_region_seats"] == 2

    # 新增 2 席：甲区 2->1 减席、丙区 4->5 增席，构成扰动
    event = by_extra[2]
    assert event["is_disturbance"] is True
    assert [r["seats"] for r in event["rows"]] == [1, 3, 5, 2]
    assert [x["delta"] for x in event["deltas"]] == [-1, 0, 1]
    assert [(x["index"], x["before"], x["after"]) for x in event["losers"]] == [(0, 2, 1)]
    assert [(x["index"], x["before"], x["after"]) for x in event["gainers"]] == [(2, 4, 5)]

    # 其余档位都不是扰动
    for k in (3, 4, 5):
        assert by_extra[k]["is_disturbance"] is False

    assert len(result["disturbances"]) == 1
    d = result["disturbances"][0]
    assert (d["extra_seats"], d["seats_total"]) == (2, 11)


def test_new_region_disturbance_only_gainers_is_not_event():
    # 新增地区人口极小：新增 2~4 席时原地区只可能持平或增席，不构成扰动
    result = new_region_disturbance([44, 43, 7, 6], 10, 1, 2, 4)
    assert result["disturbances"] == []
    for entry in result["results"]:
        assert entry["is_disturbance"] is False
        assert entry["losers"] == []
        # 每档总席位守恒（含新增地区）
        assert sum(r["seats"] for r in entry["rows"]) == entry["seats_total"]


def test_new_region_disturbance_only_losers_is_not_event():
    # 大新增地区在新增 1 席时可能令多个原地区同时减席但无人增席：不算扰动
    result = new_region_disturbance([35, 222, 287], 23, 66, 1, 1)
    entry = result["results"][0]
    assert [x["delta"] for x in entry["deltas"]] == [-1, 0, -1]
    assert entry["gainers"] == []
    assert entry["is_disturbance"] is False
    assert result["disturbances"] == []


def test_new_region_disturbance_seat_conservation_and_baseline_unchanged():
    pops = [111, 197, 319]
    result = new_region_disturbance(pops, 9, 132, 1, 50)
    assert len(result["results"]) == 50
    for entry in result["results"]:
        assert sum(r["seats"] for r in entry["rows"]) == entry["seats_total"]
        # 基准分配在每档比较中保持一致
        assert [x["before"] for x in entry["deltas"]] == [2, 3, 4]
        # 变化量总和加上新增地区席位等于新增席位数
        assert sum(x["delta"] for x in entry["deltas"]) + entry["new_region_seats"] == entry["extra_seats"]


def test_new_region_disturbance_exact_fractions():
    # 并入后总席位 11、总人口 759 的精确配额：甲 111*11/759 = 37/23
    result = new_region_disturbance([111, 197, 319], 9, 132, 2, 2)
    rows = result["results"][0]["rows"]
    assert rows[0]["quota"] == Fraction(37, 23)
    assert rows[0]["remainder"] == Fraction(14, 23)
