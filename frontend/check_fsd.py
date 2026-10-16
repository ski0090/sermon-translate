"""화면 코드의 FSD 규칙 검사(Node 없이): 층은 아래로만 가져오고(app → pages → widgets → features → entities → shared),
다른 조각은 그 조각의 index.js(공개 API)로만 가져온다. 같은 층의 다른 조각은 가져오지 않는다(entities의 @x는 허용).
사용: python frontend/check_fsd.py (문제가 있으면 어디인지 적고 1로 끝난다)"""
import os
import re
import sys

LAYERS = ["shared", "entities", "features", "widgets", "pages", "app"]  # 아래 -> 위
SLICED = {"entities", "features", "widgets", "pages"}
IMPORT = re.compile(r"""(?:import|export)\s[^'"]*?from\s*["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)""")


def where(rel):
    """src 기준 경로 -> (층, 조각 또는 None, 조각 안 경로)."""
    parts = rel.split("/")
    layer = parts[0]
    if layer in SLICED and len(parts) > 1:
        return layer, parts[1], "/".join(parts[2:])
    return layer, None, "/".join(parts[1:])


def main(root):
    src = os.path.join(root, "src")
    bad = []
    for dp, _, files in os.walk(src):
        for f in files:
            if not f.endswith(".js"):
                continue
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, src).replace(os.sep, "/")
            me = where(rel)
            text = open(path, encoding="utf-8").read()
            for m in IMPORT.finditer(text):
                spec = m.group(1) or m.group(2)
                if spec == "vue":
                    continue
                if spec.startswith("@/"):
                    target = spec[2:]
                elif spec.startswith("."):
                    target = os.path.normpath(os.path.join(os.path.dirname(rel), spec)).replace(os.sep, "/")
                else:
                    bad.append((rel, spec, "모르는 모듈"))
                    continue
                t = where(target)
                if t[0] not in LAYERS:
                    bad.append((rel, spec, "층이 아님"))
                    continue
                if (me[0], me[1]) == (t[0], t[1]):
                    if spec.startswith("@/") and me[1]:
                        bad.append((rel, spec, "같은 조각 안은 상대 경로로"))
                    continue
                if LAYERS.index(t[0]) > LAYERS.index(me[0]):
                    bad.append((rel, spec, "위층을 가져옴"))
                elif t[0] == me[0] and t[0] in SLICED and me[0] != "app":
                    if not (t[0] == "entities" and re.fullmatch(r"@x/[\w-]+\.js", t[2])):
                        bad.append((rel, spec, "같은 층의 다른 조각"))
                elif t[1] and t[2] not in ("index.js", "") and not re.fullmatch(r"@x/[\w-]+\.js", t[2]):
                    bad.append((rel, spec, "공개 API(index.js)가 아닌 곳"))
    for b in bad:
        print(*b, sep="  |  ")
    print("문제", len(bad), "곳")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))))
