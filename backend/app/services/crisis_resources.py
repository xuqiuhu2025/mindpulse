"""危机资源服务。

边界要求（对应产品边界 9/10）：
- 不硬编码“唯一可能失效的号码”：数据带 source/verified 字段，
  并始终提供国际目录（findahelpline 等）作为实时兜底。
- 无法确认用户所在地时，先询问国家或地区，而不是猜测。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..models.schemas import CrisisInfo, CrisisResource

logger = logging.getLogger("mindpulse.crisis")

_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "resources" / "crisis_resources.json"


class CrisisResourceService:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)
        self._directories = list(self._data.get("universal_directories", []))

    def get(self, country: str | None) -> CrisisInfo:
        if not country:
            return CrisisInfo(
                show_resources=True,
                need_country=True,
                country=None,
                emergency_number=None,
                resources=[],
                directories=self._directories,
                note="为了给你当地经过验证的支持资源，请告诉我你所在的国家或地区。"
                "如果你正处在立即危险中，请直接联系当地急救服务或前往最近的急诊室。",
            )

        code = country.strip().upper()
        entry = self._data["countries"].get(code)
        if entry is None:
            logger.info("crisis lookup: country=%s not in dataset, using directories", code)
            return CrisisInfo(
                show_resources=True,
                need_country=True,
                country=code,
                emergency_number=None,
                resources=[],
                directories=self._directories,
                note="暂时没有收录该国家/地区的已验证资源。请通过国际目录查找当地支持，"
                "或直接联系当地急救服务。",
            )

        resources = [CrisisResource(**h) for h in entry.get("helplines", [])]
        return CrisisInfo(
            show_resources=True,
            need_country=False,
            country=code,
            emergency_number=entry.get("emergency_number"),
            resources=resources,
            directories=self._directories,
            note="号码为静态数据，使用前请核对当地最新信息（每条附来源与核对日期）。",
        )
