# [Image Search v3](https://ankiweb.net/shared/info/178037783)

Image Search v3 is a powerful Anki add-on that lets you quickly find and add images to your cards directly from the editor. It searches for images based on the content of your fields or selected text and places the chosen image into a designated field.

## Features

- **Yandex Image Search**: Exclusively uses Yandex to find images.
- **Per-Note-Type Configuration**: Configure different query and image fields for each of your note types.
- **Graphical Settings Panel**: An easy-to-use settings panel to manage your configuration. No more manual file editing!
- **Smart Defaults**: Automatically uses the first field of a note type for searching and the last field for placing the image if not configured otherwise.
- **Search on Selection**: Simply highlight any text in the editor and use the search button or right-click context menu to search for an image.
- **Toolbar Integration**: Adds "Search", "Previous", and "Next" image buttons directly to the Anki editor toolbar for a fast workflow.
- **Right-Click Context Menu**: Right-click on highlighted text to instantly start an image search. [broken?]

## Usage

### 1. Configuration

Before using the add-on, it's best to configure it for your note types.

1.  Go to **Tools -> Image Search v3 Settings** from Anki's main window.
2.  The settings dialog will open. On the left, you will see a list of all your note types.
3.  Select a note type from the list.
4.  On the right, you can now configure that note type:
    -   **Query Fields**: Select one or more fields that the add-on should use to get the search query.
    -   **Image Field**: Select the field where the add-on should place the found image.
5.  If you don't configure a note type, the add-on will default to using the **first field** for the query and the **last field** for the image.
6.  You can use the **"Reset to Default"** button to revert the settings for the selected note type to this default behavior.
7.  Click **Save** to store your settings.

**Note:** This add-on uses Yandex as its exclusive image search provider. The option to choose a different search engine has been removed.

<img width="1214" height="737" alt="Screenshot_20251031_152138" src="https://github.com/user-attachments/assets/05a9f121-2a64-4de6-bfc6-cf9c8e664467" />


### 2. Searching for Images

There are three ways to search for an image in the card editor:

1.  **Using the Toolbar Button**: Click the **"Search Image"** button (the picture icon) on the editor toolbar.
    -   If you have text highlighted anywhere in the editor, that text will be used for the search.
    -   If no text is highlighted, the content of your configured **Query Field(s)** will be used.
2.  **Using the Right-Click Menu**: Highlight the text you want to search for, right-click it, and select **"Search image for: '...'"** from the context menu.
3.  **Browsing Results**: Use the **"Previous Image"** and **"Next Image"** buttons (the arrows) to browse through other image results for the last query that was performed from the query field(s).

<img width="2396" height="2044" alt="Screenshot_20251031_152224" src="https://github.com/user-attachments/assets/d311adb6-0313-4b65-9999-bc8aef374c5a" />
<img width="2396" height="2044" alt="Screenshot_20251031_152301" src="https://github.com/user-attachments/assets/f4c23fd3-0646-411a-a105-3120da3adda5" />
<img width="2396" height="2044" alt="Screenshot_20251031_152339" src="https://github.com/user-attachments/assets/ad8558af-233b-4fe5-a67f-1e869d76eb07" />


## Troubleshooting

### Context Menu Item Not Appearing

If the "Search image for..." option does not appear when you right-click on selected text, it might be due to a conflict with another add-on that also modifies the context menu. A common conflict is with add-ons that provide image editing or other right-click functionalities in the editor.

You can diagnose this by temporarily disabling other editor-related add-ons (like "Image Editor") via **Tools -> Add-ons**, restarting Anki, and checking if the menu item appears.

## License

This add-on is a modification of the work of original authors. Credit goes to the creators of [Anki Image Search v2](https://ankiweb.net/shared/info/432495333) and [Image Search](https://ankiweb.net/shared/info/885589449).

The icons are provided by [Open Iconic](https://useiconic.com/open).

This project is licensed under the [GPLv2](./LICENSE).
