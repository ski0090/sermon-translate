"""조립: 설정으로 어댑터(바깥)를 만들어 유스케이스(application)에 끼운다. 바깥을 바꾸려면 여기만 고친다."""
import os
from dataclasses import dataclass

from .adapters.outbound.ai_cli import CliAiRunner
from .adapters.outbound.cli_tool_probe import CliToolProbe
from .adapters.outbound.ffmpeg_dub import FfmpegDubRenderer
from .adapters.outbound.ffmpeg_shorts import FfmpegShortsRenderer
from .adapters.outbound.ffmpeg_sleep import FfmpegSleepRenderer
from .adapters.outbound.ffmpeg_video import FfmpegVideoAnalyzer
from .adapters.outbound.json_store import JsonStateStore
from .adapters.outbound.project_files import FileProjectRepository
from .adapters.outbound.rclone_drive import RcloneDrive
from .adapters.outbound.strip_images import PillowStripImages
from .adapters.outbound.supertonic_speech import SupertonicSpeech
from .adapters.outbound.youtube_api import YouTubeApi
from .application.ai_tools import AiToolsService
from .application.batch import BatchService
from .application.drive_import import DriveImportService
from .application.files import ProjectLocks
from .application.jobs import JobBoard
from .application.library import LibraryService
from .application.pipeline import PipelineService
from .application.projects import ProjectService
from .application.reading import CaptionReader
from .application.schedule import ScheduleService
from .application.shorts import ShortsService
from .application.sleep import SleepService
from .application.voice import VoiceService
from .application.youtube import YouTubeService


@dataclass
class App:
    """유스케이스 묶음. 입구(HTTP, 명령줄)는 이것만 쓴다."""
    cfg: object
    repo: object
    projects: ProjectService
    pipeline: PipelineService
    voice: VoiceService
    importer: DriveImportService
    library: LibraryService
    youtube: YouTubeService
    shorts: ShortsService
    sleep: SleepService
    batch: BatchService
    schedule: ScheduleService
    tools: AiToolsService

    def samples_dir(self):
        """목소리 예시 음성을 두는 곳."""
        return self.repo.area("_samples")


def build(cfg):
    # 바깥(어댑터)
    store = JsonStateStore(cfg.projects)
    repo = FileProjectRepository(cfg.projects)
    video = FfmpegVideoAnalyzer()
    ai = CliAiRunner(store)
    sleep_renderer = FfmpegSleepRenderer(cfg.sleep_font, cfg.sleep_sub)
    dub = FfmpegDubRenderer(sleep_renderer)
    drive = RcloneDrive(cfg.gdrive)

    # 유스케이스
    jobs = JobBoard()
    projects = ProjectService(repo, jobs, video)
    voice = VoiceService(SupertonicSpeech(cfg.tts_threads), projects)
    pipeline = PipelineService(projects, jobs, video, CaptionReader(ai, PillowStripImages(), store), voice, dub, drive)
    importer = DriveImportService(drive, projects, jobs, store, repo)
    library = LibraryService(drive, pipeline, importer, cfg.library)
    schedule = ScheduleService(store, ai)
    tools = AiToolsService(ai, CliToolProbe(), store)
    youtube = YouTubeService(YouTubeApi(cfg.gdrive, cfg.yt_client_id, cfg.yt_client_secret), store, projects, drive,
                             cfg.yt_playlist, cfg.library, os.path.join(cfg.projects, "_youtube"))
    locks = ProjectLocks()
    shorts = ShortsService(projects, store, locks, ai, FfmpegShortsRenderer(cfg.shorts_font, cfg.shorts_credit), drive,
                           pipeline)
    sleep = SleepService(projects, store, locks, dub, sleep_renderer, drive, pipeline)
    batch = BatchService(store, projects, jobs, pipeline, library, importer, drive, schedule, ai, cfg.voice_workers)

    # 서로 부르는 유스케이스 잇기
    library.youtube, library.batch = youtube, batch
    youtube.library, youtube.shorts, youtube.sleep = library, shorts, sleep
    shorts.youtube, shorts.schedule = youtube, schedule
    sleep.youtube = youtube
    pipeline.after_export = [shorts.after_export, sleep.after_export]
    pipeline.queued_status = batch.queued_status
    return App(cfg, repo, projects, pipeline, voice, importer, library, youtube, shorts, sleep, batch, schedule, tools)


def load_settings(app):
    """저장해 둔 AI 도구 설정과 스케줄을 읽는다."""
    app.tools.load()
    app.schedule.load()


def resume(app):
    """서버가 켜질 때, 꺼지기 전에 하던 일(받기, 단계, 유튜브, 자동 진행, 음성, 쇼츠, 음성 영상)을 이어 한다."""
    app.importer.resume()
    voice = app.pipeline.resume()  # 끊긴 음성은 음성 대기열에 넣는다(동시에 음성 줄 수만큼)
    app.youtube.resume()
    app.batch.resume(voice)
    app.shorts.resume()
    app.sleep.resume()
