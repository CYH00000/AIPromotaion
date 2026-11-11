import asyncio

import config
from cmd_arg import parse_cmd
from api.schemas.crawler import CrawlerStartRequest, PlatformEnum
from api.services.crawler_manager import crawler_manager


def test_login_only_flag_sets_config():
    previous = config.LOGIN_ONLY
    try:
        asyncio.run(parse_cmd(["--login_only", "true"]))
        assert config.LOGIN_ONLY is True
    finally:
        config.LOGIN_ONLY = previous


def test_login_only_is_forwarded_to_the_crawler_command():
    command = crawler_manager._build_command(
        CrawlerStartRequest(platform=PlatformEnum.DOUYIN, login_only=True)
    )
    assert "--login_only" in command
    assert command[command.index("--login_only") + 1] == "true"
