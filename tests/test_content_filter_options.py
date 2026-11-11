import asyncio
import time

import config
from api.schemas.crawler import CrawlerStartRequest, PlatformEnum
from api.services.crawler_manager import crawler_manager
from cmd_arg import parse_cmd
from tools.time_util import is_within_publish_window, publish_cutoff


def test_crawler_command_includes_content_filters():
    command = crawler_manager._build_command(
        CrawlerStartRequest(
            platform=PlatformEnum.DOUYIN,
            content_sort="latest",
            publish_time_days=7,
        )
    )

    assert command[command.index("--content_sort") + 1] == "latest"
    assert command[command.index("--publish_time_days") + 1] == "7"


def test_parse_cmd_sets_content_filters():
    previous_sort = config.CONTENT_SORT
    previous_days = config.PUBLISH_TIME_TYPE
    try:
        asyncio.run(parse_cmd(["--content_sort", "latest", "--publish_time_days", "7"]))
        assert config.CONTENT_SORT == "latest"
        assert config.PUBLISH_TIME_TYPE == 7
    finally:
        config.CONTENT_SORT = previous_sort
        config.PUBLISH_TIME_TYPE = previous_days


def test_publish_window_accepts_two_days_and_rejects_ten_days():
    now = int(time.time())
    cutoff = publish_cutoff(7)

    assert is_within_publish_window(now - 2 * 86400, cutoff) is True
    assert is_within_publish_window(now - 10 * 86400, cutoff) is False
    assert is_within_publish_window(None, 0) is True
