"""FastAPI 入口：提供 Hamilton 法席位分配悖论扫描 API 与静态页面。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from .hamilton import (
    exact_decimal,
    fraction_str,
    new_region_disturbance,
    population_paradox,
    scan_range,
)

MAX_SPAN = 500          # 扫描跨度上限：end - start <= 500
MAX_NEW_SPAN = 50       # 新增席位扫描跨度上限：added_end - added_start <= 50
MAX_REGIONS = 100       # 地区数量上限
MAX_POPULATION = 10**12 # 单个地区人口上限
MAX_SEATS = 10**6       # 席位总数上限

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Hamilton 最大余数席位分配悖论核查", version="1.0.0")


class Region(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    population: int = Field(gt=0, le=MAX_POPULATION)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("地区名称不能为空")
        return v


class ScanRequest(BaseModel):
    regions: list[Region] = Field(min_length=2, max_length=MAX_REGIONS)
    start: int = Field(ge=1, le=MAX_SEATS)
    end: int = Field(ge=2, le=MAX_SEATS)

    @model_validator(mode="after")
    def check_request(self) -> "ScanRequest":
        if self.end <= self.start:
            raise ValueError("席位终止值必须大于起始值")
        if self.end - self.start > MAX_SPAN:
            raise ValueError(f"扫描跨度（终止值 − 起始值）不能超过 {MAX_SPAN}")
        names = [r.name for r in self.regions]
        if len(set(names)) != len(names):
            raise ValueError("地区名称不能重复")
        return self


class PopulationRegion(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    population_before: int = Field(gt=0, le=MAX_POPULATION)
    population_after: int = Field(gt=0, le=MAX_POPULATION)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("地区名称不能为空")
        return v


class PopulationRequest(BaseModel):
    regions: list[PopulationRegion] = Field(min_length=2, max_length=MAX_REGIONS)
    seats: int = Field(ge=1, le=MAX_SEATS)

    @model_validator(mode="after")
    def check_request(self) -> "PopulationRequest":
        names = [r.name for r in self.regions]
        if len(set(names)) != len(names):
            raise ValueError("地区名称不能重复")
        return self


class NewRegionRequest(BaseModel):
    regions: list[Region] = Field(min_length=2, max_length=MAX_REGIONS)
    base_seats: int = Field(ge=1, le=MAX_SEATS)
    new_region: Region
    added_start: int = Field(ge=1, le=MAX_SEATS)
    added_end: int = Field(ge=1, le=MAX_SEATS)

    @model_validator(mode="after")
    def check_request(self) -> "NewRegionRequest":
        if self.added_end < self.added_start:
            raise ValueError("新增席位终止值必须不小于起始值")
        if self.added_end - self.added_start > MAX_NEW_SPAN:
            raise ValueError(f"新增席位扫描跨度（终止值 − 起始值）不能超过 {MAX_NEW_SPAN}")
        if self.base_seats + self.added_end > MAX_SEATS:
            raise ValueError(f"基准席位与新增席位之和不能超过 {MAX_SEATS}")
        names = [r.name for r in self.regions] + [self.new_region.name]
        if len(set(names)) != len(names):
            raise ValueError("地区名称不能重复（含新增地区）")
        return self


# 可复现内置示例：总人口 100，总席位 10 -> 11 时丁区由 1 席降为 0 席。
EXAMPLE = {
    "regions": [
        {"name": "甲区", "population": 44},
        {"name": "乙区", "population": 43},
        {"name": "丙区", "population": 7},
        {"name": "丁区", "population": 6},
    ],
    "start": 8,
    "end": 14,
}

# 人口悖论可复现内置示例：固定总席位 10，乙区增长比 36/31 高于丙区 8/7
# （交叉相乘验证：36×14 = 504 > 496 = 16×31），但重新分配后
# 乙区反而由 6 席降为 5 席，丙区由 2 席升为 3 席。
POPULATION_EXAMPLE = {
    "regions": [
        {"name": "甲区", "population_before": 11, "population_after": 15},
        {"name": "乙区", "population_before": 31, "population_after": 36},
        {"name": "丙区", "population_before": 14, "population_after": 16},
    ],
    "seats": 10,
}

# 新增地区席位扰动可复现内置示例：原地区人口 45/35/20（总人口 100），
# 基准总席位 8 -> 分配 4、3、1；并入人口 15 的丁区且新增 1 席（总席位 9）后
# 变为 3、3、2（丁区 1 席）：甲区减席、丙区增席，构成扰动事件。
NEW_REGION_EXAMPLE = {
    "regions": [
        {"name": "甲区", "population": 45},
        {"name": "乙区", "population": 35},
        {"name": "丙区", "population": 20},
    ],
    "base_seats": 8,
    "new_region": {"name": "丁区", "population": 15},
    "added_start": 1,
    "added_end": 10,
}


def serialize_row(row: dict) -> dict:
    return {
        "index": row["index"],
        "population": row["population"],
        "quota_str": fraction_str(row["quota"]),
        "quota_decimal": exact_decimal(row["quota"]),
        "floor": row["floor"],
        "remainder_str": fraction_str(row["remainder"]),
        "remainder_decimal": exact_decimal(row["remainder"]),
        "remainder_rank": row["remainder_rank"],
        "remainder_awarded": row["remainder_awarded"],
        "seats": row["seats"],
    }


@app.post("/api/scan")
def scan(req: ScanRequest) -> dict:
    populations = [r.population for r in req.regions]
    names = [r.name for r in req.regions]
    allocations, paradoxes = scan_range(populations, req.start, req.end)
    return {
        "regions": [
            {"index": i, "name": r.name, "population": r.population}
            for i, r in enumerate(req.regions)
        ],
        "total_population": sum(populations),
        "start": req.start,
        "end": req.end,
        "results": [
            {
                "seats_total": s,
                "remaining_seats": allocations[s]["remaining_seats"],
                "rows": [serialize_row(row) for row in allocations[s]["rows"]],
            }
            for s in range(req.start, req.end + 1)
        ],
        "paradoxes": [
            {
                "from_seats": p["from_seats"],
                "to_seats": p["to_seats"],
                "losers": [
                    {
                        "index": l["index"],
                        "name": names[l["index"]],
                        "before": l["before"],
                        "after": l["after"],
                    }
                    for l in p["losers"]
                ],
            }
            for p in paradoxes
        ],
    }


@app.get("/api/example")
def get_example() -> dict:
    return EXAMPLE


@app.post("/api/population")
def population(req: PopulationRequest) -> dict:
    before = [r.population_before for r in req.regions]
    after = [r.population_after for r in req.regions]
    names = [r.name for r in req.regions]
    result = population_paradox(before, after, req.seats)
    return {
        "regions": [
            {
                "index": i,
                "name": r.name,
                "population_before": r.population_before,
                "population_after": r.population_after,
            }
            for i, r in enumerate(req.regions)
        ],
        "seats_total": req.seats,
        "total_population_before": sum(before),
        "total_population_after": sum(after),
        "rows": [
            {
                "index": row["index"],
                "name": names[row["index"]],
                "population_before": row["population_before"],
                "population_after": row["population_after"],
                "growth_str": fraction_str(row["growth"]),
                "growth_decimal": exact_decimal(row["growth"]),
                "seats_before": row["seats_before"],
                "seats_after": row["seats_after"],
                "delta": row["delta"],
            }
            for row in result["rows"]
        ],
        "before": {
            "remaining_seats": result["before"]["remaining_seats"],
            "rows": [serialize_row(row) for row in result["before"]["rows"]],
        },
        "after": {
            "remaining_seats": result["after"]["remaining_seats"],
            "rows": [serialize_row(row) for row in result["after"]["rows"]],
        },
        "anomalies": [
            {
                "loser": {"index": a["loser"], "name": names[a["loser"]]},
                "gainer": {"index": a["gainer"], "name": names[a["gainer"]]},
                # 交叉相乘的整数乘积可能超出 JS 安全整数范围，以字符串传输
                "cross_loser": str(a["cross_loser"]),
                "cross_gainer": str(a["cross_gainer"]),
            }
            for a in result["anomalies"]
        ],
    }


@app.get("/api/population-example")
def get_population_example() -> dict:
    return POPULATION_EXAMPLE


@app.post("/api/new-region")
def new_region(req: NewRegionRequest) -> dict:
    populations = [r.population for r in req.regions]
    names = [r.name for r in req.regions]
    result = new_region_disturbance(
        populations,
        req.base_seats,
        req.new_region.population,
        req.added_start,
        req.added_end,
    )
    baseline_seats = [row["seats"] for row in result["baseline"]["rows"]]

    def scenario_out(sc: dict) -> dict:
        return {
            "added_seats": sc["added_seats"],
            "seats_total": sc["seats_total"],
            "remaining_seats": sc["merged"]["remaining_seats"],
            "rows": [serialize_row(row) for row in sc["merged"]["rows"]],
            "deltas": sc["deltas"],
            "losers": sc["losers"],
            "gainers": sc["gainers"],
            "disturbance": sc["disturbance"],
        }

    def mover(index: int, sc: dict) -> dict:
        return {
            "index": index,
            "name": names[index],
            "before": baseline_seats[index],
            "after": sc["merged"]["rows"][index]["seats"],
        }

    return {
        "regions": [
            {"index": i, "name": r.name, "population": r.population}
            for i, r in enumerate(req.regions)
        ],
        "new_region": {"name": req.new_region.name, "population": req.new_region.population},
        "base_seats": req.base_seats,
        "added_start": req.added_start,
        "added_end": req.added_end,
        "total_population_base": sum(populations),
        "total_population_merged": sum(populations) + req.new_region.population,
        "baseline": {
            "seats_total": req.base_seats,
            "remaining_seats": result["baseline"]["remaining_seats"],
            "rows": [serialize_row(row) for row in result["baseline"]["rows"]],
        },
        "scenarios": [scenario_out(sc) for sc in result["scenarios"]],
        "disturbances": [
            {
                "added_seats": sc["added_seats"],
                "seats_total": sc["seats_total"],
                "losers": [mover(i, sc) for i in sc["losers"]],
                "gainers": [mover(i, sc) for i in sc["gainers"]],
            }
            for sc in result["disturbances"]
        ],
    }


@app.get("/api/new-region-example")
def get_new_region_example() -> dict:
    return NEW_REGION_EXAMPLE


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
