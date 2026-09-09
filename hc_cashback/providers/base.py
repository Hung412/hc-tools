import logging
import re
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

PROVIDER_REGISTRY = {}

STATUS_PENDING = 'pending'
STATUS_VALIDATED = 'validated'
STATUS_PAYABLE = 'payable'
STATUS_CANCELLED = 'cancelled'


def register(key, label):
    def wrapper(cls):
        cls._key = key
        cls._label = label
        PROVIDER_REGISTRY[key] = cls
        return cls
    return wrapper


def selection_keys():
    return [(key, cls._label) for key, cls in PROVIDER_REGISTRY.items()]


@dataclass
class Conversion:
    """Provider agnostic view of one commissionable line."""

    order_reference: str
    item_reference: str
    commission_gross: float
    status: str
    sub_ids: list = field(default_factory=list)
    order_amount: float = 0.0
    currency: str = 'VND'
    purchase_datetime: object = None
    raw: dict = field(default_factory=dict)


class AffiliateProvider:
    """Base class every provider implementation derives from.

    Implementations translate a marketplace URL into a tracking URL and report
    back conversions in the `Conversion` shape above. Nothing outside this
    package may depend on a vendor specific payload.
    """

    _key = None
    _label = None
    _url_patterns = ()

    def __init__(self, provider):
        self.provider = provider
        self.env = provider.env

    def owns_url(self, url):
        return any(re.search(pattern, url or '') for pattern in self._url_patterns)

    def normalize_url(self, url):
        """Return (clean_url, shop_reference, item_reference)."""
        raise NotImplementedError

    def build_link(self, clean_url, sub_ids):
        """Return the tracking URL a member should open."""
        raise NotImplementedError

    def fetch_conversions(self, date_from, date_to):
        """Return a list of `Conversion` for the given purchase window."""
        raise NotImplementedError
