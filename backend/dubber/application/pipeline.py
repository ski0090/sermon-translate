"""단계 작업 유스케이스: 자막 찾기 -> AI 읽기 -> 문장 정리, 음성 -> 내보내기 -> 드라이브 올리기.
project.json에 진행 중인 단계를 남겨 두고 끝나면(성공, 실패, 중단) 지운다. 서버가 중간에 꺼지면 표시가 남으므로
다시 켤 때 resume이 그 단계를 처음부터 다시 한다."""
import os
import posixpath
import traceback

from ..domain import outputs, placement

MAX_RESUME = 3  # 같은 단계를 연달아 다시 시작하는 최대 횟수(서버를 죽이는 작업이 무한히 반복되지 않게)


class PipelineService:
    def __init__(self, projects, jobs, video, reader, voice, dub, drive):
        self.projects = projects  # application.projects.ProjectService
        self.jobs = jobs          # application.jobs.JobBoard
        self.video = video        # ports.VideoAnalyzer
        self.reader = reader      # application.reading.CaptionReader
        self.voice = voice        # application.voice.VoiceService
        self.dub = dub            # ports.DubRenderer
        self.drive = drive        # ports.CloudDrive
        self.after_export = []    # 영상을 내보낸 뒤 부를 것(쇼츠 후보 고르기, 음성 영상): fn(project)
        self.queued_status = lambda pid: None  # 음성 대기열에서 기다리는 것의 상태(자동 진행이 채운다)

    # ---------- 상태 ----------
    def job_status(self, pid):
        j = self.jobs.get(pid)
        if j and not j.done:
            return j.status()
        return self.queued_status(pid) or (j.status() if j else None)

    def summaries(self):
        """프로젝트 목록. 돌고 있는 작업(없으면 음성 대기)을 붙인다."""
        items = self.projects.summaries()
        for it in items:
            j = self.jobs.get(it["dir"])
            it["job"] = j.status() if j and not j.done else self.queued_status(it["dir"])
        return items

    def view(self, pid):
        p, _ = self.projects.get(pid)
        d = p.view()
        d["job"] = self.job_status(pid)
        return d

    def cancel(self, pid):
        """돌고 있는 작업에 멈추라고 알린다(진행 중인 AI 호출이 끝나면 멈춘다)."""
        job = self.jobs.get(pid)
        if job and not job.done:
            job.cancelled = True
            job.msg = "중단하는 중 (진행 중인 AI 호출이 끝나면 멈춥니다. 최대 5분)"
        return job.status() if job else None

    # ---------- 시작과 이어 하기 ----------
    def start(self, pid, kind, params, restarts=0):
        p, lock = self.projects.get(pid)
        return self.start_step(pid, p, lock, kind, params, restarts)

    def start_step(self, pid, p, lock, kind, params, restarts=0):
        def fn(job):
            with lock:
                p.mark_running(kind, params, restarts)
                self.projects.save(p)
            try:
                return self.run(p, lock, kind, job, params)
            finally:
                with lock:
                    p.clear_running()
                    self.projects.save(p)
        j = self.jobs.start(pid, kind, fn)
        j.resumed = restarts > 0
        return j

    def _mark_step(self, p, lock, kind, params):
        """한 작업 안에서 다음 단계로 넘어갈 때 진행 중 표시를 바꾼다(다음 단계에서 꺼지면 그 단계부터 다시 하도록)."""
        with lock:
            p.mark_running(kind, params)
            self.projects.save(p)

    def resume(self):
        """서버가 켜질 때, 꺼지기 전에 하던 단계를 처음부터 다시 시작한다. 끊긴 음성(내보내기 포함)은 바로 시작하지 않고
        돌려준다(음성 대기열에 넣는다): [(프로젝트, 설정, 드라이브 경로)]"""
        voice = []
        for it in self.projects.summaries():
            pid = it["dir"]
            p, lock = self.projects.get(pid)
            run = p.data.get("running_step")
            if not run:
                continue
            if run["kind"] in ("tts", "export"):
                print(f"{pid}: 꺼지기 전에 하던 음성을 음성 대기열에 넣습니다", flush=True)
                voice.append((pid, {k: v for k, v in (run.get("params") or {}).items() if k == "force"},
                              (p.data.get("drive") or {}).get("path")))
                continue
            restarts = run.get("restarts", 0) + 1
            if restarts > MAX_RESUME:
                print(f"{pid}: {run['kind']} 단계가 {MAX_RESUME}번 연달아 끊겨 다시 시작하지 않습니다", flush=True)
                with lock:
                    p.clear_running()
                    self.projects.save(p)
                continue
            print(f"{pid}: 꺼지기 전에 하던 {run['kind']} 단계를 처음부터 다시 합니다", flush=True)
            self.start_step(pid, p, lock, run["kind"], run.get("params") or {}, restarts)
        return voice

    # ---------- 드라이브 ----------
    def drive_folder(self, p):
        """결과를 올릴 드라이브 폴더와 공유 문서함 여부. 공유 문서함 맨 위에 있는 파일은 상위 폴더가 없으니 내 드라이브에 둔다."""
        src = p.data["drive"]
        parent = posixpath.dirname(src["path"])
        return posixpath.join(parent, outputs.out_name(p.name)), bool(src.get("shared")) and bool(parent)

    def export_folder(self, p):
        """내보내기 때 올린 폴더가 있으면 그 폴더, 없으면 올릴 폴더."""
        ex = p.data.get("drive_export") or {}
        return (ex["folder"], ex.get("shared", False)) if ex.get("folder") else self.drive_folder(p)

    def upload_results(self, p, files, job, start):
        def prog(done, total, speed, i, n):
            job.progress = start + (1 - start) * done / total
            job.msg = f"구글 드라이브에 올리는 중 ({i}/{n} 파일, {done / 2**20:,.0f} / {total / 2**20:,.0f}MB)"
        job.msg = "구글 드라이브에 올리는 중"
        cancel = lambda: job.cancelled  # noqa
        folder, shared = self.drive_folder(p)
        try:
            ok = self.drive.upload(files, folder, shared, prog, cancel)
        except RuntimeError:
            if not shared:
                raise
            # 공유받은 폴더에 쓸 권한이 없으면 내 드라이브에 같은 이름의 폴더를 만든다
            folder, shared = posixpath.basename(folder), False
            ok = self.drive.upload(files, folder, False, prog, cancel)
        return {"folder": folder, "shared": shared, "files": [os.path.basename(f) for f in files]} if ok else None

    # ---------- 단계 ----------
    def run(self, p, lock, kind, job, params):
        """단계 작업. progress는 0~1, msg는 사람이 읽는 진행 설명."""
        cancel = lambda: job.cancelled  # noqa
        ws = self.projects.workspace(p.id)
        if kind == "scan":
            def prog(r):
                job.progress = r * 0.98
                job.msg = f"자막이 바뀌는 순간을 찾는 중 ({int(r * 100)}%)"
            n = self.scan_captions(p, lock, prog, cancel, auto_roi=params.get("auto_roi"),
                                   status=lambda m: setattr(job, "msg", m))
            if job.cancelled:
                return {"captions": n}
            # 자막 바뀜 찾기가 끝나면 AI 읽기로 바로 이어 간다(브라우저를 닫아도 이어진다)
            job.kind, job.progress = "read", 0.0
            self._mark_step(p, lock, "read", {})
            return self.run(p, lock, "read", job, {})
        if kind == "read":
            s = p.settings
            total = (len(p.data["captions"]) + s["per_strip"] - 1) // max(s["per_strip"], 1)
            tidy_on = s.get("ai_tidy")
            share = 0.85 if tidy_on else 1.0

            def prog(d, n):
                job.progress = share * d / max(n, 1)
                job.msg = f"AI가 자막 그림을 읽는 중 ({d}/{n} 묶음)"
            job.msg = f"AI가 자막 그림을 읽는 중 (0/{total} 묶음)"
            self.read_captions(p, lock, prog, cancel)
            if job.cancelled:
                return None
            merged = None
            if tidy_on:
                def prog2(d, k):
                    job.progress = share + (1 - share) * d / max(k, 1)
                    job.msg = f"AI가 문장을 정리하는 중 ({d}/{k} 묶음)"
                job.msg = "AI가 문장을 정리하는 중"
                merged = self._tidy(p, prog2, cancel)
            with lock:
                n = p.build_sentences(merged)
                self.projects.save(p)
                return {"sentences": n}
        if kind == "tidy":
            def prog2(d, k):
                job.progress = d / max(k, 1)
                job.msg = f"AI가 문장을 정리하는 중 ({d}/{k} 묶음)"
            job.msg = "AI가 문장을 정리하는 중"
            merged = self._tidy(p, prog2, cancel)
            if merged is None:
                return None
            with lock:
                n = p.build_sentences(merged)
                self.projects.save(p)
                return {"sentences": n}
        if kind == "tts":
            def prog(d, n):
                job.progress = d / max(n, 1)
                job.msg = f"음성을 만드는 중 ({d}/{n} 문장)"
            job.msg = "음성 엔진을 준비하는 중"
            self.voice.run_all(p, progress=prog, cancel=cancel, force=bool(params.get("force")))
            with lock:
                p.set_step("tts")
                p.settings["orig_audio"] = "remove"
                self.projects.save(p)
            if job.cancelled:
                return {}
            # 음성이 끝나면 모든 결과물을 원음 제거로 바로 내보낸다(브라우저를 닫아도 이어진다)
            job.kind = "export"
            params = {"want": ["video", "audio", "srt", "txt"], "orig_audio": "remove"}
            self._mark_step(p, lock, "export", params)
            return self.run(p, lock, "export", job, params)
        if kind == "export":
            return self._export(p, lock, job, params, ws, cancel)
        raise ValueError(kind)

    def scan_captions(self, p, lock, progress=None, cancel=None, auto_roi=False, status=None):
        """자막이 바뀌는 순간을 찾아 자막 한 장마다 그림과 시간을 기록한다(외부 전송 없음). progress(0~1)."""
        ws = self.projects.workspace(p.id)
        if auto_roi or not p.data.get("roi"):
            status and status("자막 영역을 찾는 중")
            with lock:
                p.set_roi(self.video.detect_band(p.data["video"], p.data["info"]))
                self.projects.save(p)
        status and status("자막이 바뀌는 순간을 찾는 중")
        dur = p.data["info"]["duration"]
        crops = ws.ensure("crops")
        for f in os.listdir(crops):
            os.remove(os.path.join(crops, f))
        segs = self.video.scan(p.data["video"], p.data["roi"], crops,
                               progress=lambda t: progress and progress(t / dur), cancel=cancel)
        with lock:
            n = p.set_captions(segs)
            self.projects.save(p)
        return n

    def read_captions(self, p, lock, progress=None, cancel=None):
        """자막 그림을 AI에 읽힌다. 읽은 묶음은 캐시되어 중단 후 이어서 할 수 있다. progress(끝낸 묶음, 묶음 수)."""
        s = p.settings
        ws = self.projects.workspace(p.id)
        paths = [ws.path("crops", c["crop"]) for c in p.data["captions"]]
        texts = self.reader.read_all(p.id, ws, paths, tool=s["tool"], workers=s["workers"], per_strip=s["per_strip"],
                                     progress=progress, cancel=cancel)
        with lock:
            p.set_caption_texts(texts)
            self.projects.save(p)

    def tidy_sentences(self, p, progress=None, cancel=None):
        """AI가 자막을 문장으로 묶고 글자를 고치고 읽는 글과 확인 필요를 붙인 결과. 중단하면 None."""
        return self._tidy(p, progress, cancel)

    def _tidy(self, p, progress, cancel):
        s = p.settings
        return self.reader.tidy_all(p.uncut_captions(), tool=s["tool"], workers=s["workers"],
                                    keep=list(s["dictionary"]), progress=progress, cancel=cancel)

    def _export(self, p, lock, job, params, ws, cancel):
        want = set(params.get("want") or ["video", "srt"])
        names = {"track": "음성 트랙을 합치는 중", "video": "영상을 만드는 중", "audio": "오디오 파일을 만드는 중",
                 "sleep": "자면서 듣는 설교 영상을 만드는 중"}
        drive = bool(p.data.get("drive"))
        scale = 0.8 if drive else 1.0  # 남은 0.2는 드라이브 올리기

        def prog(stage, r):
            weights = {"track": (0.0, 0.1), "video": (0.1, 0.45), "audio": (0.55, 0.05), "sleep": (0.6, 0.4)}
            a, w = weights.get(stage, (0, 1))
            job.progress = scale * (a + w * r)
            job.msg = f"{names.get(stage, stage)} ({int(r * 100)}%)"
        files = self.dub.export(p, ws, placement.plan(p), want,
                                orig_audio=params.get("orig_audio") or p.settings["orig_audio"],
                                progress=prog, cancel=cancel)
        with lock:
            p.set_step("export")
            p.data["last_export"] = files
            p.data["drive_export"] = None
            self.projects.save(p)
        if drive and files and not job.cancelled:
            uploaded = self.upload_results(p, files, job, scale)
            with lock:
                p.data["drive_export"] = uploaded
                self.projects.save(p)
        if "video" in want and files and not job.cancelled:
            for after in self.after_export:
                try:
                    after(p)
                except Exception:  # noqa  쇼츠·음성 영상 때문에 내보내기가 실패로 보이지 않게
                    traceback.print_exc()
        return {"files": files, "drive": p.data["drive_export"]}
