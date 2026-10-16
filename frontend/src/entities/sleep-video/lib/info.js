// 음성 영상 한 줄의 표시: 만드는 중이거나 대기 중인지, 진행 퍼센트, 완성된 영상의 길이·크기·만든 때·드라이브 올림
import { fmt, when } from "@/shared/lib/index.js";

export const svBusy = (x) => x.status === "queued" || x.status === "rendering";
export const svPct = (x) => Math.round((x.progress || 0) * 100);
export const svInfo = (x) =>
  (x.length ? fmt(x.length) + " · " : "") +
  (x.size ? Math.round(x.size / 2 ** 20) + "MB · " : "") +
  (x.rendered ? when(x.rendered) : "") +
  (x.drive && x.drive.folder
    ? " · 드라이브에 올림"
    : x.drive && x.drive.error
      ? " · 드라이브 실패"
      : "");
