# utils.py
import os
import socket
import urllib.request
import urllib.error
from os.path import dirname, abspath, realpath
from tempfile import mkstemp

from aqt import mw

CURRENT_DIR = dirname(abspath(realpath(__file__)))

_NET_CHECK_HOSTS = ("yandex.ru", "google.com", "1.1.1.1")
_NET_CHECK_TIMEOUT_S = 1.0


def path_to(*args):
    return os.path.join(CURRENT_DIR, *args)


def get_config():
    return mw.addonManager.getConfig(__name__)


def report(text: str):
    try:
        from aqt.utils import showWarning
        showWarning(text, title="Image Search v3")
    except Exception:
        print(text)


def get_note_query(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()["id"])

    # Determine preferred query fields (per-notetype first, then global)
    query_fields = []
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("query_fields"):
        query_fields = nt_configs[nt_id]["query_fields"]
    elif "query_fields" in config and config["query_fields"]:
        query_fields = config["query_fields"]
    elif "query_field" in config:
        query_fields = [config["query_field"]]

    if query_fields:
        for fname in query_fields:
            if fname in field_names:
                return note.fields[field_names.index(fname)]

        # None of the configured fields exist; warn and fall back
        report(
            "Could not find any of the configured query fields in the current note type.\n"
            f"Note Type: {note.model()['name']}\n"
            f"Fields available: {', '.join(field_names)}\n"
            f"Fields tried: {', '.join(query_fields)}\n"
            "Falling back to the first field."
        )

    # Default: first field if present
    if field_names:
        return note.fields[0]
    return ""


def get_note_image_field_index(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()["id"])

    image_field = None
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("image_field"):
        image_field = nt_configs[nt_id]["image_field"]
    elif config.get("image_field"):
        image_field = config.get("image_field")

    if image_field:
        try:
            return field_names.index(image_field)
        except ValueError:
            if field_names:
                report(
                    f"Could not find the configured image field ('{image_field}') in "
                    f"the current note type ('{note.model()['name']}').\n"
                    f"Available fields: {', '.join(field_names)}\n"
                    f"Falling back to the last field: '{field_names[-1]}'."
                )
                return len(field_names) - 1
            report(
                f"Could not find the configured image field ('{image_field}') in the current "
                f"note type ('{note.model()['name']}'), and no fields are available."
            )
            return None

    if field_names:
        return len(field_names) - 1
    return None


def _network_available() -> bool:
    try:
        socket.setdefaulttimeout(_NET_CHECK_TIMEOUT_S)
        for host in _NET_CHECK_HOSTS:
            try:
                socket.gethostbyname(host)
                return True
            except Exception:
                continue
        return False
    finally:
        try:
            socket.setdefaulttimeout(None)
        except Exception:
            pass


def _infer_suffix_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.lower()
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            if path.endswith(ext):
                return ext
    except Exception:
        pass
    return ".jpg"


def save_file_to_library(editor, image_url, prefix, suffix):
    """
    Download image_url to a temp file and add it to Anki media.

    Returns (media_filename, error_code) where error_code is one of:
    - None (success)
    - 'offline' (clear offline case)
    - 'network' (timeout/URLError/HTTPError)
    - 'unexpected' (any other exception)
    """
    if not _network_available():
        return None, "offline"

    try:
        (i_file, temp_path) = mkstemp(prefix=prefix, suffix=suffix)
        try:
            with urllib.request.urlopen(image_url, timeout=10) as response:
                image_binary = response.read()
                os.write(i_file, image_binary)
        finally:
            os.close(i_file)

        result_filename = editor.mw.col.media.addFile(temp_path)
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        return result_filename, None

    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
        return None, "network"
    except Exception as e:
        report(f"Unexpected error while saving image\n\n{repr(e)}\n\n{image_url}")
        return None, "unexpected"


def save_image_to_library(editor, image_url):
    """
    Derive a stable filename prefix when possible and pick an extension from the URL.
    Returns (media_filename, error_code) as described in save_file_to_library().
    """
    if not image_url:
        return None, "network"
    prefix = "img_"
    try:
        if "id=" in image_url:
            prefix = image_url.split("id=")[1].split("&")[0] + "_"
    except Exception:
        pass
    suffix = _infer_suffix_from_url(image_url)
    return save_file_to_library(editor, image_url, prefix, suffix)


def image_tag(image_src):
    # Tag marked with class=imgsearch so only add-on images are targeted for replacement
    attrs = {"src": image_src, "class": "imgsearch"}
    tag_components = [f'{key}="{val}"' for key, val in attrs.items()]
    return f"<img {' '.join(tag_components)} />"
