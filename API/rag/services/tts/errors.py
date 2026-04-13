class TTSError(Exception):
    """Base error for text-to-speech failures."""


class TTSFeatureDisabledError(TTSError):
    pass


class TTSValidationError(TTSError):
    pass


class TTSProviderUnavailableError(TTSError):
    pass


class TTSProviderFailureError(TTSError):
    pass
