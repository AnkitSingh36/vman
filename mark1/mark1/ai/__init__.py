"""V-owned investigator. Proposals only; the server remains the authorization boundary."""
from .engine import Investigator
from .provider import ProviderAdapter

__all__ = ["Investigator", "ProviderAdapter"]
