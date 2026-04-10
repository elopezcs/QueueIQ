class TranscriptionError(Exception):
    """Base error for transcription failures."""


class TranscriptionFeatureDisabledError(TranscriptionError):
    pass


class TranscriptionValidationError(TranscriptionError):
    pass


class TranscriptionProviderUnavailableError(TranscriptionError):
    pass


class TranscriptionProviderFailureError(TranscriptionError):
    pass
