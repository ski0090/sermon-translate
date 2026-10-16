// 프로젝트 목록에서 아직 프로젝트가 없는 드라이브 영상을 눌렀을 때: 물어본 뒤 내려받기를 시작한다.
// 내려받기를 부탁했으면(실패해도) true, 그만두었으면 false
import { fsize } from "@/shared/lib/index.js";
import { importDrive } from "../api/drive.js";

export async function importLibraryItem(it) {
  const note = it.drive_done
    ? "\n이미 구글 드라이브에 결과가 있습니다. 다시 만들면 덮어씁니다."
    : it.legacy
      ? "\n다른 PC에서 작업한 기록이 있지만 이어서 할 수는 없고 처음부터 시작합니다."
      : "";
  if (
    !confirm(
      `"${it.name}" 영상(${fsize(it.size)})을 내려받아 작업을 시작할까요?${note}`,
    )
  )
    return false;
  try {
    await importDrive(it.path, it.size, false);
  } catch (e) {
    alert(e.message);
  }
  return true;
}
