"""
PRISM Corporate Slate — paste your organization's sample code here.

──────────────────────────────────────────────────────────────────────────────
HOW IT WORKS
──────────────────────────────────────────────────────────────────────────────
1. Replace the example class below with ONE real page-object file from your
   codebase (any language — .py / .ts / .js / .java also accepted).
2. Run:  python main.py learn
3. PRISM extracts your coding style → writes style_profile.json
4. All future `shadow` output will match your style automatically.

Updating style: just replace the content below and re-run `python main.py learn`.
──────────────────────────────────────────────────────────────────────────────
SUPPORTED INPUT LANGUAGES
──────────────────────────────────────────────────────────────────────────────
  .py   → uses Python ast module (accurate)
  .ts   → regex-based extraction
  .js   → regex-based extraction
  .java → regex-based extraction

To use a non-Python file, set in config.json:
    "shadow_coding": {
        "slate_file": "Prism_view/shadow_coding/corporate_slate.ts",
        "slate_language": "typescript"
    }
──────────────────────────────────────────────────────────────────────────────
EXAMPLE — replace everything below this line with your real corporate sample
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from Base_page import BasePage

logger = logging.getLogger(__name__)


class Videos(BasePage):
    item = "Videos"
    search_videos_url = "*/api/inventory_svc/videos/search?*"

    def create_videos(
        self,
        od_name: str,
        headers: Dict,
        videos_list: List[Dict],
        no_direct: bool = False,
        skip_create_if_exists: bool = False,
    ) -> None:
        """Create Videos from a list of item dicts.

        Args:
            od_name: Operation name.
            headers: HTTP headers dict.
            videos_list: List of video data dicts.
            no_direct: Skip navigation if True.
            skip_create_if_exists: Skip item if it already exists.
        """
        for item in videos_list:
            if no_direct is False:
                self.direct_to_network_items("videos")

            need_create = True
            if skip_create_if_exists:
                if self.search_detail_ui_instead_oltp(
                    search_url=self.search_videos_url,
                    name=item.get("Name", item.get("Title1", "")),
                ):
                    logger.info(f"Skipping — Video already exists: {item.get('Title1', '')}")
                    need_create = False

            if need_create:
                logger.info(f"Creating Video: {item}")
                self.create_btn_click()
                self.page.get_by_role("textbox", name="Video Title").clear()
                self.page.get_by_role("textbox", name="Video Title").fill(item["Title1"])
                self.page.get_by_role("textbox", name="Description").clear()
                self.page.get_by_role("textbox", name="Description").fill(item["Description"])
                self.wait_until_page_loaded()
                self.create_btn_click(wait_success=True)
                logger.info(f"Video created: {item.get('Title1', '')}")
