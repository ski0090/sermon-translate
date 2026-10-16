"""명령줄로 단계 실행: python backend/cli.py new|scan|read|sentences|tidy <영상 또는 프로젝트>"""
import sys

from dubber.adapters.inbound import cli

if __name__ == "__main__":
    cli.main(sys.argv[1:])
