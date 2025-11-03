from anki.utils import strip_html_media
from . import utils
from .yimages import get_yimages

# Try to import Google provider if present
try:
    from .gimages import get_gimages
except Exception:
    get_gimages = None

# storage of lists of images by queries
YIMAGES = {}

# indices of current image in list by queries
INDICES = {}


def get_current_image_url_by_query(query):
    query = strip_html_media(query)
    if (
        query not in YIMAGES
        or not YIMAGES[query]
        or query not in INDICES
        or INDICES[query] < 0
        or INDICES[query] >= len(YIMAGES[query])
    ):
        return None
    return YIMAGES[query][INDICES[query]]


def _resolve_provider_results(query: str):
    cfg = utils.get_config() or {}
    provider = (cfg.get("provider") or "yandex").lower()
    if provider == "google" and get_gimages:
        urls = get_gimages(query)
        if urls:
            return urls
        # fallback to Yandex if Google is empty (quota/filters/etc.)
        return get_yimages(query)
    # default provider
    return get_yimages(query)


def get_result_by_query(query):
    query = strip_html_media(query)
    if query not in YIMAGES or not len(YIMAGES[query]):
        image_urls = _resolve_provider_results(query)
        YIMAGES[query] = image_urls
        if YIMAGES.get(query):
            INDICES[query] = 0
            return get_current_image_url_by_query(query)
        else:
            INDICES[query] = -1
            return None


def get_next_result_by_query(query):
    query = strip_html_media(query)
    # Make sure the list of images for the query exists
    if query not in YIMAGES:
        return None
    if INDICES.get(query, -1) < len(YIMAGES[query]) - 1:
        INDICES[query] += 1
        return get_current_image_url_by_query(query)


def get_prev_result_by_query(query):
    query = strip_html_media(query)
    # Make sure the list of images for the query exists
    if query not in YIMAGES:
        return None
    if INDICES.get(query, -1) >= 1:
        INDICES[query] -= 1
        return get_current_image_url_by_query(query)
