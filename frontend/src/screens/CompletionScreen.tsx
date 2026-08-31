export function CompletionScreen() {
  return (
    <main className="screen-shell screen-shell--focused">
      <section className="task-card completion-card">
        <div className="completion-mark">✓</div>
        <span className="eyebrow">Session complete</span>
        <h1>Thank you</h1>
        <p className="lead-copy">
          Your MarketLens session has been completed and your responses
          have been recorded.
        </p>
        <p>You may now close this window.</p>
      </section>
    </main>
  );
}
