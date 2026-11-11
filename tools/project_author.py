# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.


def public_author_fields(platform: str, source: dict) -> dict:
    """Extract the approved user ID, nickname, and canonical homepage URL only."""
    if platform == "dy":
        user_id = source.get("uid") or source.get("user_id")
        profile_id = source.get("sec_uid") or source.get("sec_user_id")
        profile_url = f"https://www.douyin.com/user/{profile_id}" if profile_id else None
    elif platform == "xhs":
        user_id = source.get("user_id")
        profile_url = (
            f"https://www.xiaohongshu.com/user/profile/{user_id}" if user_id else None
        )
    else:
        return {"platform_user_id": None, "nickname": None, "profile_url": None}

    return {
        "platform_user_id": str(user_id) if user_id else None,
        "nickname": str(source.get("nickname") or "") or None,
        "profile_url": profile_url,
    }
