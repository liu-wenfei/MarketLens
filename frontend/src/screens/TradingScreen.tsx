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
  ParticipantMarketOverviewRead,
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
  const [marketOverview, setMarketOverview] =
    useState<ParticipantMarketOverviewRead | null>(null);
  const [stockId, setStockId] = useState("");
  const [action, setAction] = useState<PortfolioAction>("BUY");
  const [amount, setAmount] = useState("");
  const [preview, setPreview] =
    useState<PortfolioOrderPreviewRead | null>(null);
  const [lastTrade, setLastTrade] =
    useState<PortfolioTransactionRead | null>(null);
  const [showNoTradeConfirm, setShowNoTradeConfirm] =
    useState(false);
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

  const handleMarketOverviewLoaded = useCallback(
    (
      overview: ParticipantMarketOverviewRead,
    ) => {
      setMarketOverview(overview);
    },
    [],
  );

  const stockOptions = useMemo(
    () => marketOverview?.assets ?? [],
    [marketOverview],
  );

  function invalidatePreview() {
    setPreview(null);
    setShowNoTradeConfirm(false);
  }

  async function handlePreview() {
    if (!stockId) {
      setError(
        "Select an asset before previewing an order.",
      );
      return;
    }

    const numericAmount = Number(amount);

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError("Enter a positive trade amount.");
      return;
    }

    setBusy(true);
    setError(null);
    setShowNoTradeConfirm(false);

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
      setShowNoTradeConfirm(false);
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

  async function handleContinue(
    confirmedNoTrade = false,
  ) {
    if (!lastTrade && !preview?.valid && !confirmedNoTrade) {
      setShowNoTradeConfirm(true);
      return;
    }

    setBusy(true);
    setError(null);
    setShowNoTradeConfirm(false);

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
    <main className="screen-shell trading-screen">
      <div className="screen-title">
        <span className="eyebrow">Decide · Portfolio action</span>
        <h1>Portfolio & Trading</h1>
        <p>
          Trading is optional. Review your simulated portfolio and
          decide whether you want to change it during this market
          period.
        </p>

      </div>

      <MarketContext
        view={view}
        background={background}
        informationUpdate={informationUpdate}
        portfolio={portfolio}
        portfolioLoading={portfolioBusy}
        onMarketOverviewLoaded={
          handleMarketOverviewLoaded
        }
      />

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
              <span className="eyebrow">Optional portfolio action</span>
              <h2>Choose whether to change your portfolio</h2>
            </div>
          </div>

          <p className="interaction-note">
            You may preview an order before deciding. Previewing an
            order does not execute it or change your portfolio.
          </p>

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
                disabled={stockOptions.length === 0}
              >
                <option value="" disabled>
                  {stockOptions.length === 0
                    ? "Loading assets…"
                    : "Select an asset"}
                </option>

                {stockOptions.map((asset) => (
                  <option
                    value={asset.stock_id}
                    key={asset.stock_id}
                  >
                    {asset.stock_id} — {asset.display_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-section">
              <span className="field-label">Portfolio action</span>
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
              <label htmlFor="amount">Order amount</label>
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
                placeholder="Enter simulated currency amount"
              />
            </div>
          </div>

          <button
            className="secondary-button"
            type="button"
            disabled={busy || !view.allowed_actions.preview_trade}
            onClick={() => void handlePreview()}
          >
            {busy ? "Checking…" : "Preview Order"}
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
                  <span className="eyebrow">Order preview</span>
                  <h3>
                    {preview.action} {preview.stock_id}
                  </h3>
                </div>
                <strong>
                  {preview.valid ? "NOT EXECUTED" : "Unavailable"}
                </strong>
              </div>

              {preview.valid && (
                <p className="preview-state-note">
                  <strong>Preview only.</strong> Your portfolio has not
                  changed yet. Confirm the order below if you want to
                  execute this simulated trade.
                </p>
              )}

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
                <div className="preview-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={
                      busy || !view.allowed_actions.submit_trade
                    }
                    onClick={() => void handleConfirm()}
                  >
                    {busy
                      ? "Executing trade…"
                      : "Confirm & Execute Trade"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => setPreview(null)}
                  >
                    Edit Order
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => {
                      setPreview(null);
                      setAmount("");
                    }}
                  >
                    Discard Preview
                  </button>
                </div>
              )}
            </div>
          )}

          {lastTrade && (
            <div className="preview-card execution-receipt">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Trade executed</span>
                  <h3>
                    {lastTrade.action} {lastTrade.executed_units}{" "}
                    {lastTrade.stock_id}
                  </h3>
                </div>
                <strong>RECORDED</strong>
              </div>

              <div className="preview-grid">
                <div>
                  <span>Requested amount</span>
                  <strong>
                    {formatNumber(lastTrade.requested_amount)}
                  </strong>
                </div>
                <div>
                  <span>Executed units</span>
                  <strong>{lastTrade.executed_units}</strong>
                </div>
                <div>
                  <span>Settlement price</span>
                  <strong>
                    {formatNumber(lastTrade.settlement_price)}
                  </strong>
                </div>
                <div>
                  <span>Executed notional</span>
                  <strong>
                    {formatNumber(lastTrade.executed_notional)}
                  </strong>
                </div>
                <div>
                  <span>Cash after trade</span>
                  <strong>
                    {formatNumber(lastTrade.cash_after)}
                  </strong>
                </div>
                <div>
                  <span>Holding after trade</span>
                  <strong>{lastTrade.holding_after}</strong>
                </div>
              </div>

              <p className="interaction-note">
                This transaction has been executed and recorded in
                your simulated portfolio.
              </p>
            </div>
          )}
        </section>
      )}

      {showNoTradeConfirm && !lastTrade && !preview?.valid && (
        <div className="decision-modal-backdrop">
          <div
            className="decision-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="no-trade-confirm-title"
            aria-describedby="no-trade-confirm-copy"
          >
            <span className="eyebrow">Portfolio decision</span>
            <h2 id="no-trade-confirm-title">
              Confirm before continuing
            </h2>
            <p id="no-trade-confirm-copy">
              No trade has been confirmed in this interaction.
              If you continue now, this market period will
              finish without an additional portfolio trade.
            </p>

            <div className="preview-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => setShowNoTradeConfirm(false)}
              >
                Review Trading Options
              </button>

              <button
                type="button"
                className="primary-button"
                disabled={busy}
                onClick={() => void handleContinue(true)}
              >
                Continue Without Trading
              </button>
            </div>
          </div>
        </div>
      )}

      <section className="panel period-complete-panel">
        <div>
          <span className="eyebrow">Finish this market period</span>
          <h2>Ready to continue?</h2>
          <p>
            {preview?.valid
              ? "You have a previewed order that has not been executed. Confirm, edit or discard it before continuing."
              : lastTrade
                ? "Your confirmed trade has been recorded. Continue when you have finished reviewing this market period."
                : "Trading is optional. You may continue without changing your portfolio."}
          </p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          type="button"
          className="primary-button"
          disabled={
            busy ||
            !view.allowed_actions.complete_round ||
            Boolean(preview?.valid)
          }
          onClick={() => void handleContinue()}
        >
          {busy
            ? "Completing period…"
            : preview?.valid
              ? "Resolve Preview Before Continuing"
              : lastTrade
                ? view.period_number === view.period_count
                  ? "Complete Final Market Period"
                  : "Continue to Next Market Period"
                : view.period_number === view.period_count
                  ? "Complete Final Market Period"
                  : "Continue"}
        </button>
      </section>
    </main>
  );
}
