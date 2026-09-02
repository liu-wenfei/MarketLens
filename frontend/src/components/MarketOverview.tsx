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

function chartPoints(
  asset: ParticipantMarketAssetRead,
): string {
  const values = asset.price_history.map(
    (point) => point.close,
  );

  if (values.length < 2) {
    return "";
  }

  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum;

  return values
    .map((value, index) => {
      const x =
        (index / (values.length - 1)) * 96 + 2;

      const y =
        range === 0
          ? 28
          : 50 - ((value - minimum) / range) * 44;

      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function MiniPriceChart({
  asset,
}: {
  asset: ParticipantMarketAssetRead;
}) {
  const points = chartPoints(asset);
  const trend = trendClass(asset);

  if (asset.price_history.length <= 1) {
    return (
      <svg
        className={`terminal-price-chart ${trend}`}
        viewBox="0 0 100 56"
        role="img"
        aria-label={`${asset.stock_id} visible price history`}
      >
        <line
          className="terminal-price-chart__grid"
          x1="2"
          x2="98"
          y1="28"
          y2="28"
        />
        <circle
          className="terminal-price-chart__point"
          cx="50"
          cy="28"
          r="2.5"
        />
      </svg>
    );
  }

  return (
    <svg
      className={`terminal-price-chart ${trend}`}
      viewBox="0 0 100 56"
      role="img"
      aria-label={`${asset.stock_id} visible price history`}
    >
      <line
        className="terminal-price-chart__grid"
        x1="2"
        x2="98"
        y1="14"
        y2="14"
      />
      <line
        className="terminal-price-chart__grid"
        x1="2"
        x2="98"
        y1="28"
        y2="28"
      />
      <line
        className="terminal-price-chart__grid"
        x1="2"
        x2="98"
        y1="42"
        y2="42"
      />

      <polyline
        className="terminal-price-chart__line"
        points={points}
        fill="none"
      />
    </svg>
  );
}

export function MarketOverview({
  overview,
  targetStockId,
}: Props) {
  return (
    <section className="panel terminal-market-overview">
      <div className="terminal-card-heading">
        <div>
          <span className="eyebrow">Market data</span>
          <h2>Market Overview</h2>
        </div>

        <span className="terminal-asof">
          As of {overview.price_date}
        </span>
      </div>

      <div className="terminal-market-grid">
        {overview.assets.map((asset) => {
          const isTarget =
            asset.stock_id === targetStockId;

          const firstPoint = asset.price_history[0];
          const lastPoint =
            asset.price_history[
              asset.price_history.length - 1
            ];

          return (
            <article
              className={`terminal-quote-card ${
                isTarget
                  ? "terminal-quote-card--target"
                  : ""
              }`}
              key={asset.stock_id}
            >
              <div className="terminal-quote-card__top">
                <div className="terminal-quote-card__identity">
                  <span className="terminal-ticker-icon">
                    {asset.stock_id.slice(0, 2)}
                  </span>

                  <div>
                    <strong>{asset.stock_id}</strong>
                    <span title={asset.display_name}>
                        {asset.short_display_name}
                      </span>
                  </div>
                </div>

                {isTarget && (
                  <span className="terminal-target-badge">
                    Assessment
                  </span>
                )}
              </div>

              <div className="terminal-quote-card__quote">
                <strong>
                  {formatPrice(asset.current_price)}
                </strong>

                <span className={trendClass(asset)}>
                  {formatChange(
                    asset.change_from_previous_visible_pct,
                  )}
                </span>
              </div>

              <MiniPriceChart asset={asset} />

              <div className="terminal-quote-card__footer">
                <span>
                  {firstPoint?.participant_date ?? "—"}
                </span>
                <span>
                  {asset.price_history.length} periods
                </span>
                <span>
                  {lastPoint?.participant_date ?? "—"}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
