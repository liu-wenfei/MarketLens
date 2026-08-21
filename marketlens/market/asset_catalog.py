from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


_REQUIRED_COLUMNS = {"stock_id", "weight", "name", "industry", "description"}


class AssetCatalogError(ValueError):
    """The inherited stock-profile source is missing or malformed."""


class AssetNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class AssetDefinition:
    """One investable synthetic sector instrument from stock_profile.csv.

    ``market_weight`` is the inherited source field named ``weight``. It is a
    property of the market/benchmark universe, not a participant portfolio
    weight.
    """

    stock_id: str
    market_weight: float
    name: str
    industry: str
    description: str


def default_stock_profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "stock_profile.csv"


class AssetCatalog:
    """Read the inherited asset universe without modifying the source file."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_stock_profile_path()
        self._assets = self._load()

    def _load(self) -> dict[str, AssetDefinition]:
        if not self.path.exists():
            raise AssetCatalogError(f"Asset catalog not found: {self.path}")

        assets: dict[str, AssetDefinition] = {}
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            missing = _REQUIRED_COLUMNS - columns
            if missing:
                raise AssetCatalogError(
                    f"Asset catalog is missing required columns: {sorted(missing)}"
                )

            for line_number, row in enumerate(reader, start=2):
                stock_id = (row.get("stock_id") or "").strip()
                if not stock_id:
                    raise AssetCatalogError(f"Empty stock_id on line {line_number}")
                if stock_id in assets:
                    raise AssetCatalogError(f"Duplicate stock_id: {stock_id}")

                try:
                    market_weight = float(row["weight"])
                except (TypeError, ValueError) as exc:
                    raise AssetCatalogError(
                        f"Invalid weight for {stock_id} on line {line_number}"
                    ) from exc

                if market_weight < 0:
                    raise AssetCatalogError(f"Negative weight for {stock_id}")

                assets[stock_id] = AssetDefinition(
                    stock_id=stock_id,
                    market_weight=market_weight,
                    name=(row.get("name") or "").strip(),
                    industry=(row.get("industry") or "").strip(),
                    description=(row.get("description") or "").strip(),
                )

        if not assets:
            raise AssetCatalogError("Asset catalog contains no assets")
        return assets

    def all(self) -> tuple[AssetDefinition, ...]:
        return tuple(self._assets.values())

    def ids(self) -> tuple[str, ...]:
        return tuple(self._assets.keys())

    def get(self, stock_id: str) -> AssetDefinition:
        try:
            return self._assets[stock_id]
        except KeyError as exc:
            raise AssetNotFoundError(stock_id) from exc

    def __len__(self) -> int:
        return len(self._assets)
