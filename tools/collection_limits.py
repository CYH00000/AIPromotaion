# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.


def limit_page_items(items, collected_count: int, max_count: int) -> list:
    """Restrict a platform page to the remaining task-wide content capacity."""
    remaining = max(0, max_count - collected_count)
    if remaining == 0:
        return []
    return list(items)[:remaining]
