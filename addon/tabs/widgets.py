# tabs/widgets.py

from __future__ import annotations

# Anki APIs resolve add-on metadata from the loaded module's package name.
# This is numeric for an installed add-on and usually `addon` in a checkout.
ADDON_PACKAGE = __name__.split(".")[0]
