/* ---------- 음성 영상(자면서 듣는 설교) 화면 ----------
   음성을 만든 영상마다 이퀄라이저 화면 + 싱크 없이 이은 음성 영상을 만들고, 재생·내려받기·유튜브 올리기를 한다.
   index.html의 $, api, esc, fmt, S, showView, navMark, navCounts, stopPoll, when을 쓴다. */
const SV={filter:"all",poll:null,busy:false,open:null,d:null};
const svStage=x=>x.status==="queued"||x.status==="rendering"?"making":x.has_file?"done":"todo";

async function showSleep(){
  stopPoll();S.pid=null;S.d=null;
  showView("sleepv");$("#steps").innerHTML="";$("#title").textContent="음성 영상";
  history.replaceState(null,"","#sleep");
  await svList();
  clearInterval(SV.poll);
  SV.poll=setInterval(async()=>{if(S.view!=="sleepv"){clearInterval(SV.poll);SV.poll=null;return;}
    if(SV.busy)return;SV.busy=true;try{await svList();}catch(e){}finally{SV.busy=false;}},3000);
}

async function svList(){
  const d=SV.d=await api("/api/sleep");
  navCounts("sleep",d.items.map(svStage));navMark();
  const todo=d.items.filter(x=>!x.has_file&&svStage(x)!=="making").length;
  const top=`<div class="row" style="justify-content:space-between;margin:0"><strong>음성 영상 (자면서 듣는 설교)</strong>
      <button class="primary small" id="svAll" ${todo?"":"disabled"}>아직 없는 영상 모두 만들기 (${todo}편)</button></div>
    <div class="muted">원본 화면 대신 어두운 배경에 설교 제목과 소리에 맞춰 움직이는 이퀄라이저를 보여 주고, 소리는 영상 싱크 없이 문장을 원래 속도로 이은 더빙 음성입니다. 한 편씩 만들며 1시간 설교에 약 11분 걸립니다. 다 만들면 구글 드라이브의 결과 폴더에 올립니다.</div>
    <label class="muted" style="display:block;margin-top:8px"><input type="checkbox" id="svAuto" ${d.auto?"checked":""}> 내보내기가 끝나면 자동으로 만들기</label>`;
  const a=document.activeElement;
  if(!(a&&a.id==="svAuto")&&$("#svTop").innerHTML!==top){$("#svTop").innerHTML=top;
    $("#svAll").onclick=async()=>{if(!confirm(`음성 영상이 없는 ${todo}편을 모두 대기열에 넣습니다. 한 편에 약 11분 걸립니다.`))return;await api("/api/sleep","POST",{action:"all"});svList();};
    $("#svAuto").onchange=e=>api("/api/sleep","POST",{auto:e.target.checked});}
  const items=d.items.filter(x=>SV.filter==="all"||svStage(x)===SV.filter);
  const html=items.length?items.map(svRow).join(""):`<li class="muted">해당하는 영상이 없습니다.</li>`;
  // 재생 중인 영상이 있으면 그 줄은 다시 그리지 않는다
  if($("#svList").innerHTML!==html){
    const playing=SV.open&&document.querySelector(`#svList li[data-id="${CSS.escape(SV.open)}"] video`);
    if(playing&&!playing.paused){items.forEach(x=>{if(x.dir!==SV.open){const li=document.querySelector(`#svList li[data-id="${CSS.escape(x.dir)}"]`);if(li)li.outerHTML=svRow(x);}});}
    else $("#svList").innerHTML=html;
  }
}
function svRow(x){
  const P=p=>`/api/p/${encodeURIComponent(x.dir)}/sleep${p}`;
  const st=x.status==="rendering"?`<span class="badge ok">만드는 중</span> <span class="muted">${esc(x.msg||"")}</span>`
    :x.status==="queued"?`<span class="badge">대기${x.ahead?` (앞에 ${x.ahead}편)`:""}</span>`
    :x.status==="error"?`<span class="badge bad">실패</span> <span class="muted" style="color:var(--bad)">${esc((x.error||"").slice(0,150))}</span>`
    :x.has_file?`<span class="badge ok">완성</span> <span class="muted">${x.length?fmt(x.length)+" · ":""}${x.size?Math.round(x.size/2**20)+"MB · ":""}${x.rendered?when(x.rendered):""}${x.drive&&x.drive.folder?" · 드라이브에 올림":x.drive&&x.drive.error?" · 드라이브 실패":""}</span>`
    :`<span class="badge">아직 없음</span>`;
  const voice=x.voice_done?"":` <span class="badge warn" title="음성이 없는 문장은 빠집니다">음성 ${x.tts}/${x.sentences}</span>`;
  const busy=x.status==="queued"||x.status==="rendering";
  const y=x.youtube||{};
  const yt=y.status==="done"?`<a href="${esc(y.url)}" target="_blank" style="color:var(--accent)">▶ 유튜브 (비공개)</a>`
    :y.status==="queued"||y.status==="uploading"?`<span class="muted">${esc(y.msg||"유튜브 대기 중")}${y.progress?` ${Math.round(y.progress*100)}%`:""}</span> <button class="small" data-act="youtube/cancel">취소</button>`
    :x.has_file&&!busy&&SV.d.yt?`${y.status==="error"?`<span class="muted" style="color:var(--bad)" title="${esc(y.error||"")}">유튜브 실패</span> `:""}<button class="small" data-act="youtube">유튜브 올리기</button>`:"";
  const btns=[busy?`<button class="small" data-act="cancel">${x.status==="rendering"?"중단":"대기 취소"}</button>`
      :`<button class="small ${x.has_file?"":"primary"}" data-act="">${x.has_file?"다시 만들기":"만들기"}</button>`,
    x.has_file?`<button class="small" data-play>${SV.open===x.dir?"닫기":"▶ 재생"}</button><a href="${P("/video?dl=1")}" download style="color:var(--accent)">내려받기</a>`:"",yt].filter(Boolean).join(" ");
  const bar=x.status==="rendering"?`<div class="pjob" style="justify-content:flex-start;margin-top:4px"><div class="bar"><i style="width:${Math.round((x.progress||0)*100)}%"></i></div><span class="time">${Math.round((x.progress||0)*100)}%</span></div>`:"";
  const vid=SV.open===x.dir&&x.has_file?`<div style="flex-basis:100%"><video controls preload="metadata" src="${P(`/video?v=${Math.round(x.rendered||0)}`)}"></video></div>`:"";
  return `<li data-id="${esc(x.dir)}"><div class="pleft"><div>${esc(x.name)} ${st}${voice}</div>${bar}</div><div class="pright row" style="margin:0;justify-content:flex-end">${btns}</div>${vid}</li>`;
}
$("#svList").addEventListener("click",async e=>{
  const li=e.target.closest("li[data-id]");if(!li)return;const id=li.dataset.id,x=SV.d.items.find(i=>i.dir===id);
  if(e.target.matches("[data-play]")){SV.open=SV.open===id?null:id;li.outerHTML=svRow(x);return;}
  const b=e.target.closest("[data-act]");if(!b)return;
  const act=b.dataset.act;
  if(act==="cancel"&&x.status==="rendering"&&!confirm("만들던 음성 영상을 멈출까요?"))return;
  if(act===""&&x.has_file&&!confirm("음성 영상을 다시 만듭니다. 약 11분 걸립니다."))return;
  try{await api(`/api/p/${encodeURIComponent(id)}/sleep${act?"/"+act:""}`,"POST",{});}catch(err){alert(err.message);}
  svList();
});
