from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Callable, Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PlatformDefinition:
    platform_id: str
    label: str
    source_modes: frozenset[str]
    login_supported: bool
    content_filters_supported: bool
    content_id_field: str
    content_url_field: str
    allowed_hosts: frozenset[str]
    source_parser: Callable[[str, str], str]


def _normalize_search_source(mode: str, value: str) -> str:
    text = value.strip()
    if not text or len(text) > 100:
        raise ValueError("搜索关键词必须为 1 到 100 个字符")
    return text


def _parse_douyin_source(mode: str, value: str) -> str:
    candidate = value.strip()
    if mode == "search":
        return _normalize_search_source(mode, candidate)
    if candidate.isdigit():
        return candidate
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"}:
        raise ValueError("内容来源必须是 HTTP 或 HTTPS 链接")
    if host not in {"douyin.com", "www.douyin.com", "v.douyin.com"}:
        raise ValueError("抖音来源必须使用 douyin.com 域名")
    if host == "v.douyin.com":
        return f"https://v.douyin.com{parts.path.rstrip('/')}"
    query = dict(item.split("=", 1) for item in parts.query.split("&") if "=" in item)
    match = re.search(r"/video/(\d+)", parts.path)
    content_id = query.get("modal_id") or (match.group(1) if match else None)
    if not content_id:
        raise ValueError("抖音来源必须包含视频 ID")
    return content_id


def _parse_xhs_source(mode: str, value: str) -> str:
    candidate = value.strip()
    if mode == "search":
        return _normalize_search_source(mode, candidate)
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"}:
        raise ValueError("内容来源必须是 HTTP 或 HTTPS 链接")
    if host not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
        raise ValueError("小红书来源必须使用 xiaohongshu.com 域名")
    match = re.search(r"/explore/([^/?]+)", parts.path)
    if not match:
        raise ValueError("小红书来源必须是笔记链接")
    return f"https://www.xiaohongshu.com/explore/{match.group(1)}"


PLATFORM_DEFINITIONS: Mapping[str, PlatformDefinition] = MappingProxyType(
    {
        "dy": PlatformDefinition(
            platform_id="dy",
            label="抖音",
            source_modes=frozenset({"search", "detail"}),
            login_supported=True,
            content_filters_supported=True,
            content_id_field="aweme_id",
            content_url_field="aweme_url",
            allowed_hosts=frozenset({"douyin.com", "www.douyin.com", "v.douyin.com"}),
            source_parser=_parse_douyin_source,
        ),
        "xhs": PlatformDefinition(
            platform_id="xhs",
            label="小红书",
            source_modes=frozenset({"search", "detail"}),
            login_supported=True,
            content_filters_supported=True,
            content_id_field="note_id",
            content_url_field="note_url",
            allowed_hosts=frozenset({"xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com"}),
            source_parser=_parse_xhs_source,
        ),
    }
)


def get_platform_definition(platform_id: str) -> PlatformDefinition:
    try:
        return PLATFORM_DEFINITIONS[platform_id]
    except KeyError as exc:
        raise ValueError(f"不支持的平台：{platform_id}") from exc
