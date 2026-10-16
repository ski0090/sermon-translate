// fn을 ms마다 부른다. 앞 호출이 안 끝났으면 건너뛰고 탭이 숨어 있으면 쉰다. 멈추는 함수를 돌려준다
export function every(ms, fn) {
  let busy = false;
  const tick = async () => {
    if (busy || document.hidden) return;
    busy = true;
    try {
      await fn();
    } catch (e) {
    } finally {
      busy = false;
    }
  };
  const vis = () => {
    if (!document.hidden) tick();
  };
  tick();
  const t = setInterval(tick, ms);
  document.addEventListener("visibilitychange", vis);
  return () => {
    clearInterval(t);
    document.removeEventListener("visibilitychange", vis);
  };
}
