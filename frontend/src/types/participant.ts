export type DecisionAction = "BUY" | "HOLD" | "SELL";
export type PortfolioAction = "BUY" | "SELL";

export type ParticipantRequiredAction =
  | "LOAD_MARKET_INFORMATION"
  | "LOAD_INFORMATION_UPDATE"
  | "SUBMIT_ASSESSMENT"
  | "ROUND_ACTIVE"
  | "VIEW_FEEDBACK"
  | "VIEW_DEBRIEF"
  | "COMPLETED";

export type ParticipantAssessmentMode =
  | "PRE_UPDATE"
  | "POST_UPDATE"
  | "LATER";

export interface SessionRead {
  session_id: string;
  participant_id: string;
  created_at: string;
  current_step: number;
  current_date: string | null;
  experiment_status: string;
  completed: boolean;
}

export interface ParticipantAllowedActions {
  load_market_information: boolean;
  load_information_update: boolean;
  submit_assessment: boolean;
  view_portfolio: boolean;
  preview_trade: boolean;
  submit_trade: boolean;
  complete_round: boolean;
}

export interface ParticipantMarketView {
  market_open: boolean;
  market_status_reason: string;
  current_market_date: string | null;
  next_trading_date: string | null;
  closure_start_date: string | null;
  closure_end_date: string | null;
  market_state_date: string | null;
  trading_enabled_by_market: boolean;
}

export interface ParticipantHistoricalMarketPricePointRead {
  price_date: string;
  close: number;
}

export interface ParticipantMarketPricePointRead {
  participant_date: string;
  price_date: string;
  close: number;
}

export interface ParticipantMarketAssetRead {
  stock_id: string;
  display_name: string;
  short_display_name: string;
  current_price: number;
  previous_visible_close: number | null;
  change_from_previous_visible_pct: number | null;
  historical_price_context: ParticipantHistoricalMarketPricePointRead[];
  price_history: ParticipantMarketPricePointRead[];
}

export interface ParticipantMarketOverviewRead {
  session_id: string;
  current_date: string;
  price_date: string;
  assets: ParticipantMarketAssetRead[];
}

export interface ParticipantViewState {
  contract_version: string;
  session_id: string;
  current_step_assertion: number;
  period_number: number;
  period_count: number;
  current_date: string;
  experiment_status: string;
  completed: boolean;
  assessment_target_stock_id: string;
  required_action: ParticipantRequiredAction;
  assessment_mode: ParticipantAssessmentMode | null;
  market: ParticipantMarketView;
  allowed_actions: ParticipantAllowedActions;
}

export interface ParticipantForumPostRead {
  post_id: number;
  author_id: string;
  source_label: string;
  display_text: string;
  created_at: string;
}

export interface ParticipantBackgroundRead {
  session_id: string;
  current_date: string;
  natural_news: string[];
  forum_posts: ParticipantForumPostRead[];
}

export interface ParticipantInformationUpdateRead {
  session_id: string;
  current_date: string;
  headline: string;
  body: string;
  source_label: string;
  source_descriptor: string;
}

export interface ParticipantAssessmentCreate {
  request_id: string;
  action: DecisionAction;
  confidence: number;
  evidence_sources: string[];
  rationale: string | null;
}

export interface ParticipantAssessmentRead {
  assessment_id: string;
  session_id: string;
  request_id: string;
  assessment_target_stock_id: string;
  assessment_mode: ParticipantAssessmentMode;
  action: DecisionAction;
  confidence: number;
  evidence_sources: string[];
  rationale: string | null;
  submitted_at: string;
}

export interface PortfolioHoldingRead {
  stock_id: string;
  name: string;
  short_name: string | null;
  quantity: number;
  current_price: number;
  market_value: number;
  portfolio_weight: number;
}

export interface PortfolioRead {
  session_id: string;
  step: number;
  price_date: string | null;
  initial_cash: number;
  cash: number;
  total_value: number;
  period_pnl: number | null;
  period_pnl_pct: number | null;
  holdings: PortfolioHoldingRead[];
}

export interface PortfolioOrderPreviewCreate {
  step: number;
  stock_id: string;
  action: PortfolioAction;
  amount: number;
}

export interface PortfolioOrderCreate extends PortfolioOrderPreviewCreate {
  request_id: string;
}

export interface PortfolioOrderPreviewRead {
  session_id: string;
  step: number;
  price_date: string;
  stock_id: string;
  action: PortfolioAction;
  settlement_price: number;
  requested_amount: number;
  requested_units: number;
  executable_units: number;
  executed_notional: number;
  fee: number;
  cash_before: number;
  cash_after: number;
  holding_before: number;
  holding_after: number;
  portfolio_value_before: number;
  portfolio_value_after: number;
  weight_before: number;
  weight_after: number;
  valid: boolean;
  reason_code: string;
  maximum_valid_amount: number | null;
}

export interface PortfolioTransactionRead {
  transaction_id: string;
  session_id: string;
  request_id: string;
  step: number;
  stock_id: string;
  action: PortfolioAction;
  requested_amount: number;
  requested_units: number;
  executed_units: number;
  executed_notional: number;
  settlement_price: number;
  price_date: string;
  transaction_cost_bps: number;
  fee: number;
  cash_before: number;
  cash_after: number;
  holding_before: number;
  holding_after: number;
  portfolio_value_before: number;
  portfolio_value_after: number;
  weight_before: number;
  weight_after: number;
  submitted_at: string;
}

export interface ParticipantFeedbackRead {
  feedback_kind: string;
  reflection_stage: "early" | "mid_session" | "final";
  statistics: Record<string, unknown>;
  reflection: string;
}

export interface ParticipantJourneyJudgementRead {
  sequence_within_period: number;
  stock_id: string;
  action: string;
  confidence: number;
  evidence_sources: string[];
  rationale: string | null;
  submitted_at: string;
}

export interface ParticipantJourneyTransactionRead {
  sequence_within_period: number;
  transaction_id: string;
  stock_id: string;
  action: string;
  requested_amount: number | null;
  requested_units: number | null;
  executed_units: number;
  executed_notional: number;
  settlement_price: number;
  fee: number;
  cash_before: number;
  cash_after: number;
  holding_before: number;
  holding_after: number;
  submitted_at: string;
}

export interface ParticipantJourneyPortfolioSnapshotRead {
  cash: number;
  holdings: Record<string, number>;
  portfolio_value: number;
}

export interface ParticipantJourneyPeriodRead {
  period_number: number;
  agent_world_date: string;
  market_open: boolean;
  participant_trading_enabled: boolean;
  judgements: ParticipantJourneyJudgementRead[];
  transactions: ParticipantJourneyTransactionRead[];
  behaviour_summary: string;
  holding_changes: Record<string, number>;
  portfolio_end: ParticipantJourneyPortfolioSnapshotRead;
  period_pnl: number;
  cumulative_pnl: number;
  pnl_direction: string;
  feedback_boundary: string;
}

export interface ParticipantDecisionJourneyRead {
  journey_version: string;
  target_stock_id: string;
  initial_cash: number;
  initial_holdings: Record<string, number>;
  initial_portfolio_value: number;
  periods: ParticipantJourneyPeriodRead[];
}
