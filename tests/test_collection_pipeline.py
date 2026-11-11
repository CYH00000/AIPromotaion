from api.services.collection_pipeline import (
    comment_matches,
    normalize_comment,
    public_author_fields,
    spreadsheet_safe,
)


def test_comment_filter_applies_include_and_exclude_keywords():
    assert comment_matches("想了解这个课程，求介绍", ["课程", "学习"], ["广告"])
    assert not comment_matches("课程广告，点击领取", ["课程"], ["广告"])
    assert comment_matches("普通交流内容", [], [])
    assert not comment_matches("普通交流内容", ["课程"], [])


def test_normalize_comment_keeps_only_approved_author_fields():
    normalized = normalize_comment(
        "xhs",
        {
            "comment_id": "comment-1",
            "note_id": "note-1",
            "content": "有帮助",
            "create_time": 1_760_000_000,
            "like_count": 4,
            "sub_comment_count": 2,
            "project_author": {
                "platform_user_id": "user-1",
                "nickname": "公开昵称",
                "profile_url": "https://www.xiaohongshu.com/user/profile/user-1",
                "avatar": "must-not-be-stored",
            },
        },
        {"note-1": {"title": "笔记标题", "url": "https://www.xiaohongshu.com/explore/note-1"}},
    )

    assert normalized is not None
    assert normalized["external_comment_id"] == "comment-1"
    assert normalized["content_title"] == "笔记标题"
    assert normalized["author_user_id"] == "user-1"
    assert set(normalized).isdisjoint({"avatar", "project_author"})


def test_normalize_comment_skips_records_without_platform_id():
    assert normalize_comment("dy", {"content": "no id"}, {}) is None


def test_public_author_fields_allowlist_excludes_other_profile_data():
    author = public_author_fields(
        "dy",
        {
            "uid": "user-2",
            "sec_uid": "secure-user-2",
            "nickname": "昵称",
            "signature": "not-approved",
            "avatar_thumb": {"url_list": ["not-approved"]},
        },
    )

    assert author == {
        "platform_user_id": "user-2",
        "nickname": "昵称",
        "profile_url": "https://www.douyin.com/user/secure-user-2",
    }


def test_spreadsheet_export_escapes_formulas_after_leading_whitespace():
    assert spreadsheet_safe(" \t=HYPERLINK(\"https://example.invalid\")") == "' \t=HYPERLINK(\"https://example.invalid\")"
