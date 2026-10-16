// 구글 드라이브에서 영상 고르기 창. 다 받으면 그 프로젝트를 연다. 보던 폴더는 다시 열어도 그대로다(model/folder.js)
import { computed, onMounted, onUnmounted, reactive } from "vue";
import { fsize } from "@/shared/lib/index.js";
import { openProject } from "@/shared/router/index.js";
import { ModalCard, TaskProgress } from "@/shared/ui/index.js";
import {
  fetchDriveStatus,
  listDrive,
  importDrive,
  cancelDriveImport,
} from "../api/drive.js";
import { folder as D } from "../model/folder.js";

export default {
  components: { ModalCard, TaskProgress },
  emits: ["close"],
  setup(_, { emit }) {
    const s = reactive({ items: null, error: null, job: null });
    const running = computed(() => !!(s.job && !s.job.done));
    const crumbs = computed(() => {
      const parts = D.path ? D.path.split("/") : [];
      return [
        { name: D.shared ? "공유 문서함" : "내 드라이브", path: "" },
      ].concat(
        parts.map((n, i) => ({
          name: n,
          path: parts.slice(0, i + 1).join("/"),
        })),
      );
    });
    async function list(path) {
      D.path = path;
      s.items = null;
      s.error = null;
      try {
        const items = await listDrive(path, D.shared);
        if (path === D.path) s.items = items;
      } catch (e) {
        if (path === D.path) s.error = e.message;
      }
    }
    let poll = null;
    function watchJob() {
      clearInterval(poll);
      const tick = async () => {
        const { job } = await fetchDriveStatus();
        s.job = job;
        if (!job || job.done) {
          clearInterval(poll);
          poll = null;
          if (job && job.done && !job.error && !job.cancelled && job.result) {
            emit("close");
            openProject(job.result.id);
          }
        }
      };
      tick();
      poll = setInterval(tick, 1000);
    }
    async function pick(it) {
      const p = (D.path ? D.path + "/" : "") + it.name;
      if (it.dir) return list(p);
      try {
        await importDrive(p, it.size, D.shared);
      } catch (e) {
        alert(e.message);
        return;
      }
      watchJob();
    }
    onMounted(async () => {
      list(D.path);
      const { job } = await fetchDriveStatus();
      if (job && !job.done) watchJob();
    });
    onUnmounted(() => clearInterval(poll));
    return {
      D,
      s,
      running,
      crumbs,
      list,
      pick,
      fsize,
      cancel: cancelDriveImport,
    };
  },
  template: `<ModalCard>
    <div class="row" style="justify-content:space-between;margin-top:0"><h2 style="margin:0">구글 드라이브에서 영상 선택</h2><label class="muted" style="margin:0"><input type="checkbox" v-model="D.shared" :disabled="running" @change="list('')"> 공유 문서함</label></div>
    <div class="row crumbs"><template v-for="(c,i) in crumbs" :key="c.path"><span v-if="i"> / </span><a @click="list(c.path)">{{c.name}}</a></template></div>
    <ul class="plist dlist" :class="{busy:running}">
      <li v-if="s.error" class="err">{{s.error}}</li>
      <li v-else-if="!s.items" class="muted">불러오는 중…</li>
      <li v-else-if="!s.items.length" class="muted">폴더나 영상 파일이 없습니다.</li>
      <template v-else><li v-for="it in s.items" :key="it.name" @click="pick(it)"><span>{{it.dir?"📁 ":"🎬 "}}{{it.name}}</span><span class="muted">{{it.dir?"":fsize(it.size)}}</span></li></template>
    </ul>
    <TaskProgress v-if="running" :msg="s.job.msg||'내려받는 중'" :progress="s.job.progress"><button class="small" @click="cancel">중단</button></TaskProgress>
    <div v-else-if="s.job&&s.job.error" class="err">{{s.job.error}}</div>
    <div class="muted">고른 영상은 이 PC(projects/_drive)에 내려받은 뒤 프로젝트로 만듭니다. 이미 받은 영상은 다시 받지 않습니다.</div>
    <div class="row" style="justify-content:flex-end;margin-top:12px"><button @click="$emit('close')">닫기</button></div>
  </ModalCard>`,
};
