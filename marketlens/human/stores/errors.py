class StoreSessionNotFoundError(LookupError):
    pass


class StoreIdempotencyConflictError(ValueError):
    pass


class StoreDecisionAlreadySubmittedError(ValueError):
    pass


class StoreRoundAlreadyCompletedError(ValueError):
    pass


class StoreWrongExperimentStepError(ValueError):
    pass
