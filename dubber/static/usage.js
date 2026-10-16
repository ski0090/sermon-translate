/* ---------- 사용량 ----------
   Claude(5시간·주간·Fable 추가 몫), Codex(한도), Antigravity(/usage)와 날짜별 호출 수·토큰.
   index.html의 $, api, esc, S, showView, stopPoll, when을 쓴다. */
const UV={poll:null};

async function showUsage(){
  stopPoll();S.pid=null;S.d=null;
  showView("usagev");$("#steps").innerHTML="";$("#title").textContent="사용량";
  history.replaceState(null,"","#usage");
  await uvLoad();
  clearInterval(UV.poll);
  UV.poll=setInterval(async()=>{if(S.view!=="usagev"){clearInterval(UV.poll);UV.poll=null;return;}try{await uvLoad();}catch(e){}},30000);
}
const uvAgo=t=>{if(!t)return "아직 모름";const m=Math.round((Date.now()/1000-t)/60);return m<1?"방금":m<60?m+"분 전":m<1440?Math.round(m/60)+"시간 전":Math.round(m/1440)+"일 전";};
function uvBar(label,used,resets,note){
  if(used==null)return `<div class="uvrow"><span class="uvlab">${label}</span><span class="muted">모름</span></div>`;
  const p=Math.round(used*100),c=p>=90?"var(--bad)":p>=70?"var(--warn)":"var(--accent)";
  return `<div class="uvrow"><span class="uvlab">${label}</span><div class="uvbar"><i style="width:${Math.min(100,p)}%;background:${c}"></i></div>
    <span class="uvval"><b>${p}%</b> 사용 · 남음 ${Math.max(0,100-p)}%</span><span class="muted">${resets?when(resets)+" 초기화":""}${note?" · "+note:""}</span></div>`;
}
const uvWin=m=>!m?"":m>=1440?Math.round(m/1440)+"일":m>=60?Math.round(m/60)+"시간":m+"분";
async function uvLoad(){
  const d=await api("/api/usage/all");
  const name=d.names,cw=d.claude.windows||{},cx=d.codex.limits||{},ag=d.agy||{};
  const card=(tool,title,body,t)=>`<div class="card" style="margin-bottom:12px"><div class="row" style="justify-content:space-between;margin:0">
      <strong>${title}${d.today===tool?' <span class="badge ok">오늘 자동 작업 도구</span>':""}</strong>
      <span class="row" style="margin:0"><span class="muted">${uvAgo(t)} 기준</span><button class="small" data-check="${tool}">확인</button></span></div>${body}</div>`;
  const claude=uvBar("5시간",(cw.five_hour||{}).utilization,(cw.five_hour||{}).resetsAt)+uvBar("주간",(cw.seven_day||{}).utilization,(cw.seven_day||{}).resetsAt)
    +uvBar("Fable 추가 몫",(cw.seven_day_overage_included||{}).utilization,(cw.seven_day_overage_included||{}).resetsAt,"주간 사용량을 다 쓴 뒤 Fable로 쓰는 몫")
    +(d.claude.status==="rejected"?`<div class="err" style="margin:6px 0 0">지금 한도에 걸려 있습니다</div>`:"");
  const win=(w,lab)=>w?uvBar(`${lab} (${uvWin(w.window_minutes)})`,w.used_percent/100,w.resets_at):"";
  const codex=(cx.primary||cx.secondary?win(cx.primary,"한도")+win(cx.secondary,"두 번째 한도"):`<div class="muted">아직 기록이 없습니다. "확인"을 누르면 아주 짧게 한 번 불러 봅니다.</div>`)
    +(cx.credits&&cx.credits.has_credits?`<div class="muted">크레딧 ${esc(String(cx.credits.balance))}</div>`:"")+(d.codex.model?`<div class="muted">마지막 모델 ${esc(d.codex.model)}</div>`:"");
  const agy=ag.text?`<pre class="tlcode">${esc(ag.text)}</pre>`:`<div class="muted">"확인"을 누르면 agy에 /usage(모델 할당량)를 물어봅니다. Antigravity가 설치·로그인되어 있어야 합니다.</div>`;
  const days=d.days.length?`<table class="uvtab"><tr><th>날짜</th>${Object.values(name).map(n=>`<th>${esc(n)}</th>`).join("")}</tr>
    ${d.days.map(([day,v])=>`<tr><td>${esc(day)}</td>${Object.keys(name).map(t=>{const x=v[t];return `<td>${x?`${x.calls}회${x.fails?` <span style="color:var(--bad)">(실패 ${x.fails})</span>`:""}<div class="muted">${uvTok(x.in)} / ${uvTok(x.out)}</div>`:'<span class="muted">-</span>'}</td>`;}).join("")}</tr>`).join("")}</table>
    <div class="muted">호출 수(실패 수)와 토큰(보낸 것 / 받은 것). 이 앱이 부른 것만 셉니다.</div>`:`<div class="muted">아직 기록이 없습니다.</div>`;
  const html=card("claude",esc(name.claude),claude,d.claude.t)+card("codex",esc(name.codex),codex,d.codex.t)+card("agy",esc(name.agy),agy,ag.t)
    +`<div class="card"><strong>날짜별 사용 (최근 14일)</strong>${days}</div>`;
  if($("#uvBody").innerHTML!==html)$("#uvBody").innerHTML=html;
}
const uvTok=n=>!n?"0":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?Math.round(n/1e3)+"K":String(n);
$("#uvBody").addEventListener("click",async e=>{
  const b=e.target.closest("[data-check]");if(!b)return;
  b.disabled=true;b.textContent="확인 중…";
  try{await api("/api/usage/all/check","POST",{tool:b.dataset.check});}catch(err){alert(err.message);}
  await uvLoad();
});
