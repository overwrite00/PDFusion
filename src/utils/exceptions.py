class PDFusionError(Exception):
    """Errore applicativo generico di PDFusion."""


class FileLockedError(PDFusionError):
    """Il file PDF è aperto in un'altra applicazione."""


class InvalidPageRangeError(PDFusionError):
    """Range di pagine non valido."""


class EncryptedPDFError(PDFusionError):
    """Il PDF è protetto da password e non è stata fornita la password corretta."""


class UnsupportedFormatError(PDFusionError):
    """Il file non è un PDF valido o supportato."""
