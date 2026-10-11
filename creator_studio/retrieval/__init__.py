"""M66 structured media discovery foundation (offline by default)."""
from .engine import build_retrieval
from .provider import MediaProvider, OfflineEmptyProvider
from .models import RetrievalError, RetrievalRequest, ProviderRetrievalResult
from .stage import MediaRetrievalStage
