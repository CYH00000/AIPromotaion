from tools.collection_limits import limit_page_items


def test_page_limit_uses_only_remaining_global_capacity():
    page = [{"id": str(index)} for index in range(10)]

    assert len(limit_page_items(page, collected_count=0, max_count=1)) == 1
    assert limit_page_items(page, collected_count=4, max_count=6) == page[:2]
    assert limit_page_items(page, collected_count=6, max_count=6) == []

