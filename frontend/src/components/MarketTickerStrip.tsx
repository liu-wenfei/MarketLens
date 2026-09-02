import type {
  ParticipantMarketAssetRead,
  ParticipantMarketOverviewRead,
} from "../types/participant";

interface Props {
  overview: ParticipantMarketOverviewRead;
  targetStockId: string;
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatChange(value: number | null): string {
  if (value === null) {
    return "—";
  }

  const normalised = Math.abs(value) < 0.005 ? 0 : value;

  if (normalised === 0) {
    return "0.00%";
  }

  return `${normalised > 0 ? "↑" : "↓"} ${Math.abs(
    normalised,
  ).toFixed(2)}%`;
}

function trendClass(
  asset: ParticipantMarketAssetRead,
): string {
  const value = asset.change_from_previous_visible_pct;

  if (value === null || Math.abs(value) < 0.005) {
    return "market-trend--flat";
  }

  return value > 0
    ? "market-trend--up"
    : "market-trend--down";
}

export function MarketTickerStrip({
  overview,
  targetStockId,
}: Props) {
  return (
    <div
      className="market-terminal-ticker"
      aria-label="Participant-visible market prices"
    >
      {overview.assets.map((asset) => (
        <div
          className={`market-terminal-ticker__item ${
            asset.stock_id === targetStockId
              ? "market-terminal-ticker__item--target"
              : ""
          }`}
          key={asset.stock_id}
          title={asset.display_name}
        >
          <strong>{asset.stock_id}</strong>

          <span className="market-terminal-ticker__price">
            {formatPrice(asset.current_price)}
          </span>

          <span
            className={`market-terminal-ticker__change ${trendClass(
              asset,
            )}`}
          >
            {formatChange(
              asset.change_from_previous_visible_pct,
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
