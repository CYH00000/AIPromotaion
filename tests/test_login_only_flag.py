import asyncio

import config
from cmd_arg import parse_cmd


def test_login_only_flag_sets_config():
    previous = config.LOGIN_ONLY
    try:
        asyncio.run(parse_cmd(["--login_only", "true"]))
        assert config.LOGIN_ONLY is True
    finally:
        config.LOGIN_ONLY = previous
