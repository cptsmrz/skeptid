"""Provider implementations for SKEPTID."""

from skeptid.providers.external import ExternalProvider
from skeptid.providers.mock import MockProvider
from skeptid.providers.opensource import OpenSourceTextProvider
from skeptid.providers.opensource_image import OpenSourceImageProvider
from skeptid.providers.own_image import OwnImageProvider
from skeptid.providers.own_text import OwnTextProvider

__all__ = [
    "ExternalProvider",
    "MockProvider",
    "OpenSourceImageProvider",
    "OpenSourceTextProvider",
    "OwnImageProvider",
    "OwnTextProvider",
]
