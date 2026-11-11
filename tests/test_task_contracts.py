import pytest
from pydantic import ValidationError

from api.schemas.collection import TaskCreate


def test_task_contract_removes_temporary_xhs_query_tokens():
    task = TaskCreate(
        name="note collection",
        platform="xhs",
        source_mode="detail",
        source_values=[
            "https://www.xiaohongshu.com/explore/abc123?xsec_token=secret&xsec_source=pc_feed"
        ],
    )

    assert task.source_values == ["https://www.xiaohongshu.com/explore/abc123"]


def test_task_contract_rejects_too_frequent_intervals():
    with pytest.raises(ValidationError):
        TaskCreate(
            name="frequent task",
            platform="dy",
            source_mode="search",
            source_values=["topic"],
            schedule_type="interval",
            schedule_value="15",
        )


def test_task_contract_extracts_douyin_video_id_without_share_query():
    task = TaskCreate(
        name="video collection",
        platform="dy",
        source_mode="detail",
        source_values=["https://www.douyin.com/video/123456?from=share&modal_id=999999"],
    )

    assert task.source_values == ["999999"]
