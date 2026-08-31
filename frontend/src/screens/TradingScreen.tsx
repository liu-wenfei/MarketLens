import { useCallback, useEffect, useMemo, useState } from "react";

import {
  completeRound,
  createRequestId,
  getPortfolio,
  previewPortfolioOrder,
  submitPortfolioOrder,
} from "../api/participantApi";
import { MarketContext } from "../components/MarketContext";
import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantViewState,
  PortfolioAction,
  PortfolioOrderPreviewRead,
  PortfolioRead,
  PortfolioTransactionRead,
} from "../types/participant";

interface Props {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  informationUpdate: ParticipantInformationUpdateRead | null;
  onChanged: () => Promise<void>;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function TradingScreen({
  view,
  background,
  informationUpdate,
  onChanged,
}: Props) {
  const [portfolio, setPortfolio] = useState<PortfolioRead | null>(null);
  const [stockId, setStockId] = useState(
    view.assessment_target_stock_id,
  );
  const [action, setAction] = useState<PortfolioAction>("BUY");
  const [amount, setAmount] = useState("");
  const [preview, setPreview] =
    useState<PortfolioOrderPreviewRead | null>(null);
  const [lastTrade, setLastTrade] =
    useState<PortfolioTransactionRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [portfolioBusy, setPortfolioBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPortfolio = useCallback(async () => {
    if (!view.allowed_actions.view_portfolio) {
      setPortfolio(null);
      return;
    }

    setPortfolioBusy(true);

    try {
      setPortfolio(await getPortfolio(view.session_id));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load the portfolio.",
      );
    } finally {
      setPortfolioBusy(false);
    }
  }, [view.allowed_actions.view_portfolio, view.session_id]);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  const stockOptions = useMemo(() => {
    const values = new Set<string>([
      view.assessment_target_stock_id,
    ]);

    portfolio?.holdings.forEach((holding) => {
      values.add(holding.stock_id);
    });

    return Array.from(values);
  }, [portfolio, view.assessment_target_stock_id]);

  function invalidatePreview() {
    setPreview(null);
    setLastTrade(null);
  }

  async function handlePreview() {
    const numericAmount = Number(amount);

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError("Enter a positive trade amount.");
      return;
    }

    setBusy(true);
    setError(null);
    setLastTrade(null);

    try {
      const result = await previewPortfolioOrder(
        view.session_id,
        {
          step: view.current_step_assertion,
          stock_id: stockId,
          action,
          amount: numericAmount,
        },
      );

      setPreview(result);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to preview the order.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!preview?.valid) {
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const transaction = await submitPortfolioOrder(
        view.session_id,
        {
          request_id: createRequestId(),
          step: view.current_step_assertion,
          stock_id: preview.stock_id,
          action: preview.action,
          amount: preview.requested_amount,
        },
      );

      setLastTrade(transaction);
      setPreview(null);
      setAmount("");
      await loadPortfolio();
      await onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to submit the order.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleContinue() {
    setBusy(true);
    setError(null);

    try {
      await completeRound(
        view.session_id,
        createRequestId(),
        view.current_step_assertion,
      );
      await onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to complete the market period.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen-shell">
      <div className="screen-title">
        <span className="eyebrow">Market environment</span>
        <h1>Portfolio & Trading</h1>
        <p>
          Review your simulated portfolio and decide whether you
          want to place a trade during this market period.
        </p>
      </div>

      <MarketContext
        view={view}
        background={background}
        informationUpdate={informationUpdate}
      />

      <section className="panel portfolio-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Your portfolio</span>
            <h2>Portfolio summary</h2>
          </div>
          {portfolio?.price_date && (
            <span className="small-meta">
              Prices: {portfolio.price_date}
            </span>
          )}
        </div>

        {portfolioBusy && (
          <p className="empty-copy">Loading portfolio…</p>
        )}

        {portfolio && (
          <>
            <div className="portfolio-summary">
              <div>
                <span>Cash</span>
                <strong>{formatNumber(portfolio.cash)}</strong>
              </div>
              <div>
                <span>Total portfolio value</span>
                <strong>{formatNumber(portfolio.total_value)}</strong>
              </div>
              <div>
                <span>Starting cash</span>
                <strong>{formatNumber(portfolio.initial_cash)}</strong>
              </div>
            </div>

            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Quantity</th>
                    <th>Current price</th>
                    <th>Market value</th>
                    <th>Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.holdings.map((holding) => (
                    <tr key={holding.stock_id}>
                      <td>
                        <strong>{holding.stock_id}</strong>
                        <span>{holding.name}</span>
                      </td>
                      <td>{holding.quantity}</td>
                      <td>{formatNumber(holding.current_price)}</td>
                      <td>{formatNumber(holding.market_value)}</td>
                      <td>
                        {formatNumber(
                          holding.portfolio_weight * 100,
                        )}
                        %
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {!view.market.market_open && (
        <section className="panel market-closed-panel">
          <span className="eyebrow">Trading status</span>
          <h2>Market Closed</h2>

          {view.market.closure_start_date &&
          view.market.closure_end_date &&
          view.market.next_trading_date ? (
            <p>
              Trading is temporarily unavailable due to a scheduled
              market closure. The closure runs from{" "}
              <strong>{view.market.closure_start_date}</strong> through{" "}
              <strong>{view.market.closure_end_date}</strong>. The next
              trading date is{" "}
              <strong>{view.market.next_trading_date}</strong>.
            </p>
          ) : (
            <p>
              Trading is currently unavailable for this market period.
              You may still review the market information and your
              simulated portfolio.
            </p>
          )}
        </section>
      )}

      {view.allowed_actions.preview_trade && (
        <section className="panel trading-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Optional action</span>
              <h2>Place a simulated trade</h2>
            </div>
          </div>

          <div className="trade-grid">
            <div className="form-section">
              <label htmlFor="stock">Asset</label>
              <select
                id="stock"
                value={stockId}
                onChange={(event) => {
                  setStockId(event.target.value);
                  invalidatePreview();
                }}
              >
                {stockOptions.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-section">
              <span className="field-label">Action</span>
              <div className="trade-actions">
                {(["BUY", "SELL"] as PortfolioAction[]).map(
                  (value) => (
                    <button
                      type="button"
                      key={value}
                      aria-pressed={action === value}
                      className={`trade-action ${
                        action === value
                          ? "trade-action--selected"
                          : ""
                      }`}
                      onClick={() => {
                        setAction(value);
                        invalidatePreview();
                      }}
                    >
                      {value}
                    </button>
                  ),
                )}
              </div>
            </div>

            <div className="form-section">
              <label htmlFor="amount">Trade amount</label>
              <input
                id="amount"
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(event) => {
                  setAmount(event.target.value);
                  invalidatePreview();
                }}
                placeholder="Enter amount"
              />
            </div>
          </div>

          <button
            className="secondary-button"
            type="button"
            disabled={busy || !view.allowed_actions.preview_trade}
            onClick={() => void handlePreview()}
          >
            {busy ? "Checking…" : "Preview trade"}
          </button>

          {preview && (
            <div
              className={`preview-card ${
                preview.valid
                  ? "preview-card--valid"
                  : "preview-card--invalid"
              }`}
            >
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Server preview</span>
                  <h3>
                    {preview.action} {preview.stock_id}
                  </h3>
                </div>
                <strong>
                  {preview.valid ? "Valid" : "Unavailable"}
                </strong>
              </div>

              <div className="preview-grid">
                <div>
                  <span>Settlement price</span>
                  <strong>
                    {formatNumber(preview.settlement_price)}
                  </strong>
                </div>
                <div>
                  <span>Executable units</span>
                  <strong>{preview.executable_units}</strong>
                </div>
                <div>
                  <span>Executed notional</span>
                  <strong>
                    {formatNumber(preview.executed_notional)}
                  </strong>
                </div>
                <div>
                  <span>Fee</span>
                  <strong>{formatNumber(preview.fee)}</strong>
                </div>
                <div>
                  <span>Cash after</span>
                  <strong>
                    {formatNumber(preview.cash_after)}
                  </strong>
                </div>
                <div>
                  <span>Holding after</span>
                  <strong>{preview.holding_after}</strong>
                </div>
              </div>

              {!preview.valid && (
                <p className="preview-reason">
                  The server did not authorise this trade:{" "}
                  {preview.reason_code}.
                  {preview.maximum_valid_amount !== null
                    ? ` Maximum valid amount: ${formatNumber(
                        preview.maximum_valid_amount,
                      )}.`
                    : ""}
                </p>
              )}

              {preview.valid && (
                <button
                  type="button"
                  className="primary-button"
                  disabled={
                    busy || !view.allowed_actions.submit_trade
                  }
                  onClick={() => void handleConfirm()}
                >
                  {busy ? "Submitting…" : "Confirm trade"}
                </button>
              )}
            </div>
          )}

          {lastTrade && (
            <div className="success-banner">
              Trade recorded: {lastTrade.action}{" "}
              {lastTrade.executed_units} units of{" "}
              {lastTrade.stock_id} at{" "}
              {formatNumber(lastTrade.settlement_price)}.
            </div>
          )}
        </section>
      )}

      <section className="panel period-complete-panel">
        <div>
          <span className="eyebrow">Finish this market period</span>
          <h2>Ready to continue?</h2>
          <p>
            Trading is optional. Continue when you have finished
            reviewing this market period.
          </p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          type="button"
          className="primary-button"
          disabled={
            busy || !view.allowed_actions.complete_round
          }
          onClick={() => void handleContinue()}
        >
          {busy
            ? "Completing period…"
            : view.period_number === view.period_count
              ? "Complete final market period"
              : "Continue to next market period"}
        </button>
      </section>
    </main>
  );
}
