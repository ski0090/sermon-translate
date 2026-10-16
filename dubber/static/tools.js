/* ---------- 설정 > AI 도구 ----------
   Claude, Codex, Antigravity마다 설치·로그인·플랜, 사용 켜기/끄기, 모델 고르기, 지금 쓰는 모델, 로그인·로그아웃·연결 시험.
   index.html의 $, api, esc, S, showView, stopPoll, when을 쓴다. */
const TL={d:null,poll:null};

async function showTools(){
  stopPoll();S.pid=null;S.d=null;
  showView("toolsv");$("#steps").innerHTML="";$("#title").textContent="AI 도구";
  history.replaceState(null,"","#tools");
  $("#tlList").innerHTML=`<div class="card muted">도구 상태를 확인하는 중…</div>`;
  await tlLoad(true);
  clearInterval(TL.poll);
  TL.poll=setInterval(async()=>{if(S.view!=="toolsv"){clearInterval(TL.poll);TL.poll=null;return;}
    // Codex 로그인 중에만 자주 새로 읽는다
    if((TL.d||[]).some(x=>x.login&&x.login.running))try{await tlLoad();}catch(e){}},2000);
}

async function tlLoad(fresh){
  const r=await api("/api/tools"+(fresh?"?fresh=1":""));TL.d=r.tools;
  const name={claude:"Claude",codex:"Codex",agy:"Antigravity"};
  $("#tlTop").innerHTML=`<strong>AI 도구</strong>
    <div class="muted">자막 읽기, 문장 정리, 쇼츠 후보 고르기에 쓰는 AI 도구입니다. 끈 도구는 쓰지 않고, 스케줄에서 끈 도구로 정한 날은 켜진 도구로 대신합니다. 모델을 비워 두면 도구의 기본 모델을 씁니다.</div>
    <div class="row">오늘 자동 작업 도구: <b>${r.today?esc(name[r.today]):"없음(모든 도구가 꺼짐)"}</b> <button class="small" id="tlRefresh">상태 다시 읽기</button></div>`;
  $("#tlRefresh").onclick=()=>tlLoad(true);
  const a=document.activeElement;if(a&&a.closest&&a.closest("#tlList")&&a.matches("input,select"))return;  // 고르는 중이면 덮지 않는다
  $("#tlList").innerHTML=r.tools.map(tlCard).join("");
}
function tlCard(x){
  const yes=(v,y,n,u)=>v===true?`<span class="badge ok">${y}</span>`:v===false?`<span class="badge bad">${n}</span>`:`<span class="badge">${u||"모름"}</span>`;
  const head=`<div class="row" style="justify-content:space-between;margin:0"><strong style="font-size:15px">${esc(x.name)}</strong>
    <label class="row" style="margin:0"><input type="checkbox" data-en="${x.tool}" ${x.enabled?"checked":""} ${x.installed?"":"disabled"}> 사용</label></div>`;
  if(!x.installed)return `<div class="card" style="margin-bottom:12px">${head}
    <div class="row"><span class="badge warn">설치 안 됨</span></div>
    <div class="muted">서버 PC 터미널에서 설치합니다:</div><pre class="tlcode">${esc(x.install)}</pre>
    <div class="muted">설치한 뒤 로그인: ${esc(x.login_help)} 그다음 "상태 다시 읽기"를 누르세요.</div></div>`;
  const plan=x.plan?`<span class="badge ok">플랜 ${esc(x.plan)}</span>`:"";
  const acct=x.account?` <span class="muted">${esc(x.account)}</span>`:"";
  const seen=x.seen_model?`${esc(x.seen_model)}${x.seen_t?` <span class="muted">(${when(x.seen_t)} 호출 기준)</span>`:""}`:"<span class=muted>아직 호출 기록 없음</span>";
  const opts=(x.models||[]).map(([v,l])=>`<option value="${esc(v)}" ${v===x.model?"selected":""}>${esc(l)}${v&&v!==l?` (${esc(v)})`:""}</option>`).join("")
    +(x.model&&!(x.models||[]).some(([v])=>v===x.model)?`<option value="${esc(x.model)}" selected>${esc(x.model)}</option>`:"");
  const fb=x.tool==="claude"?`<div class="muted">사용량을 다 쓰면 Fable로 이어 하기: <b>${x.fallback?"켜짐":"꺼짐"}</b>${x.fallback_now?' <span class="badge ok">지금 Fable로 작업 중</span>':""} (설정 &gt; 스케줄에서 바꿈)</div>`:"";
  const lg=x.login;
  const login=lg&&(lg.running||lg.error||lg.ok)?`<div class="tllogin">${lg.running?`<b>로그인 진행 중</b> — 아래 주소를 아무 기기의 브라우저에서 열고 코드를 넣으세요.<br>${lg.url?`<a href="${esc(lg.url)}" target="_blank">${esc(lg.url)}</a>`:"주소를 기다리는 중…"}${lg.code?` · 코드 <b style="font-size:16px;letter-spacing:1px">${esc(lg.code)}</b>`:""}`
      :lg.ok?`<span class="badge ok">로그인했습니다</span>`:`<span class="badge bad">로그인 실패</span> ${esc(lg.error||"")}`}
      ${lg.lines&&lg.lines.length&&!lg.url?`<pre class="tlcode">${esc(lg.lines.join("\n"))}</pre>`:""}${lg.running?` <button class="small" data-cancel="${x.tool}">로그인 취소</button>`:""}</div>`:"";
  const ts=x.tested?`<span class="muted">연결 시험 ${when(x.tested.t)}: ${x.tested.ok?`<span style="color:var(--ok)">성공</span>`:`<span style="color:var(--bad)">${esc(x.tested.msg)}</span>`}</span>`:"";
  const btns=[`<button class="small" data-test="${x.tool}">연결 시험</button>`,
    x.can_login&&!x.logged_in?`<button class="small primary" data-login="${x.tool}">로그인</button>`:"",
    x.can_login&&x.logged_in?`<button class="small" data-login="${x.tool}">다른 계정으로 로그인</button>`:"",
    x.can_logout&&x.logged_in!==false?`<button class="small" data-logout="${x.tool}">로그아웃 (설정 해제)</button>`:""].filter(Boolean).join(" ");
  return `<div class="card" style="margin-bottom:12px">${head}
    <div class="row">${yes(x.logged_in,"로그인됨","로그인 안 됨","로그인 확인 전")} ${plan}${acct} <span class="muted">${esc(x.version||"")}</span></div>
    <div class="row">지금 쓰는 모델: <b>${x.active_model?esc(x.active_model):"도구 기본"}</b>${x.model?' <span class="badge">직접 고름</span>':""} <span class="muted">· 마지막 호출: ${seen}</span></div>
    <div class="row">모델 <select data-model="${x.tool}">${opts}</select>
      ${x.tool!=="claude"?`<input data-mtext="${x.tool}" placeholder="목록에 없으면 이름 입력" style="width:200px" value="">`:""}<button class="small" data-msave="${x.tool}">모델 저장</button></div>
    ${fb}${x.logged_in===false?`<div class="muted">로그인: ${esc(x.login_help)}</div>`:""}${x.tool==="claude"?`<div class="muted">Claude 로그아웃은 이 PC의 Claude Code도 같이 로그아웃되어 화면에서는 하지 않습니다. 쓰지 않으려면 "사용"을 끄세요.</div>`:""}
    ${login}<div class="row">${btns} ${ts}</div></div>`;
}
$("#tlList").addEventListener("change",async e=>{
  const t=e.target;
  try{if(t.dataset.en){await api("/api/tools","POST",{tool:t.dataset.en,enabled:t.checked});await tlLoad();}}catch(err){alert(err.message);}
});
$("#tlList").addEventListener("click",async e=>{
  const b=e.target.closest("button");if(!b)return;
  try{
    if(b.dataset.msave){const t=b.dataset.msave,txt=document.querySelector(`[data-mtext="${t}"]`);
      const model=(txt&&txt.value.trim())||document.querySelector(`[data-model="${t}"]`).value;
      await api("/api/tools","POST",{tool:t,model});document.activeElement.blur();await tlLoad();return;}
    if(b.dataset.test){b.disabled=true;b.textContent="시험 중…";await api(`/api/tools/${b.dataset.test}/test`,"POST",{});await tlLoad(true);return;}
    if(b.dataset.login){const cur=(TL.d||[]).find(t=>t.tool===b.dataset.login);
      if(cur&&cur.logged_in&&!confirm("새로 로그인을 시작하면 지금 로그인이 잠시 풀립니다. 새 로그인을 끝내지 않으면(취소, 15분 지남) 지금 로그인을 되살립니다. 시작할까요?"))return;
      await api(`/api/tools/${b.dataset.login}/login`,"POST",{});await tlLoad();return;}
    if(b.dataset.cancel){await api(`/api/tools/${b.dataset.cancel}/cancel`,"POST",{});await tlLoad(true);return;}
    if(b.dataset.logout){if(!confirm("로그아웃하면 다시 로그인할 때까지 이 도구를 쓸 수 없습니다. 로그아웃할까요?"))return;
      await api(`/api/tools/${b.dataset.logout}/logout`,"POST",{});await tlLoad(true);return;}
  }catch(err){alert(err.message);await tlLoad();}
});
