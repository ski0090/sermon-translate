// 프로젝트 작업 화면이 연 프로젝트 하나의 상태와 동작(W)을 아래 조각(위젯·기능)에 넘기는 열쇠.
// W를 만드는 것은 pages/work(model/session.js)이고, 위젯·기능은 useWork()로 꺼내 쓴다
import { inject, provide } from "vue";

const WORK = Symbol("work");

export const provideWork = (W) => provide(WORK, W);
export const useWork = () => inject(WORK);
