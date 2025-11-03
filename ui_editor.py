# ui_editor.py

import re
from aqt import mw
from anki.hooks import addHook
from . import utils
from . import search

try:
    from aqt import gui_hooks
except Exception:
    gui_hooks = None

last_query = None


def _replace_last_imgsearch_tag(html: str, new_img_tag: str):
    pattern = r'(<img[^>]*\bclass="[^"]*\bimgsearch\b[^"]*"[^>]*>)'
    matches = list(re.finditer(pattern, html, flags=re.IGNORECASE))
    if not matches:
        return None
    start, end = matches[-1].span(1)
    return html[:start] + new_img_tag + html[end:]


def display_image(editor, img_filename, image_dest_field_index):
    img_tag = utils.image_tag(img_filename)
    config = utils.get_config()
    nt_id = str(editor.note.model()["id"])
    nt_configs = config.get("configs_by_notetype_id", {})
    nt_config = nt_configs.get(nt_id, {})
    placement = nt_config.get("image_placement", "replace")

    current = editor.note.fields[image_dest_field_index]

    if placement == "append":
        sep = " " if current else ""
        editor.note.fields[image_dest_field_index] = current + sep + img_tag
    elif placement == "prepend":
        sep = " " if current else ""
        editor.note.fields[image_dest_field_index] = img_tag + sep + current
    else:
        if current and current.strip():
            replaced = _replace_last_imgsearch_tag(current, img_tag)
            editor.note.fields[image_dest_field_index] = replaced or (current + (" " if current else "") + img_tag)
        else:
            editor.note.fields[image_dest_field_index] = img_tag

    editor.loadNote()


def _show_download_error(code: str):
    if code == "offline":
        utils.report("No internet connection. Unable to download image. Please reconnect and try again.")
    elif code == "network":
        utils.report("Network error while downloading image. Please try again in a moment.")
    else:
        utils.report("Could not save image to media collection.")


def on_search(editor):
    global last_query
    query = editor.web.selectedText() if editor.web else ""
    if not query:
        query = utils.get_note_query(editor.note)
    if not query:
        utils.report("No text selected and no query field content found.")
        return

    last_query = query
    image_url = search.getresultbyquery(query)
    if not image_url:
        utils.report("No images found for the query.")
        return

    idx = utils.get_note_image_field_index(editor.note)
    if idx is None:
        utils.report("No destination field found on this note type.")
        return

    img_filename, err = utils.save_image_to_library(editor, image_url)
    if err or not img_filename:
        _show_download_error(err or "unexpected")
        return

    display_image(editor, img_filename, idx)


def on_previous(editor):
    global last_query
    if not last_query:
        utils.report("No previous image search in this session.")
        return
    url = search.getprevresultbyquery(last_query)
    if not url:
        utils.report("No previous image available for this query.")
        return
    idx = utils.get_note_image_field_index(editor.note)
    if idx is None:
        utils.report("No destination field found on this note type.")
        return
    img_filename, err = utils.save_image_to_library(editor, url)
    if err or not img_filename:
        _show_download_error(err or "unexpected")
        return
    display_image(editor, img_filename, idx)


def on_next(editor):
    global last_query
    if not last_query:
        utils.report("No previous image search in this session.")
        return
    url = search.getnextresultbyquery(last_query)
    if not url:
        utils.report("No next image available for this query.")
        return
    idx = utils.get_note_image_field_index(editor.note)
    if idx is None:
        utils.report("No destination field found on this note type.")
        return
    img_filename, err = utils.save_image_to_library(editor, url)
    if err or not img_filename:
        _show_download_error(err or "unexpected")
        return
    display_image(editor, img_filename, idx)

def add_editor_buttons(buttons, editor):
    # Full paths to icons in images/
    icon_search = utils.path_to("images", "image-2x.png")
    icon_prev   = utils.path_to("images", "arrow-thick-left-2x.png")
    icon_next   = utils.path_to("images", "arrow-thick-right-2x.png")

    b_search = editor.addButton(
        icon_search,
        "imgsearch.search",
        lambda ed=editor: on_search(ed),
        "Search image",
    )
    buttons.append(b_search)

    b_prev = editor.addButton(
        icon_prev,
        "imgsearch.prev",
        lambda ed=editor: on_previous(ed),
        "Previous image",
    )
    buttons.append(b_prev)

    b_next = editor.addButton(
        icon_next,
        "imgsearch.next",
        lambda ed=editor: on_next(ed),
        "Next image",
    )
    buttons.append(b_next)

    return buttons


def _install_context_menu_modern():
    def on_ctx_menu(editor_webview, menu):
        editor = getattr(editor_webview, "editor", None)
        if editor is None:
            return
        sel = editor.web.selectedText() if getattr(editor, "web", None) else ""
        label = "Search image for selection" if sel else "Search image"
        action = menu.addAction(label)
        action.triggered.connect(lambda: on_search(editor))

    gui_hooks.editor_will_show_context_menu.append(on_ctx_menu)


def _install_context_menu_legacy():
    def on_ctx_menu_legacy(webview, menu):
        editor = getattr(webview, "editor", None)
        if editor is None:
            return
        sel = editor.web.selectedText() if getattr(editor, "web", None) else ""
        label = "Search image for selection" if sel else "Search image"
        action = menu.addAction(label)
        action.triggered.connect(lambda: on_search(editor))

    addHook("EditorWebView.contextMenuEvent", on_ctx_menu_legacy)


def add_editor_context_menu_install():
    if gui_hooks:
        _install_context_menu_modern()
    else:
        _install_context_menu_legacy()


def init_editor():
    addHook("setupEditorButtons", add_editor_buttons)
    add_editor_context_menu_install()
