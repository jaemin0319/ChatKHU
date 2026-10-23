"""RGB 카메라(UVC) 신원: 어느 카메라·어느 USB 포트로 보정했는지 cam2base.yaml에 남기고, 실행할 때 비교한다.

Astra의 OpenNI 시리얼은 여러 대가 같은 값(SN0001)이라 구별에 쓸 수 없다. 대신
  - v4l 장치 이름 (/sys/class/video4linux/videoN/name)
  - USB 포트 경로 (/dev/v4l/by-path/...-video-index0 → /dev/videoN)
  - by-id 이름 (/dev/v4l/by-id/usb-<제조사>_<모델>_<시리얼>-video-index0, 있으면)
를 쓴다. 같은 카메라를 다른 USB 포트에 꽂으면 by-path가 바뀌므로 "다른 카메라일 수 있음"으로 본다(다시 보정하거나
같은 포트에 꽂는다). ⚠️ 리눅스 전용.
"""
from __future__ import annotations

import os
from pathlib import Path

SYS_V4L = Path("/sys/class/video4linux")
DEV_V4L = Path("/dev/v4l")


def device_name(index: int, root: Path = SYS_V4L) -> str:
    try:
        return (Path(root) / f"video{int(index)}" / "name").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _links_to(index: int, folder: Path) -> str:
    """folder 안에서 /dev/videoN을 가리키는 링크 이름 ("" = 없음)."""
    target = f"video{int(index)}"
    try:
        for p in sorted(folder.iterdir()):
            if os.path.basename(os.path.realpath(p)) == target:
                return p.name
    except OSError:
        pass
    return ""


def rgb_identity(index: int, sys_root: Path = SYS_V4L, dev_root: Path = DEV_V4L) -> dict:
    """/dev/videoN의 신원 {device, name, by_path, by_id}. 모르는 항목은 ""."""
    return {"device": int(index), "name": device_name(index, sys_root),
            "by_path": _links_to(index, Path(dev_root) / "by-path"),
            "by_id": _links_to(index, Path(dev_root) / "by-id")}


def identity_problems(recorded: dict | None, current: dict) -> list[str]:
    """보정 때 신원과 지금 신원의 차이 (빈 목록 = 같은 카메라·같은 포트로 보임).

    장치 번호(device)는 재부팅·연결 순서로 바뀔 수 있어 비교하지 않는다. 기록이 없으면(예전 보정 파일) 차이를 말할 수
    없으므로 ["no_identity"]를 돌려준다."""
    if not recorded:
        return ["no_identity"]
    out = []
    for key in ("name", "by_path", "by_id"):
        a, b = str(recorded.get(key) or ""), str(current.get(key) or "")
        if a and b and a != b:
            out.append(f"{key}: calibrated '{a}', now '{b}'")
        elif a and not b:
            out.append(f"{key}: calibrated '{a}', now unknown")
    return out
