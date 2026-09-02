import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getMarketOverview,
} from "../api/participantApi";

import { CommunityPostCard } from "./CommunityPostCard";
import { MarketOverview } from "./MarketOverview";
import { MarketTickerStrip } from "./MarketTickerStrip";
import { PortfolioSnapshotCard } from "./PortfolioSnapshotCard";

import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantMarketOverviewRead,
  ParticipantViewState,
  PortfolioRead,
} from "../types/participant";

interface MarketContextProps {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  informationUpdate?: ParticipantInformationUpdateRead | null;
  portfolio?: PortfolioRead | null;
  portfolioLoading?: boolean;
  onMarketOverviewLoaded?: (
    overview: ParticipantMarketOverviewRead,
  ) => void;
}

interface OverviewState {
  key: string;
  overview: ParticipantMarketOverviewRead | null;
  error: string | null;
}

export function MarketContext({
  view,
  background,
  informationUpdate = null,
  portfolio,
  portfolioLoading = false,
  onMarketOverviewLoaded,
}: MarketContextProps) {
  const [overviewState, setOverviewState] =
    useState<OverviewState | null>(null);

  const overviewKey = useMemo(() => {
    if (
      !background ||
      background.current_date !== view.current_date
    ) {
      return null;
    }

    return `${view.session_id}:${view.current_date}`;
  }, [
    background,
    view.current_date,
    view.session_id,
  ]);

  useEffect(() => {
    if (!overviewKey) {
      return;
    }

    let cancelled = false;

    void getMarketOverview(view.session_id)
      .then((payload) => {
        if (cancelled) {
          return;
        }

        if (payload.current_date !== view.current_date) {
          setOverviewState({
            key: overviewKey,
            overview: null,
            error:
              "Market overview date does not match the current study period.",
          });
          return;
        }

        setOverviewState({
          key: overviewKey,
          overview: payload,
          error: null,
        });

        onMarketOverviewLoaded?.(
          payload
        );
      })
      .catch((caught) => {
        if (cancelled) {
          return;
        }

        setOverviewState({
          key: overviewKey,
          overview: null,
          error:
            caught instanceof Error
              ? caught.message
              : "Unable to load the market overview.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [
    onMarketOverviewLoaded,
    overviewKey,
    view.current_date,
    view.session_id,
  ]);

  const currentOverviewState =
    overviewKey &&
    overviewState?.key === overviewKey
      ? overviewState
      : null;

  const marketOverview =
    currentOverviewState?.overview ?? null;

  const marketOverviewError =
    currentOverviewState?.error ?? null;

  const marketOverviewLoading =
    overviewKey !== null &&
    currentOverviewState === null;

  const showPortfolio =
    portfolio !== undefined ||
    portfolioLoading;

  return (
    <div className="market-context market-context--terminal">
      {marketOverview && (
        <MarketTickerStrip
          overview={marketOverview}
          targetStockId={view.assessment_target_stock_id}
        />
      )}

      <div
        className={`terminal-dashboard-top ${
          showPortfolio
            ? ""
            : "terminal-dashboard-top--market-only"
        }`}
      >
        {showPortfolio && (
          <PortfolioSnapshotCard
            portfolio={portfolio ?? null}
            loading={portfolioLoading}
          />
        )}

        <div className="terminal-dashboard-market">
          {marketOverviewLoading && (
            <section className="panel terminal-market-loading">
              <span className="eyebrow">Market data</span>
              <h2>Market Overview</h2>
              <p className="empty-copy">
                Loading participant-visible prices…
              </p>
              <div className="loading-line" />
            </section>
          )}

          {!marketOverviewLoading &&
            marketOverviewError && (
              <section className="panel terminal-market-loading">
                <span className="eyebrow">Market data</span>
                <h2>Market Overview</h2>
                <p className="error-copy">
                  {marketOverviewError}
                </p>
              </section>
            )}

          {marketOverview && (
            <MarketOverview
              overview={marketOverview}
              targetStockId={
                view.assessment_target_stock_id
              }
            />
          )}
        </div>
      </div>

      {informationUpdate && (
        <section className="panel terminal-market-update">
          <div className="terminal-update-marker">
            Market update
          </div>

          <div className="terminal-market-update__body">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  New market information
                </span>
                <h2>
                  {informationUpdate.headline}
                </h2>
              </div>

              <span className="source-badge">
                {informationUpdate.source_label}
              </span>
            </div>

            <p className="source-descriptor">
              {informationUpdate.source_descriptor}
            </p>

            <p className="information-body">
              {informationUpdate.body}
            </p>
          </div>
        </section>
      )}

      {background ? (
        <div className="terminal-information-layout">
          <section className="panel terminal-community-panel">
            <div className="terminal-card-heading">
              <div>
                <span className="eyebrow">Community</span>
                <h2>Market Discussion</h2>
              </div>

              <span className="count-badge">
                {background.forum_posts.length}
              </span>
            </div>

            {background.forum_posts.length > 0 ? (
              <div className="terminal-community-feed">
                {background.forum_posts.map((post) => (
                  <CommunityPostCard
                    key={post.post_id}
                    post={post}
                  />
                ))}
              </div>
            ) : (
              <p className="empty-copy">
                No community posts are available for this period.
              </p>
            )}
          </section>

          <section className="panel terminal-news-panel">
            <div className="terminal-card-heading">
              <div>
                <span className="eyebrow">News</span>
                <h2>Market News</h2>
              </div>

              <span className="count-badge">
                {background.natural_news.length}
              </span>
            </div>

            {background.natural_news.length > 0 ? (
              <div className="terminal-news-feed">
                {background.natural_news.map(
                  (item, index) => (
                    <article
                      className="terminal-news-item"
                      key={`${background.current_date}-${index}`}
                    >
                      <span>
                        {String(index + 1).padStart(
                          2,
                          "0",
                        )}
                      </span>

                      <p>{item}</p>
                    </article>
                  ),
                )}
              </div>
            ) : (
              <p className="empty-copy">
                No natural-news items are available for this period.
              </p>
            )}
          </section>
        </div>
      ) : (
        <section className="panel">
          <p className="empty-copy">
            Market information will appear after it has been delivered
            by the study server.
          </p>
        </section>
      )}
    </div>
  );
}
