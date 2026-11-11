from datetime import datetime, timedelta, timezone

from api.services.run_progress import JsonlLineCounter, is_stalled


def _comment_file(tmp_path):
    path = tmp_path / "dy" / "jsonl" / "search_comments_2026-11-11.jsonl"
    path.parent.mkdir(parents=True)
    return path


def test_counter_counts_appended_lines(tmp_path):
    path = _comment_file(tmp_path)
    path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")
    counter = JsonlLineCounter()

    assert counter.scan(tmp_path) == (0, 2)

    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"id":3}\n')

    assert counter.scan(tmp_path) == (0, 3)


def test_counter_ignores_incomplete_trailing_line(tmp_path):
    path = _comment_file(tmp_path)
    path.write_text('{"id":1}\n{"id":2}', encoding="utf-8")
    counter = JsonlLineCounter()

    assert counter.scan(tmp_path) == (0, 1)

    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")

    assert counter.scan(tmp_path) == (0, 2)


def test_counter_resets_when_file_shrinks(tmp_path):
    path = _comment_file(tmp_path)
    path.write_text('{"id":1}\n{"id":2}\n{"id":3}\n', encoding="utf-8")
    counter = JsonlLineCounter()
    assert counter.scan(tmp_path) == (0, 3)

    path.write_text('{"id":9}\n', encoding="utf-8")

    assert counter.scan(tmp_path) == (0, 1)


def test_counter_separates_contents_and_comments(tmp_path):
    path = _comment_file(tmp_path)
    path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")
    content = path.with_name("search_contents_2026-11-11.jsonl")
    content.write_text('{"id":10}\n', encoding="utf-8")

    assert JsonlLineCounter().scan(tmp_path) == (1, 2)


def test_stall_threshold():
    now = datetime.now(timezone.utc)

    assert is_stalled(now - timedelta(seconds=179), now, 180) is False
    assert is_stalled(now - timedelta(seconds=181), now, 180) is True
    assert is_stalled(None, now, 180) is False
