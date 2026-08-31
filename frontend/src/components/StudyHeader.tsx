import type { ParticipantViewState } from "../types/participant";

interface StudyHeaderProps {
  view: ParticipantViewState;
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function StudyHeader({ view }: StudyHeaderProps) {
  return (
    <header className="study-header">
      <div className="study-header__brand">
        <span className="study-header__mark">ML</span>
        <div>
          <strong>MarketLens</strong>
          <span>Financial simulation system</span>
        </div>
      </div>

      <div className="study-header__context">
        <div>
          <span className="context-label">Market period</span>
          <strong>
            {view.period_number} of {view.period_count}
          </strong>
        </div>

        <div>
          <span className="context-label">Market date</span>
          <strong>{formatDate(view.current_date)}</strong>
        </div>

        <div>
          <span className="context-label">Market status</span>
          <strong
            className={
              view.market.market_open
                ? "status-text status-text--open"
                : "status-text"
            }
          >
            {view.market.market_open ? "Open" : "Closed"}
          </strong>
        </div>
      </div>
    </header>
  );
}
