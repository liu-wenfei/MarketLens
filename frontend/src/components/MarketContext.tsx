import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantViewState,
} from "../types/participant";

interface MarketContextProps {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  informationUpdate?: ParticipantInformationUpdateRead | null;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MarketContext({
  view,
  background,
  informationUpdate = null,
}: MarketContextProps) {
  return (
    <div className="market-context">
      <section className="panel panel--market-summary">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Market environment</span>
            <h2>{view.assessment_target_stock_id}</h2>
          </div>

          <span
            className={`market-pill ${
              view.market.market_open
                ? "market-pill--open"
                : "market-pill--closed"
            }`}
          >
            {view.market.market_open ? "Market open" : "Market closed"}
          </span>
        </div>

        {!view.market.market_open && (
          <div className="market-closure">
            <strong>Trading is currently unavailable.</strong>
            <span>
              {view.market.next_trading_date
                ? ` The next trading date is ${view.market.next_trading_date}.`
                : ""}
            </span>
          </div>
        )}
      </section>

      {informationUpdate && (
        <section className="panel information-update-card">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">New market information</span>
              <h2>{informationUpdate.headline}</h2>
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
        </section>
      )}

      {background ? (
        <div className="market-grid">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Natural news</span>
                <h2>Market news</h2>
              </div>
              <span className="count-badge">
                {background.natural_news.length}
              </span>
            </div>

            {background.natural_news.length > 0 ? (
              <div className="news-list">
                {background.natural_news.map((item, index) => (
                  <article
                    className="news-item"
                    key={`${background.current_date}-${index}`}
                  >
                    <span className="news-index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <p>{item}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-copy">
                No natural-news items are available for this market period.
              </p>
            )}
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Community</span>
                <h2>Market discussion</h2>
              </div>
              <span className="count-badge">
                {background.forum_posts.length}
              </span>
            </div>

            {background.forum_posts.length > 0 ? (
              <div className="community-list">
                {background.forum_posts.map((post) => (
                  <article
                    className="community-post"
                    key={post.post_id}
                  >
                    <div className="community-post__meta">
                      <span className="source-badge">
                        {post.source_label}
                      </span>
                      <time>{formatTimestamp(post.created_at)}</time>
                    </div>

                    <p>{post.display_text}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-copy">
                No community posts are available for this market period.
              </p>
            )}
          </section>
        </div>
      ) : (
        <section className="panel">
          <p className="empty-copy">
            Market information will appear here once it has been delivered
            by the study server.
          </p>
        </section>
      )}
    </div>
  );
}
