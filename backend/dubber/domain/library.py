"""영상 목록 규칙: 구글 드라이브 목록 폴더의 영상마다 이 PC의 프로젝트, 드라이브의 결과, 유튜브, 자동 진행 상태를
붙인다."""
import os
import re

from . import outputs
from . import youtube as yt


def natural(name):
    """숫자는 숫자로 비교하는 이름순(2 < 10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def build(root, files, projects, importing, import_status, yt_items, batch_items, videos):
    """files: 드라이브 목록 폴더의 파일(rclone 결과), projects: 프로젝트 요약(작업 상태 포함),
    importing: 지금 받는 영상의 드라이브 경로, videos: 유튜브 채널에 있는 영상."""
    sub = {f["path"] for f in files if "/" in f["path"]}
    by_path = {it["drive"]: it for it in projects if it.get("drive")}
    items, used = [], set()
    for f in sorted((f for f in files if "/" not in f["path"]), key=lambda f: natural(f["path"])):
        path = root + "/" + f["path"]
        stem = os.path.splitext(f["path"])[0]
        dubbed = outputs.dubbed(stem)
        it = {"name": stem, "path": path, "size": f["size"],
              "drive_done": f"{outputs.out_name(stem)}/{dubbed}" in sub or f"{stem}/out/{dubbed}" in sub,
              "legacy": f"{stem}/project.json" in sub,
              "project": by_path.get(path),
              "importing": import_status if importing == path else None,
              "youtube": yt_items.get(path),
              "batch": (batch_items.get(path) or {}).get("stage"),
              "yt_existing": yt.existing(stem, videos)}
        it["yt_ready"] = it["drive_done"] or bool(it["project"] and it["project"]["exported"])
        if it["project"]:
            used.add(it["project"]["dir"])
        items.append(it)
    return items, [p for p in projects if p["dir"] not in used]
