from aqt import mw
from anki.hooks import addHook

from . import utils
from . import search

# Global variable to store the last query used for a search
last_query = None

def display_image(editor, img_filename, image_dest_field_index):
    img_tag = utils.image_tag(img_filename)

    # Get placement config
    config = utils.get_config()
    nt_id = str(editor.note.model()['id'])
    nt_configs = config.get("configs_by_notetype_id", {})
    nt_config = nt_configs.get(nt_id, {})
    placement = nt_config.get("image_placement", "append") # Default to append

    current_content = editor.note.fields[image_dest_field_index]

    if placement == "append":
        # Add a space if the field is not empty
        separator = " " if current_content else ""
        editor.note.fields[image_dest_field_index] += separator + img_tag
    elif placement == "prepend":
        separator = " " if current_content else ""
        editor.note.fields[image_dest_field_index] = img_tag + separator + current_content
    else: # "replace"
        editor.note.fields[image_dest_field_index] = img_tag

    editor.loadNote()


def search_image(editor):
    global last_query
    query = editor.web.selectedText()
    if not query:
        query = utils.get_note_query(editor.note)

    if not query:
        utils.report("Could not determine a query. Please select some text or configure a query field for this note type.")
        return

    last_query = query
    image_url = search.get_result_by_query(query)
    if not image_url:
        utils.report("Couldn't find images for query '{}' :(".format(query))
        return

    filename = utils.save_image_to_library(editor, image_url)
    if not filename:
        return

    image_dest_field_index = utils.get_note_image_field_index(editor.note)
    if image_dest_field_index is None:
        return

    display_image(editor, filename, image_dest_field_index)


def prev_image(editor):
    global last_query
    if not last_query:
        utils.report("Please perform a search first before using the previous/next buttons.")
        return

    image_url = search.get_prev_result_by_query(last_query)
    if not image_url:
        # This can happen if you are at the beginning of the list
        utils.report("No previous image available for query '{}'.".format(last_query))
        return

    filename = utils.save_image_to_library(editor, image_url)
    if not filename:
        return

    image_dest_field_index = utils.get_note_image_field_index(editor.note)
    if image_dest_field_index is None:
        return

    display_image(editor, filename, image_dest_field_index)


def next_image(editor):
    global last_query
    if not last_query:
        utils.report("Please perform a search first before using the previous/next buttons.")
        return

    image_url = search.get_next_result_by_query(last_query)
    if not image_url:
        # This can happen if you are at the end of the list
        utils.report("No more images found for query '{}'.".format(last_query))
        return

    filename = utils.save_image_to_library(editor, image_url)
    if not filename:
        return

    image_dest_field_index = utils.get_note_image_field_index(editor.note)
    if image_dest_field_index is None:
        return

    display_image(editor, filename, image_dest_field_index)


def add_context_menu_action(editor_webview, menu):
    selected_text = editor_webview.selectedText()
    if selected_text:
        action = menu.addAction("Search image for: '{}'".format(selected_text))
        action.triggered.connect(lambda _, e=editor_webview.editor: search_image(e))


def hook_image_buttons(buttons, editor):
    search_tip = "Search for image (uses selected text if any, otherwise uses configured field)"
    prev_tip = "Load previous image from last search"
    next_tip = "Load next image from last search"

    for (cmd, func, tip, icon) in [
        ("search_image", search_image, search_tip, "image"),
        ("prev_image", prev_image, prev_tip, "arrow-thick-left"),
        ("next_image", next_image, next_tip, "arrow-thick-right"),
    ]:
        icon_path = utils.path_to("images", "{}-2x.png".format(icon))
        buttons.append(editor.addButton(icon_path, cmd, func, tip=tip))

    return buttons


def init_editor():
    addHook("setupEditorButtons", hook_image_buttons)
    addHook("editor_will_show_context_menu", add_context_menu_action)
