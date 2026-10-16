"""HTTP API 경로표: 화면(frontend)이 쓰는 /api/... 를 유스케이스에 잇는다. 응답 모양은 화면과의 약속이라 바꾸지 않는다."""
from ....domain.errors import Conflict
from .server import Bytes, File, Json, Router, not_found

P = r"/api/p/([^/]+)"  # 프로젝트 id


def build(app):
    """app: bootstrap.App (유스케이스 묶음)."""
    r = Router()
    route = r.route

    # ---------- 목록과 자동 진행 ----------
    @route("GET", r"/api/projects")
    def projects(req):
        return app.pipeline.summaries()

    @route(None, r"/api/library")
    def library(req):
        return app.library.view(force=bool(req.query.get("refresh")))

    @route(None, r"/api/batch", errors={RuntimeError: 409})
    def batch(req):
        if req.method == "POST":
            body = req.body()
            if body.get("action") == "start":
                app.batch.start(body.get("voice"))
            elif body.get("action") == "stop":
                app.batch.stop()
        return app.batch.status()

    # ---------- AI 도구와 사용량 ----------
    @route(None, r"/api/tools", errors={ValueError: 400})
    def tools(req):
        if req.method == "POST":
            body = req.body()
            app.tools.set_config(body.get("tool"), body.get("enabled"), body.get("model"))
        return {"tools": app.tools.status(fresh=bool(req.query.get("fresh"))), "today": app.schedule.day_tool()}

    @route("POST", r"/api/tools/(claude|codex|agy)/(login|logout|test|cancel)", errors={ValueError: 409})
    def tool_action(req, tool, action):
        res = getattr(app.tools, action)(tool)
        return {"result": res, "tools": app.tools.status()}

    @route(None, r"/api/usage/all")
    def usage_all(req):
        return dict(app.tools.usage(), today=app.schedule.day_tool())

    @route("POST", r"/api/usage/all/check", errors={ValueError: 409, RuntimeError: 409})
    def usage_check(req):
        return dict(app.tools.check(req.body().get("tool")), today=app.schedule.day_tool())

    @route(None, r"/api/usage")
    def usage(req):
        return app.tools.claude_usage()

    @route("POST", r"/api/usage/check")
    def usage_claude_check(req):
        return app.tools.check_claude()

    @route(None, r"/api/schedule", errors={ValueError: 400, TypeError: 400})
    def schedule(req):
        if req.method == "POST":
            app.schedule.set(req.body())
        return app.schedule.view()

    # ---------- 유튜브 ----------
    @route(None, r"/api/youtube/status")
    def yt_status(req):
        return app.youtube.status()

    @route("POST", r"/api/youtube/login", errors={RuntimeError: 409})
    def yt_login(req):
        return {"url": app.youtube.login()}

    @route("POST", r"/api/youtube/upload", errors={RuntimeError: 409})
    def yt_upload(req):
        return app.youtube.enqueue(req.body()["path"])

    @route(None, r"/api/youtube/settings")
    def yt_settings(req):
        if req.method == "POST":
            app.youtube.save_settings(req.body())
        return app.youtube.settings_view()

    @route("POST", r"/api/youtube/cancel")
    def yt_cancel(req):
        app.youtube.cancel(req.body()["path"])
        return {"ok": True}

    # ---------- 음성 영상, 쇼츠 목록 ----------
    @route(None, r"/api/sleep")
    def sleep(req):
        if req.method == "POST":
            body = req.body()
            if "auto" in body:
                app.sleep.set_auto(body["auto"])
            if body.get("action") == "all":  # 아직 없는 영상 모두
                app.sleep.enqueue_missing()
        return app.sleep.summary()

    @route(None, r"/api/shorts")
    def shorts(req):
        if req.method == "POST":
            body = req.body()
            if "auto" in body:
                app.shorts.set_auto(body["auto"])
        return app.shorts.summary()

    # ---------- 구글 드라이브 ----------
    @route(None, r"/api/drive/status")
    def drive_status(req):
        return app.importer.status()

    @route(None, r"/api/drive/list")
    def drive_list(req):
        return app.importer.list_dir(req.query.get("path", ""), bool(req.query.get("shared")))

    @route("POST", r"/api/drive/import", errors={Conflict: (409, "이미 내려받는 영상이 있습니다")})
    def drive_import(req):
        return app.importer.start(req.body()).status()

    @route("POST", r"/api/drive/cancel")
    def drive_cancel(req):
        return app.importer.cancel()

    # ---------- 목소리 ----------
    @route(None, r"/api/voices")
    def voices(req):
        return app.voice.voices

    @route(None, r"/api/voice-sample/([^/]+)")
    def voice_sample(req, voice):
        if voice not in app.voice.voices:
            return Json({"error": "없는 목소리"}, 404)
        return File(app.voice.sample(voice, app.samples_dir()), cache=True)

    # ---------- 프로젝트 ----------
    @route("GET", P)
    def project(req, pid):
        return app.pipeline.view(pid)

    @route(None, P + r"/video")
    def video(req, pid):
        return File(app.projects.video_file(pid))

    @route(None, P + r"/crop/(.+)")
    def crop(req, pid, name):
        app.projects.get(pid)
        return File(app.projects.crop_file(pid, name), cache=True)

    @route("GET", P + r"/tts/(.+)")
    def tts(req, pid, name):
        app.projects.get(pid)
        return File(app.projects.tts_file(pid, name))

    @route(None, P + r"/frame")
    def frame(req, pid):
        return Bytes(app.projects.frame(pid, float(req.query.get("t", "0")), bool(req.query.get("roi"))), "image/jpeg")

    @route("GET", P + r"/job")
    def job(req, pid):
        app.projects.get(pid)
        return app.pipeline.job_status(pid)

    @route("POST", P + r"/job", errors={RuntimeError: 409})
    def job_start(req, pid):
        body = req.body()
        if body.get("kind") == "tts":  # 음성은 바로 시작하지 않고 음성 대기열에 넣는다(직접 누른 것이 앞)
            app.batch.voice_start(pid, body)
            return app.pipeline.job_status(pid)
        return app.pipeline.start(pid, body.get("kind"), body).status()

    @route("POST", P + r"/job/cancel")
    def job_cancel(req, pid):
        app.projects.get(pid)
        if app.batch.voice_cancel(pid):
            return app.pipeline.job_status(pid)
        return app.pipeline.cancel(pid)

    @route("POST", P + r"/roi")
    def roi(req, pid):
        return app.projects.set_roi(pid, req.body())

    @route("POST", P + r"/settings")
    def settings(req, pid):
        return app.projects.apply_settings(pid, req.body())

    @route("POST", P + r"/cuts")
    def cuts(req, pid):
        return app.projects.set_cuts(pid, req.body().get("cuts") or [])

    @route(None, P + r"/plan")
    def plan(req, pid):
        return app.projects.plan(pid)

    @route(None, P + r"/download")
    def download(req, pid):
        return File(app.projects.export_file(pid, req.query.get("path")), download=True)

    @route("DELETE", P + r"/sentence/(\d+)")
    def sentence_delete(req, pid, sid):
        app.projects.delete_sentence(pid, int(sid))
        return {"ok": True}

    @route("POST", P + r"/sentence/(\d+)")
    def sentence_update(req, pid, sid):
        return app.projects.update_sentence(pid, int(sid), req.body())

    @route(None, P + r"/sentence/(\d+)/split")
    def sentence_split(req, pid, sid):
        return app.projects.split_sentence(pid, int(sid), int(req.body()["cap"])) or {}

    @route(None, P + r"/sentence/(\d+)/merge")
    def sentence_merge(req, pid, sid):
        return app.projects.merge_next(pid, int(sid)) or {}

    @route(None, P + r"/sentence/(\d+)/tts")
    def sentence_tts(req, pid, sid):
        return app.voice.regenerate(pid, int(sid), req.body())

    # ---------- 프로젝트의 음성 영상 ----------
    @route("GET", P + r"/sleep/video")
    def sleep_video(req, pid):
        return File(app.sleep.video_file(pid), download=bool(req.query.get("dl")))

    sleep_actions = {"": "enqueue", "/cancel": "cancel", "/youtube": "upload", "/youtube/cancel": "cancel_upload"}

    @route("POST", P + r"/sleep(|/cancel|/youtube|/youtube/cancel)", errors={RuntimeError: 409})
    def sleep_action(req, pid, act):
        app.projects.get(pid)
        getattr(app.sleep, sleep_actions[act])(pid)
        return app.sleep.summary()

    # ---------- 프로젝트의 쇼츠 ----------
    shorts_errors = {ValueError: 409, RuntimeError: 409}

    def shorts_view(pid):
        return app.shorts.view(pid, lite=True)

    @route("GET", P + r"/shorts", errors=shorts_errors)
    def shorts_list(req, pid):
        return app.shorts.view(pid, lite=bool(req.query.get("lite")))

    @route("POST", P + r"/shorts/suggest", errors=shorts_errors)
    def shorts_suggest(req, pid):
        app.projects.get(pid)
        app.shorts.suggest_now(pid)
        return shorts_view(pid)

    @route("POST", P + r"/shorts/new", errors=shorts_errors)
    def shorts_new(req, pid):
        app.shorts.new(pid, float(req.body().get("at") or 0))
        return shorts_view(pid)

    @route(None, P + r"/shorts/(\d+)(/.*)?", errors=shorts_errors)
    def short(req, pid, sid, action):
        sid, action, m = int(sid), action or "", req.method
        app.projects.get(pid)
        app.shorts.item(pid, sid)  # 없으면 404
        if action == "/video" and m == "GET":
            return File(app.shorts.video_file(pid, sid), download=bool(req.query.get("dl")))
        if action == "/frame" and m == "GET":
            return Bytes(app.shorts.preview(pid, sid, float(req.query["t"]) if req.query.get("t") else None),
                         "image/jpeg")
        if action == "" and m == "DELETE":
            app.shorts.delete(pid, sid)
        elif action == "" and m == "POST":
            app.shorts.update(pid, sid, req.body())
        elif action == "/render" and m == "POST":
            app.shorts.render(pid, sid)
        elif action == "/youtube" and m == "POST":
            app.shorts.upload(pid, sid)
        elif action == "/youtube/cancel" and m == "POST":
            app.shorts.cancel_upload(pid, sid)
        else:
            return not_found()
        return shorts_view(pid)

    @route(None, P + r"(/.*)?")
    def project_other(req, pid, rest):
        app.projects.get(pid)  # 없는 프로젝트면 404
        return not_found()

    return r
