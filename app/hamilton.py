"""Hamilton 法（最大余数法）席位分配的精确计算核心。

所有配额与余数均使用 fractions.Fraction 精确分数表示，
余数排名、决胜与席位分配全程不使用浮点数。
"""

from __future__ import annotations

from fractions import Fraction


def exact_decimal(value: Fraction, places: int = 6) -> str:
    """把非负分数四舍五入到 places 位小数（全程整数运算，仅供展示）。"""
    scaled = value.numerator * (10 ** places)
    q, r = divmod(scaled, value.denominator)
    if r * 2 >= value.denominator:
        q += 1
    digits = str(q).rjust(places + 1, "0")
    head, tail = digits[:-places], digits[-places:].rstrip("0")
    return head if not tail else f"{head}.{tail}"


def fraction_str(value: Fraction) -> str:
    """精确分数的字符串形式，分母为 1 时只显示整数。"""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def hamilton_allocate(populations: list[int], seats: int) -> dict:
    """对给定人口列表与总席位数，返回 Hamilton 法的完整分配结果。

    返回 {"seats_total", "remaining_seats", "rows"}，每行包含配额、
    整数席位、余数、余数排名、是否获得余数席位与最终席位（Fraction/int）。
    """
    total_population = sum(populations)
    quotas = [Fraction(p * seats, total_population) for p in populations]
    floors = [q.numerator // q.denominator for q in quotas]
    remainders = [q - f for q, f in zip(quotas, floors)]
    remaining = seats - sum(floors)

    # 余数降序；余数相同 -> 人口较多者优先；再相同 -> 录入顺序较早者优先。
    # 排序键只含 Fraction 与 int，绝不引入浮点数。
    order = sorted(
        range(len(populations)),
        key=lambda i: (remainders[i], populations[i], -i),
        reverse=True,
    )
    ranks = [0] * len(populations)
    for rank, idx in enumerate(order, start=1):
        ranks[idx] = rank

    allocation = list(floors)
    awarded = [False] * len(populations)
    for idx in order[:remaining]:
        allocation[idx] += 1
        awarded[idx] = True

    rows = []
    for i, pop in enumerate(populations):
        rows.append(
            {
                "index": i,
                "population": pop,
                "quota": quotas[i],
                "floor": floors[i],
                "remainder": remainders[i],
                "remainder_rank": ranks[i],
                "remainder_awarded": awarded[i],
                "seats": allocation[i],
            }
        )
    return {"seats_total": seats, "remaining_seats": remaining, "rows": rows}


def compare_growth(after_a: int, before_a: int, after_b: int, before_b: int) -> int:
    """整数交叉相乘比较增长比 after_a/before_a 与 after_b/before_b。

    返回 1 / 0 / -1 分别表示前者大于 / 等于 / 小于后者。
    只比较 after_a * before_b 与 after_b * before_a 两个整数，
    不使用浮点数，也不使用任何舍入后的展示值。
    """
    left = after_a * before_b
    right = after_b * before_a
    return (left > right) - (left < right)


def population_paradox(
    populations_before: list[int], populations_after: list[int], seats: int
) -> dict:
    """固定总席位下，对同一组地区的前后两期人口分别做 Hamilton 分配并核查人口悖论。

    返回 {"seats_total", "before", "after", "rows", "anomalies"}：
    before/after 为两期完整分配结果；rows 汇总每个地区的两期人口、
    精确增长比（Fraction）、两期席位与变化量；anomalies 记录每个
    「减席地区增长比严格高于增席地区」的异常组合，并附上交叉相乘的
    两个整数乘积作为可复核证据。
    """
    alloc_before = hamilton_allocate(populations_before, seats)
    alloc_after = hamilton_allocate(populations_after, seats)

    rows = []
    for i, (rb, ra) in enumerate(zip(alloc_before["rows"], alloc_after["rows"])):
        rows.append(
            {
                "index": i,
                "population_before": populations_before[i],
                "population_after": populations_after[i],
                "growth": Fraction(populations_after[i], populations_before[i]),
                "seats_before": rb["seats"],
                "seats_after": ra["seats"],
                "delta": ra["seats"] - rb["seats"],
            }
        )

    losers = [r for r in rows if r["delta"] < 0]
    gainers = [r for r in rows if r["delta"] > 0]
    anomalies = []
    for loser in losers:
        for gainer in gainers:
            li, gi = loser["index"], gainer["index"]
            # 整数交叉相乘：增长比 after/before 前者更高
            # 当且仅当 after_l * before_g > after_g * before_l。
            cross_loser = populations_after[li] * populations_before[gi]
            cross_gainer = populations_after[gi] * populations_before[li]
            if cross_loser > cross_gainer:
                anomalies.append(
                    {
                        "loser": li,
                        "gainer": gi,
                        "cross_loser": cross_loser,
                        "cross_gainer": cross_gainer,
                    }
                )

    return {
        "seats_total": seats,
        "before": alloc_before,
        "after": alloc_after,
        "rows": rows,
        "anomalies": anomalies,
    }


def scan_range(populations: list[int], start: int, end: int) -> tuple[dict, list]:
    """对 [start, end] 内每个总席位数做分配，并扫描阿拉巴马悖论。

    返回 (allocations, paradoxes)：allocations 以总席位数为键；
    paradoxes 记录每次「总席位 +1 后某地区席位反而减少」的事件。
    """
    allocations = {s: hamilton_allocate(populations, s) for s in range(start, end + 1)}
    paradoxes = []
    for s in range(start, end):
        before = allocations[s]["rows"]
        after = allocations[s + 1]["rows"]
        losers = [
            {"index": i, "before": b["seats"], "after": a["seats"]}
            for i, (b, a) in enumerate(zip(before, after))
            if a["seats"] < b["seats"]
        ]
        if losers:
            paradoxes.append({"from_seats": s, "to_seats": s + 1, "losers": losers})
    return allocations, paradoxes


def new_region_disturbance(
    populations: list[int],
    base_seats: int,
    new_population: int,
    extra_start: int,
    extra_end: int,
) -> dict:
    """新增地区席位扰动分析。

    先对原地区按基准总席位做一次 Hamilton 分配（baseline）；随后把新增地区
    并入人口列表，对 [extra_start, extra_end] 内每个新增席位数 k，以
    base_seats + k 为总席位重新分配。逐档比较所有原地区相对基准分配的席位
    变化，仅当原地区中同时出现减席者与增席者时标记为一次扰动事件
    （新增地区自身的席位不计入减/增席判定）。

    返回 {"base_seats", "new_population", "baseline", "results",
    "disturbances"}：baseline 为原地区基准分配；results 逐档给出并入后的
    完整分配（含新增地区）、各原地区席位变化及减/增席名单；disturbances
    只收录扰动档。
    """
    baseline = hamilton_allocate(populations, base_seats)
    base_seat_map = [row["seats"] for row in baseline["rows"]]

    merged_populations = list(populations) + [new_population]
    n_original = len(populations)

    results = []
    disturbances = []
    for extra in range(extra_start, extra_end + 1):
        total_seats = base_seats + extra
        merged = hamilton_allocate(merged_populations, total_seats)

        deltas = []
        for i in range(n_original):
            before = base_seat_map[i]
            after = merged["rows"][i]["seats"]
            deltas.append(
                {"index": i, "before": before, "after": after, "delta": after - before}
            )
        losers = [d for d in deltas if d["delta"] < 0]
        gainers = [d for d in deltas if d["delta"] > 0]
        is_disturbance = bool(losers) and bool(gainers)

        entry = {
            "extra_seats": extra,
            "seats_total": total_seats,
            "remaining_seats": merged["remaining_seats"],
            "rows": merged["rows"],
            "deltas": deltas,
            "new_region_seats": merged["rows"][n_original]["seats"],
            "is_disturbance": is_disturbance,
            "losers": losers,
            "gainers": gainers,
        }
        results.append(entry)
        if is_disturbance:
            disturbances.append(
                {
                    "extra_seats": extra,
                    "seats_total": total_seats,
                    "losers": losers,
                    "gainers": gainers,
                }
            )

    return {
        "base_seats": base_seats,
        "new_population": new_population,
        "baseline": baseline,
        "results": results,
        "disturbances": disturbances,
    }
