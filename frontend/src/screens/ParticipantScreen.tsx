import { StudyHeader } from "../components/StudyHeader";
import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantViewState,
} from "../types/participant";
import { AssessmentScreen } from "./AssessmentScreen";
import { CompletionScreen } from "./CompletionScreen";
import { DebriefScreen } from "./DebriefScreen";
import { FeedbackScreen } from "./FeedbackScreen";
import { InformationUpdateScreen } from "./InformationUpdateScreen";
import { MarketInformationScreen } from "./MarketInformationScreen";
import { TradingScreen } from "./TradingScreen";

interface Props {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  informationUpdate: ParticipantInformationUpdateRead | null;
  onBackgroundDelivered: (
    background: ParticipantBackgroundRead,
  ) => Promise<void>;
  onInformationUpdateDelivered: (
    update: ParticipantInformationUpdateRead,
  ) => Promise<void>;
  onMutationComplete: () => Promise<void>;
}

export function ParticipantScreen({
  view,
  background,
  informationUpdate,
  onBackgroundDelivered,
  onInformationUpdateDelivered,
  onMutationComplete,
}: Props) {
  let content;

  switch (view.required_action) {
    case "LOAD_MARKET_INFORMATION":
      content = (
        <MarketInformationScreen
          view={view}
          onDelivered={onBackgroundDelivered}
        />
      );
      break;

    case "LOAD_INFORMATION_UPDATE":
      content = (
        <InformationUpdateScreen
          view={view}
          background={background}
          onDelivered={onInformationUpdateDelivered}
        />
      );
      break;

    case "SUBMIT_ASSESSMENT":
      content = (
        <AssessmentScreen
          view={view}
          background={background}
          informationUpdate={informationUpdate}
          onSubmitted={onMutationComplete}
        />
      );
      break;

    case "ROUND_ACTIVE":
      content = (
        <TradingScreen
          view={view}
          background={background}
          informationUpdate={informationUpdate}
          onChanged={onMutationComplete}
        />
      );
      break;

    case "VIEW_FEEDBACK":
      content = (
        <FeedbackScreen
          view={view}
          onContinued={onMutationComplete}
        />
      );
      break;

    case "VIEW_DEBRIEF":
      content = (
        <DebriefScreen
          sessionId={view.session_id}
          onCompleted={onMutationComplete}
        />
      );
      break;

    case "COMPLETED":
      content = <CompletionScreen />;
      break;
  }

  return (
    <div className="participant-app">
      <StudyHeader view={view} />
      {content}
    </div>
  );
}
