from __future__ import annotations

from typing import Protocol


class GeoIndex(Protocol):
    def cell(self, latitude: float, longitude: float, resolution: int) -> str: ...
    def parent(self, cell: str, resolution: int) -> str: ...
    def grid_distance(self, a: str, b: str) -> int: ...
    def disk(self, cell: str, k: int) -> set[str]: ...
    def boundary(self, cell: str) -> list[tuple[float, float]]: ...


class H3GeoIndex:
    """Production adapter for h3-py 4.x."""

    def __init__(self) -> None:
        try:
            import h3  # type: ignore
        except ImportError as exc:
            raise RuntimeError("h3 is required. Run: pip install -r requirements.txt") from exc
        self._h3 = h3

    def cell(self, latitude: float, longitude: float, resolution: int) -> str:
        return str(self._h3.latlng_to_cell(latitude, longitude, resolution))

    def parent(self, cell: str, resolution: int) -> str:
        return str(self._h3.cell_to_parent(cell, resolution))

    def grid_distance(self, a: str, b: str) -> int:
        try:
            return int(self._h3.grid_distance(a, b))
        except Exception:
            return 10**9

    def disk(self, cell: str, k: int) -> set[str]:
        return {str(x) for x in self._h3.grid_disk(cell, k)}

    def boundary(self, cell: str) -> list[tuple[float, float]]:
        return [(float(lat), float(lon)) for lat, lon in self._h3.cell_to_boundary(cell)]


class SyntheticGeoIndex:
    """Deterministic adapter used only in tests and dependency-free smoke runs.

    Cell format is g<resolution>:<x>:<y>. It must never be used to claim H3 output.
    """

    def cell(self, latitude: float, longitude: float, resolution: int) -> str:
        scale = 10 ** max(0, min(5, resolution - 5))
        x = round((longitude + 180.0) * scale)
        y = round((latitude + 90.0) * scale)
        return f"g{resolution}:{x}:{y}"

    def parent(self, cell: str, resolution: int) -> str:
        src, x, y = cell.split(":")
        src_res = int(src[1:])
        diff = max(0, src_res - resolution)
        factor = 10**diff
        return f"g{resolution}:{int(x)//factor}:{int(y)//factor}"

    def _xy(self, cell: str) -> tuple[int, int]:
        _, x, y = cell.split(":")
        return int(x), int(y)

    def grid_distance(self, a: str, b: str) -> int:
        ax, ay = self._xy(a); bx, by = self._xy(b)
        return max(abs(ax-bx), abs(ay-by))

    def disk(self, cell: str, k: int) -> set[str]:
        p, x, y = cell.split(":"); x=int(x); y=int(y)
        return {f"{p}:{x+dx}:{y+dy}" for dx in range(-k,k+1) for dy in range(-k,k+1)}

    def boundary(self, cell: str) -> list[tuple[float, float]]:
        p, x, y = cell.split(":"); r=int(p[1:]); scale=10 ** max(0, min(5, r-5)); x=int(x); y=int(y)
        lon=x/scale-180.0; lat=y/scale-90.0; d=0.5/scale
        return [(lat-d,lon-d),(lat-d,lon+d),(lat+d,lon+d),(lat+d,lon-d)]
