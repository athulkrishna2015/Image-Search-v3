import os
from os.path import dirname, abspath, realpath
import urllib
import importlib
from tempfile import mkstemp

from aqt import mw


CURRENT_DIR = dirname(abspath(realpath(__file__)))


def path_to(*args):
    return os.path.join(CURRENT_DIR, *args)


def get_config():
    return mw.addonManager.getConfig(__name__)


def get_note_query(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()['id'])
    
    query_fields = []
    
    # New per-note-type config
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("query_fields"):
        query_fields = nt_configs[nt_id]["query_fields"]
    # Fallback to old global config for backward compatibility
    elif "query_fields" in config and config["query_fields"]:
        query_fields = config["query_fields"]
    elif "query_field" in config:
        query_fields = [config["query_field"]]

    if query_fields:
        for field_name in query_fields:
            if field_name in field_names:
                idx = field_names.index(field_name)
                return note.fields[idx]

        # If no configured field is found in the note
        report(f"""Could not find any of the configured query fields in the current note type.

Note Type: {note.model()['name']}
Fields available: {', '.join(field_names)}
Fields tried: {', '.join(query_fields)}

Please review your settings for this note type.""")
        return ""

    # If no query fields configured, default to first field
    if field_names:
        return note.fields[0]

    return ""


def get_note_image_field_index(note):
    field_names = mw.col.models.fieldNames(note.model())
    config = get_config()
    nt_id = str(note.model()['id'])

    image_field = None

    # New per-note-type config
    nt_configs = config.get("configs_by_notetype_id", {})
    if nt_id in nt_configs and nt_configs[nt_id].get("image_field"):
        image_field = nt_configs[nt_id]["image_field"]
    # Fallback to old global config
    elif config.get("image_field"):
        image_field = config.get("image_field")

    if image_field:
        try:
            return field_names.index(image_field)
        except ValueError:
            report(
                f"""Could not find the configured image field ('{image_field}') in the current note type ('{note.model()['name']}').

Available fields: {', '.join(field_names)}

Please review your settings for this note type."""
            )
            return None

    # If image_field is not configured, default to the last field.
    if field_names:
        return len(field_names) - 1

    return None


def save_file_to_library(editor, image_url, prefix, suffix):
    (i_file, temp_path) = mkstemp(prefix=prefix, suffix=suffix)

    with urllib.request.urlopen(image_url) as response:
        image_binary = response.read()

    os.write(i_file, image_binary)
    os.close(i_file)

    result_filename = editor.mw.col.media.addFile(temp_path)
    try:
        os.unlink(temp_path)
    except:
        pass
    return result_filename


def save_image_to_library(editor, image_url):
    if not image_url:
        return
    # parsing Yandex Images thumbnail url to get id
    image_id = image_url.split("id=")[1].split("&")[0]
    return save_file_to_library(editor, image_url, image_id, ".webp")


def image_tag(image_url):
    attrs = {"src": image_url, "class": "imgsearch"}

    tag_components = ['{}="{}"'.format(key, val) for key, val in attrs.items()]

    return "<img " + " ".join(tag_components) + " />"


def report(text):
    if importlib.util.find_spec("aqt"):
        from aqt.utils import showWarning

        showWarning(text, title="Image Search v3")
    else:
        print(text)