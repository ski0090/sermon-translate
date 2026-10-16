"""계층 규칙 시험: 안쪽 계층은 바깥 계층을 가져오지 않는다(domain <- ports <- application <- adapters <- bootstrap).
domain과 application은 바깥 라이브러리(numpy, PIL, supertonic)와 프로세스·네트워크 모듈도 쓰지 않는다."""
import ast
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dubber")
LAYERS = ["domain", "ports", "application", "adapters", "bootstrap"]
OUTSIDE = {"numpy", "PIL", "supertonic", "subprocess", "urllib", "http", "socket", "signal", "shutil", "glob"}


def imports(path, package):
    """파일이 가져오는 dubber 안의 최상위 조각(domain, ports...)과 바깥 모듈."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    inner, outer = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # 상대 경로: package 기준으로 풀어 맨 위 조각을 본다
                parts = package.split(".")[:len(package.split(".")) - node.level + 1]
                target = parts + (node.module.split(".") if node.module else [])
                if len(target) > 1:
                    inner.add(target[1])
            else:
                outer.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            outer.update(a.name.split(".")[0] for a in node.names)
    return inner, outer


class LayerTest(unittest.TestCase):
    def test_dependencies_point_inward(self):
        for layer in ("domain", "ports", "application"):
            base = os.path.join(ROOT, layer)
            for name in os.listdir(base):
                if not name.endswith(".py"):
                    continue
                inner, outer = imports(os.path.join(base, name), f"dubber.{layer}")
                allowed = set(LAYERS[:LAYERS.index(layer) + 1])
                self.assertLessEqual(inner, allowed, f"{layer}/{name}가 바깥 계층을 가져온다: {inner - allowed}")
                if layer != "ports":
                    self.assertFalse(outer & OUTSIDE, f"{layer}/{name}가 바깥 모듈을 쓴다: {outer & OUTSIDE}")


if __name__ == "__main__":
    unittest.main()
