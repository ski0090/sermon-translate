"""포트: 유스케이스(application)가 바깥에 바라는 것. 구현은 adapters/outbound에 있고 bootstrap에서 끼운다.
진행은 progress 콜백, 중단은 cancel()이 True를 돌려주는 콜백으로 알린다."""
from .ai import AiRunner, StripImages, ToolProbe
from .drive import CloudDrive
from .media import DubRenderer, ShortsRenderer, SleepRenderer, VideoAnalyzer
from .speech import SpeechSynth
from .storage import ProjectRepository, StateStore, Workspace
from .video_platform import VideoPlatform

__all__ = ["AiRunner", "StripImages", "ToolProbe", "CloudDrive", "DubRenderer", "ShortsRenderer", "SleepRenderer",
           "VideoAnalyzer", "SpeechSynth", "ProjectRepository", "StateStore", "Workspace", "VideoPlatform"]
