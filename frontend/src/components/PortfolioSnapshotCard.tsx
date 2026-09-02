import type {
  PortfolioRead,
} from "../types/participant";

interface Props {
  portfolio: PortfolioRead | null;
  loading: boolean;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function movementClass(
  value: number | null,
): string {
  if (value === null || value === 0) {
    return "market-trend--flat";
  }

  return value > 0
    ? "market-trend--up"
    : "market-trend--down";
}

function formatSignedNumber(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  const absolute = formatNumber(
    Math.abs(value),
  );

  if (value > 0) {
    return `+${absolute}`;
  }

  if (value < 0) {
    return `-${absolute}`;
  }

  return absolute;
}

function formatSignedPercent(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  const absolute = Math.abs(
    value
  ).toFixed(2);

  if (value > 0) {
    return `+${absolute}%`;
  }

  if (value < 0) {
    return `-${absolute}%`;
  }

  return `${absolute}%`;
}


export function PortfolioSnapshotCard({
  portfolio,
  loading,
}: Props) {
  if (loading && !portfolio) {
    return (
      <section className="panel terminal-portfolio-card">
        <span className="eyebrow">Your portfolio</span>
        <h2>Portfolio</h2>
        <p className="empty-copy">Loading portfolio…</p>
      </section>
    );
  }

  if (!portfolio) {
    return null;
  }

  const invested = Math.max(
    0,
    portfolio.total_value - portfolio.cash,
  );

  return (
    <section className="panel terminal-portfolio-card">
      <div className="terminal-card-heading">
        <div>
          <span className="eyebrow">Your portfolio</span>
          <h2>Portfolio</h2>
        </div>

        {portfolio.price_date && (
          <span className="terminal-asof">
            {portfolio.price_date}
          </span>
        )}
      </div>

      <div className="terminal-portfolio-metrics">
        <div className="terminal-primary-metric">
          <span>Total value</span>
          <strong>{formatNumber(portfolio.total_value)}</strong>
        </div>

        <div>
          <span>Period P/L</span>
          <strong
            className={movementClass(
              portfolio.period_pnl,
            )}
          >
            {formatSignedNumber(
              portfolio.period_pnl,
            )}
          </strong>
        </div>

        <div>
          <span>Period P/L %</span>
          <strong
            className={movementClass(
              portfolio.period_pnl_pct,
            )}
          >
            {formatSignedPercent(
              portfolio.period_pnl_pct,
            )}
          </strong>
        </div>

        <div>
          <span>Cash</span>
          <strong>{formatNumber(portfolio.cash)}</strong>
        </div>

        <div>
          <span>Invested</span>
          <strong>{formatNumber(invested)}</strong>
        </div>
      </div>

      <div className="terminal-holdings-heading">
        <strong>Holdings</strong>
        <span>{portfolio.holdings.length}</span>
      </div>

      {portfolio.holdings.length > 0 ? (
        <div className="terminal-holdings">
          {portfolio.holdings.map((holding) => (
            <div
              className="terminal-holding-row"
              key={holding.stock_id}
            >
              <div>
                <strong>{holding.stock_id}</strong>
                <span title={holding.name}>
                    {holding.short_name ?? holding.name}
                  </span>
              </div>

              <div className="terminal-holding-row__numbers">
                <strong>{holding.quantity}</strong>
                <span>
                  {formatNumber(holding.market_value)}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="terminal-empty-holdings">
          No risky-asset holdings.
        </p>
      )}
    </section>
  );
}
