# ui_editor.py

import re
from aqt import mw
from anki.hooks import addHook
from . import utils
from . import search
from .logger import log

try:
    from aqt import gui_hooks
except Exception:
    gui_hooks = None

_HOOKS_INSTALLED = False
_MW_HOOK_FLAG = "_imgsearchv3_editor_hooks_installed"
_LAST_Q_ATTR = "_imgsearchv3_last_query"


def _get_last_query(editor):
    return getattr(editor, _LAST_Q_ATTR, None)


def _set_last_query(editor, q):
    try:
        setattr(editor, _LAST_Q_ATTR, q)
    except Exception:
        pass


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
    full_reload = True  # append/prepend need to refresh the field
    new_value = current

    if placement == "append":
        sep = " " if current else ""
        new_value = current + sep + img_tag
    elif placement == "prepend":
        sep = " " if current else ""
        new_value = img_tag + sep + current
    else:
        # Smart replace (in-place swap preserves editor focus, undo, and selection).
        if current and current.strip():
            replaced = _replace_last_imgsearch_tag(current, img_tag)
            if replaced is not None:
                new_value = replaced
                full_reload = False
            else:
                new_value = current + (" " if current else "") + img_tag
        else:
            new_value = img_tag

    if new_value != current:
        editor.note.fields[image_dest_field_index] = new_value
    if full_reload:
        editor.loadNote()


def _show_download_error(code: str):
    if code == "offline":
        utils.report("No internet connection. Unable to download image. Please reconnect and try again.")
    elif code == "network":
        utils.report("Network error while downloading image. Please try again in a moment.")
    else:
        utils.report("Could not save image to media collection.")


def on_search(editor):
    query = editor.web.selectedText() if editor.web else ""
    if not query:
        query = utils.get_note_query(editor.note)
    if not query:
        utils.report("No text selected and no query field content found.")
        return

    _set_last_query(editor, query)
    log.info("on_search: query=%r", query)
    image_url = search.getresultbyquery(query)
    provider_label = search.get_provider_label(query)
    utils.notify(f"Provider: {provider_label}")
    if not image_url:
        log.info("on_search: no results for %r (provider=%s)", query, provider_label)
        utils.report(f"No images found for the query (provider: {provider_label}).")
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
    last = _get_last_query(editor)
    if not last:
        utils.report("No image search yet in this editor. Press the search button first.")
        return
    log.debug("on_previous: query=%r", last)
    url = search.getprevresultbyquery(last)
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
    last = _get_last_query(editor)
    if not last:
        utils.report("No image search yet in this editor. Press the search button first.")
        return
    log.debug("on_next: query=%r", last)
    url = search.getnextresultbyquery(last)
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
    # Emoji toolbar labels (icon assets removed)
    icon_search = ""
    icon_prev = ""
    icon_next = ""

    b_search = editor.addButton(
        icon_search,
        "imgsearch.search",
        lambda ed=editor: on_search(ed),
        "Search image",
        "🖼",
    )
    buttons.append(b_search)

    b_prev = editor.addButton(
        icon_prev,
        "imgsearch.prev",
        lambda ed=editor: on_previous(ed),
        "Previous image",
        "⬅",
    )
    buttons.append(b_prev)

    b_next = editor.addButton(
        icon_next,
        "imgsearch.next",
        lambda ed=editor: on_next(ed),
        "Next image",
        "➡",
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
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED or (mw and getattr(mw, _MW_HOOK_FLAG, False)):
        return
    addHook("setupEditorButtons", add_editor_buttons)
    add_editor_context_menu_install()
    _HOOKS_INSTALLED = True
    if mw:
        setattr(mw, _MW_HOOK_FLAG, True)
    # Apply log level from config (so a user setting takes effect immediately
    # after they change it in the Logs tab and reopen the editor).
    try:
        cfg = utils.get_config() or {}
        level = cfg.get("log_level")
        if level:
            log.set_level(level)
    except Exception:
        pass
    log.info("init_editor: hooks installed")
