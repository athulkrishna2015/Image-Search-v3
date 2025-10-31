# utils.py

import os
from os.path import dirname, abspath, realpath
import importlib
import urllib.request
import urllib.error
import socket
import time
from tempfile import mkstemp

from aqt import mw

CURRENT_DIR = dirname(abspath(realpath(__file__)))
_NET_CHECK_HOST = "yandex.ru"
_NET_CHECK_TIMEOUT_S = 1.0

def path_to(*args):
    return os.path.join(CURRENT_DIR, *args)

def get_config():
    return mw.addonManager.getConfig(__name__)

def get_note_query(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()["id"])

    query_fields = []

    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("query_fields"):
        query_fields = nt_configs[nt_id]["query_fields"]
    elif "query_fields" in config and config["query_fields"]:
        query_fields = config["query_fields"]
    elif "query_field" in config:
        query_fields = [config["query_field"]]

    if query_fields:
        for field_name in query_fields:
            if field_name in field_names:
                idx = field_names.index(field_name)
                return note.fields[idx]
        report(
            f"Could not find any of the configured query fields in the current note type.\n"
            f"Note Type: {note.model()['name']}\n"
            f"Fields available: {', '.join(field_names)}\n"
            f"Fields tried: {', '.join(query_fields)}\n"
            f"Falling back to the first field."
        )
        if field_names:
            return note.fields[0]
        return ""

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
                    f"Could not find the configured image field ('{image_field}') in the current note type ('{note.model()['name']}').\n"
                    f"Available fields: {', '.join(field_names)}\n"
                    f"Falling back to the last field: '{field_names[-1]}'."
                )
                return len(field_names) - 1
            report(
                f"Could not find the configured image field ('{image_field}') in the current note type ('{note.model()['name']}'), and no fields are available."
            )
            return None

    if field_names:
        return len(field_names) - 1
    return None

def _network_available() -> bool:
    try:
        # Fast DNS check; avoids raising verbose exceptions on obvious offline cases
        socket.setdefaulttimeout(_NET_CHECK_TIMEOUT_S)
        socket.gethostbyname(_NET_CHECK_HOST)
        return True
    except Exception:
        return False
    finally:
        try:
            socket.setdefaulttimeout(None)
        except Exception:
            pass

def save_file_to_library(editor, image_url, prefix, suffix):
    """
    Download image_url to a temp file and add it to Anki media.
    Returns (media_filename, error_code) where error_code is one of:
      - None (success)
      - 'offline' (clear offline case)
      - 'network' (timeout/URLError/HTTPError)
      - 'unexpected' (any other exception)
    The caller is responsible for showing at most one concise message.
    """
    # Early offline check to avoid long timeouts and noisy tracebacks
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
        # Network flake/offline after the initial quick check
        return None, "network"
    except Exception as e:
        # Rare unexpected issues: report once here so they’re not silent
        report(f"Unexpected error while saving image\n\n{repr(e)}\n\n{image_url}")
        return None, "unexpected"

def save_image_to_library(editor, image_url):
    """
    For Yandex thumbnails, derive a stable temp filename prefix from 'id=' when present.
    Returns (media_filename, error_code) as described in save_file_to_library().
    """
    if not image_url:
        return None, "network"
    prefix = "yimg_"
    try:
        if "id=" in image_url:
            prefix = image_url.split("id=")[1].split("&")[0] + "_"
    except Exception:
        pass
    return save_file_to_library(editor, image_url, prefix, ".webp")

def image_tag(image_src):
    # Tag marked with class=imgsearch so only add-on images are targeted for replacement
    attrs = {"src": image_src, "class": "imgsearch"}
    tag_components = [f'{key}="{val}"' for key, val in attrs.items()]
    return "<img {}>".format(" ".join(tag_components))

def report(text):
    try:
        from aqt.utils import showWarning
        showWarning(text, title="Image Search v3")
    except Exception:
        print(text)
