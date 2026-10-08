/* ---------- 쇼츠 화면 ----------
   왼쪽: 음성을 다 만든 영상 목록. 오른쪽: 고른 영상의 쇼츠 카드.
   카드에서 제목, 구간(문장 단위), 강조 구절, 가로 위치를 고치면 바로 저장되고, 미리 보기 그림으로 확인한 뒤
   "다시 만들기"를 누르면 영상에 반영된다. index.html의 $, api, esc, fmt, S, showView, openProject를 쓴다. */
const SH={pid:null,d:null,poll:null,listPoll:null,listBusy:false,busy:false,pt:{},pv:0};
const SP=path=>`/api/p/${encodeURIComponent(SH.pid)}/shorts${path||""}`;

async function showShorts(pid){
  stopPoll();S.pid=null;S.d=null;
  showView("shorts");$("#steps").innerHTML="";$("#title").textContent="쇼츠";
  if(!pid&&!SH.pid)history.replaceState(null,"","#shorts");
  try{S.yt=await api("/api/youtube/status");}catch(e){}
  await shList();
  clearInterval(SH.listPoll);
  SH.listPoll=setInterval(async()=>{if(S.view!=="shorts"){clearInterval(SH.listPoll);SH.listPoll=null;return;}
    if(SH.listBusy)return;SH.listBusy=true;try{await shList();}catch(e){}finally{SH.listBusy=false;}},5000);
  if(pid||SH.pid)await shOpen(pid||SH.pid);
}
$("#btnShorts").onclick=()=>showShorts();
$("#shAuto").onchange=e=>api("/api/shorts","POST",{auto:e.target.checked});

async function shList(){
  const r=await api("/api/shorts");
  $("#shAuto").checked=!!r.auto;
  const html=r.items.length?r.items.map(x=>{
    const st=x.busy?`<span class="badge ok">${x.suggest==="queued"||x.suggest==="running"?"후보 고르는 중":"만드는 중"}</span>`
      :x.error?`<span class="badge bad">후보 고르기 실패</span>`
      :x.count?`<span class="badge">${x.done}/${x.count}개 완성${x.uploaded?` · 유튜브 ${x.uploaded}`:""}</span>`
      :`<span class="badge">아직 없음</span>`;
    return `<li data-id="${esc(x.dir)}" class="${x.dir===SH.pid?"sel":""}"><div>${esc(x.name)}</div><div>${st}${x.voice_done?"":' <span class="badge warn">음성이 덜 됨</span>'}</div></li>`;}).join("")
    :`<li class="muted">음성까지 만든 영상이 없습니다.</li>`;
  if($("#shList").innerHTML!==html){$("#shList").innerHTML=html;
    document.querySelectorAll("#shList li[data-id]").forEach(li=>li.onclick=()=>shOpen(li.dataset.id));}
}

async function shOpen(pid){
  SH.pid=pid;SH.pt={};history.replaceState(null,"","#shorts/"+encodeURIComponent(pid));
  document.querySelectorAll("#shList li[data-id]").forEach(li=>li.classList.toggle("sel",li.dataset.id===pid));
  $("#shMain").innerHTML=`<div class="card muted">불러오는 중…</div>`;
  let d;try{d=await api(SP());}catch(e){$("#shMain").innerHTML=`<div class="err">${esc(e.message)}</div>`;return;}
  if(SH.pid!==pid)return;
  SH.d=d;shRender();
  clearInterval(SH.poll);SH.poll=setInterval(shTick,2500);
}
async function shTick(){
  if(S.view!=="shorts"||!SH.pid){clearInterval(SH.poll);SH.poll=null;return;}
  if(SH.busy)return;SH.busy=true;
  try{const pid=SH.pid,v=await api(SP("?lite=1"));if(pid===SH.pid)shMerge(v);}catch(e){}finally{SH.busy=false;}
}
// 주기적으로 받은 상태를 반영한다. 카드가 늘거나 줄면 다시 그리고(글을 입력하는 중이면 다음 번에), 아니면 상태만 바꾼다
function shMerge(v){
  const old=SH.d,ids=x=>x.items.map(i=>i.id).join(",");
  v.sentences=old.sentences;
  if(ids(v)!==ids(old)){const a=document.activeElement;if(a&&a.closest&&a.closest("#shMain")&&a.matches("input"))return;SH.d=v;shRender();return;}
  SH.d=v;
  const h=shHead();if($("#shHead").innerHTML!==h)$("#shHead").innerHTML=h;
  v.items.forEach((it,k)=>{const o=old.items[k],card=document.querySelector(`.shcard[data-id="${it.id}"]`);if(!card)return;
    if(shMode(it)!==shMode(o)||it.rendered!==o.rendered)card.querySelector(".shvid").innerHTML=shVid(it);
    const st=card.querySelector(".shstat"),sh=shStat(it);if(st.innerHTML!==sh)st.innerHTML=sh;
    const b=card.querySelector(".shbtns"),bh=shBtns(it);if(b.innerHTML!==bh)b.innerHTML=bh;});
}

function shRender(){
  const d=SH.d;
  $("#shMain").innerHTML=`<div class="card" style="margin-bottom:12px" id="shHead">${shHead()}</div>
    ${d.items.length?d.items.map(shCard).join(""):'<div class="card muted">아직 쇼츠가 없습니다. "Claude로 후보 만들기"를 누르거나 "직접 추가"로 구간을 정하세요.</div>'}`;
}
function shHead(){
  const d=SH.d,g=d.suggest||{},busy=g.status==="queued"||g.status==="running";
  const st=g.status==="running"?`<div class="job" style="margin:8px 0 0"><span>${esc(g.msg||"Claude가 고르는 중")}</span></div>`
    :g.status==="queued"?`<div class="muted" style="margin-top:6px">후보 고르기 대기 중${g.ahead?` (앞에 ${g.ahead}개)`:""}${g.msg?" · "+esc(g.msg):""}</div>`
    :g.status==="error"?`<div class="err" style="margin:8px 0 0">후보를 고르지 못했습니다: ${esc(g.error)}</div>`:"";
  return `<div class="row" style="justify-content:space-between">
      <div><strong>${esc(d.name)}</strong> <span class="muted">${d.items.length?`쇼츠 ${d.items.length}개`:""}</span></div>
      <span class="row"><button class="small" id="shOpenProj">프로젝트 열기</button><button class="small" id="shNew">직접 추가</button>
      <button class="primary small" id="shSuggest" ${busy?"disabled":""}>${d.items.length?"Claude로 후보 3개 더":"Claude로 후보 3개 만들기"}</button></span></div>
    <div class="muted">제목과 구간, 강조를 고치면 왼쪽에 미리 보기 그림이 나오고, "다시 만들기"를 눌러야 영상에 반영됩니다. 강조는 글을 마우스로 고른 뒤 "선택한 글 강조"를 누르고, 노란 글을 누르면 뺍니다. 문장을 누르면 그 장면을 봅니다.</div>${st}`;
}

/* ----- 카드 ----- */
function shSeg(it){const ss=SH.d.sentences;return {ss,a:ss.findIndex(s=>s.id===it.start),b:ss.findIndex(s=>s.id===it.end)};}
// 왼쪽 칸: 고친 내용이 반영된 영상이 있으면 영상, 아니면 지금 설정의 미리 보기 그림
const shMode=it=>it.has_file&&!it.dirty?"video":it.invalid?"none":"img";
function shVid(it){
  const m=shMode(it);
  if(m==="video")return `<video controls preload="metadata" playsinline src="${SP(`/${it.id}/video?v=${Math.round(it.rendered||0)}`)}"></video>`;
  if(m==="none")return `<div style="padding:12px">${esc(it.invalid)}</div>`;
  const t=SH.pt[it.id];
  return `<div style="position:relative;width:100%;height:100%"><div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:12px">미리 보기를 그리는 중…</div>
    <img style="position:relative;width:100%;height:100%;object-fit:contain" alt="" src="${SP(`/${it.id}/frame?v=${SH.pv}${t!=null?"&t="+t.toFixed(2):""}`)}" onerror="this.style.display='none'"></div>`;
}
function shStat(it){
  const len=it.invalid?`<span class="badge bad">${esc(it.invalid)}</span>`
    :`<span class="time" title="더빙 영상에서의 시각">${fmt(it.at)} – ${fmt(it.at+it.len)} · ${Math.round(it.len)}초</span>${it.len>60?' <span class="badge warn" title="쇼츠는 3분까지 올릴 수 있지만 짧을수록 좋습니다">60초 넘음</span>':""}`;
  let s;
  if(it.status==="rendering")s=`<span class="badge ok">만드는 중</span><span class="shbar"><i style="width:${Math.round((it.progress||0)*100)}%"></i></span><span class="muted">${esc(it.msg||"")}</span>`;
  else if(it.status==="queued")s=`<span class="badge">만들기 대기${it.ahead?` (앞에 ${it.ahead}개)`:""}</span>`;
  else if(it.status==="error")s=`<span class="badge bad">실패</span> <span class="muted" style="color:var(--bad)">${esc((it.error||"").slice(0,200))}</span>`;
  else if(it.has_file&&it.dirty)s=`<span class="badge warn">고친 내용 반영 안 됨</span>`;
  else if(it.has_file)s=`<span class="badge ok">완성</span>${it.drive&&it.drive.folder?' <span class="muted">드라이브에 올림</span>':it.drive&&it.drive.error?` <span class="muted" style="color:var(--bad)" title="${esc(it.drive.error)}">드라이브 올리기 실패</span>`:""}`;
  else s=`<span class="badge">아직 안 만듦</span>`;
  return `<b>#${it.id}</b> ${len} ${s}`;
}
function shBtns(it){
  const busy=it.status==="queued"||it.status==="rendering";
  const b=[`<button class="${!it.has_file||it.dirty?"primary ":""}small" data-render ${busy||it.invalid?"disabled":""}>${it.has_file?"다시 만들기":"만들기"}</button>`];
  if(it.has_file)b.push(`<a href="${SP(`/${it.id}/video?dl=1`)}" download style="color:var(--accent)">내려받기</a>`);
  b.push(shYt(it,busy));
  b.push(`<span style="flex:1"></span><button class="small" data-del>삭제</button>`);
  return b.join(" ");
}
function shYt(it,busy){
  const y=it.youtube||{};
  if(y.status==="done")return `<a href="${esc(y.url)}" target="_blank" style="color:var(--accent)">▶ 유튜브 쇼츠 (비공개)</a>`;
  if(y.status==="queued"||y.status==="uploading")return `<span class="muted">${esc(y.msg||"유튜브 대기 중")}${y.status==="uploading"&&y.progress?` ${Math.round(y.progress*100)}%`:""}</span> <button class="small" data-ytc>취소</button>`;
  const err=y.status==="error"?`<span class="muted" style="color:var(--bad)" title="${esc(y.error||"")}">유튜브 실패: ${esc((y.error||"").slice(0,80))}</span> `:"";
  if(!(S.yt&&S.yt.connected))return err;
  const ok=it.has_file&&!it.dirty&&!busy;
  return err+`<button class="small" data-yt ${ok?"":"disabled"} title="${ok?"비공개로 올립니다":"영상을 만든 뒤 올릴 수 있습니다"}">${y.status==="error"?"유튜브 다시 올리기":"유튜브 올리기"}</button>`;
}
function shMark(text,ph,sid){
  const f=new Array(text.length).fill(false);
  ph.forEach(p=>{const i=text.indexOf(p);if(i>=0)for(let k=i;k<i+p.length;k++)f[k]=true;});
  let out="",i=0;
  while(i<text.length){let j=i;while(j<text.length&&f[j]===f[i])j++;const part=esc(text.slice(i,j));
    out+=f[i]?`<mark data-sid="${sid}" data-a="${i}" data-b="${j}" title="누르면 강조를 뺍니다">${part}</mark>`:part;i=j;}
  return out;
}
function shText(it){
  const {ss,a,b}=shSeg(it);if(a<0||b<0)return '<span class="muted">문장을 찾지 못했습니다</span>';
  const ctx=(s,lab)=>s?`<span class="ctx">${lab}: ${esc(s.text)}</span>`:"";
  return ctx(ss[a-1],"앞 문장")+ss.slice(a,b+1).map(s=>`<span class="shs" data-sid="${s.id}">${shMark(s.text,(it.emph||{})[s.id]||[],s.id)}</span>`).join(" ")+ctx(ss[b+1],"다음 문장");
}
function shCard(it){
  const x=Math.round((it.xpos==null?0.5:it.xpos)*100);
  return `<div class="shcard" data-id="${it.id}">
    <div class="shvid">${shVid(it)}</div>
    <div class="shed">
      <div class="row shstat">${shStat(it)}</div>
      <div class="shtitle"><input data-title="0" value="${esc(it.title[0]||"")}" placeholder="제목 첫 줄 (흰색)"><input data-title="1" value="${esc(it.title[1]||"")}" placeholder="제목 둘째 줄 (노란색)"></div>
      <div class="row shrange"><span class="muted">시작</span><button class="small" data-mv="start:-1" title="앞 문장부터">◀</button><button class="small" data-mv="start:1" title="다음 문장부터">▶</button>
        <span class="muted" style="margin-left:8px">끝</span><button class="small" data-mv="end:-1" title="한 문장 덜">◀</button><button class="small" data-mv="end:1" title="한 문장 더">▶</button>
        <span class="muted" style="margin-left:8px">가로 위치</span><input type="range" min="0" max="100" step="5" value="${x}" data-xpos style="width:120px" title="${x}%"></div>
      <div class="shtext">${shText(it)}</div>
      <div class="row"><button class="small" data-emph>선택한 글 강조</button><span class="muted">${esc(it.reason||"")}</span></div>
      <div class="row shbtns">${shBtns(it)}</div>
    </div></div>`;
}
// 요청 뒤 받은 목록으로 바꾼다. id가 있고 카드 수가 같으면 그 카드만 다시 그린다
async function shAct(url,method,body,id){
  const v=await api(url,method,body);v.sentences=SH.d.sentences;
  const same=v.items.map(i=>i.id).join(",")===SH.d.items.map(i=>i.id).join(",");SH.d=v;SH.pv++;
  const card=id!=null&&document.querySelector(`.shcard[data-id="${id}"]`);
  if(same&&card){card.outerHTML=shCard(v.items.find(i=>i.id===id));$("#shHead").innerHTML=shHead();}
  else shRender();
}

/* ----- 카드 조작 ----- */
const shNode=n=>n&&(n.nodeType===1?n:n.parentElement);
$("#shMain").addEventListener("mousedown",e=>{if(e.target.matches("[data-emph]"))e.preventDefault();});  // 버튼을 눌러도 고른 글이 풀리지 않게
$("#shMain").addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.matches("[data-title]"))e.target.blur();});
$("#shMain").addEventListener("click",async e=>{
  const t=e.target,card=t.closest(".shcard"),id=card?+card.dataset.id:null,it=card&&SH.d.items.find(x=>x.id===id);
  try{
    if(t.id==="shSuggest")return await shAct(SP("/suggest"),"POST",{});
    if(t.id==="shOpenProj")return openProject(SH.pid);
    if(t.id==="shNew"){const v=prompt("더빙 영상에서 쇼츠를 시작할 시각을 적으세요 (예: 12:30)");if(!v)return;
      const at=v.trim().split(":").reduce((a,x)=>a*60+Number(x),0);if(!isFinite(at))return alert("시각을 알아보지 못했습니다.");
      return await shAct(SP("/new"),"POST",{at});}
    if(!it)return;
    if(t.matches("[data-mv]")){const [k,dl]=t.dataset.mv.split(":"),{ss,a,b}=shSeg(it),i=(k==="start"?a:b)+(+dl);
      if(i<0||i>=ss.length||(k==="start"&&i>b)||(k==="end"&&i<a))return;
      return await shAct(SP("/"+id),"POST",{[k]:ss[i].id},id);}
    if(t.matches("mark[data-sid]")){const sid=t.dataset.sid,s=SH.d.sentences.find(x=>x.id==sid),A=+t.dataset.a,B=+t.dataset.b;
      const emph=Object.assign({},it.emph);emph[sid]=(emph[sid]||[]).filter(p=>{const i=s.text.indexOf(p);return i<0||i+p.length<=A||i>=B;});
      return await shAct(SP("/"+id),"POST",{emph},id);}
    if(t.matches("[data-emph]")){const sel=getSelection(),txt=sel.toString().replace(/\s+/g," ").trim();
      const sa=shNode(sel.anchorNode),sb=shNode(sel.focusNode),ea=sa&&sa.closest(".shs"),eb=sb&&sb.closest(".shs");
      if(!txt||!ea||ea!==eb||!card.contains(ea))return alert("이 카드의 글에서 강조할 부분을 한 문장 안에서 마우스로 고른 뒤 누르세요.");
      const sid=ea.dataset.sid,s=SH.d.sentences.find(x=>x.id==sid);
      if(!s.text.includes(txt))return alert("고른 글을 문장에서 찾지 못했습니다.");
      const emph=Object.assign({},it.emph);emph[sid]=(emph[sid]||[]).concat([txt]);sel.removeAllRanges();
      return await shAct(SP("/"+id),"POST",{emph},id);}
    const sn=t.closest(".shs");
    if(sn&&!it.invalid){const s=SH.d.sentences.find(x=>x.id==sn.dataset.sid),at=Math.max(0,s.t-it.at+Math.min(1,s.d/2));
      const v=card.querySelector(".shvid video");if(v){v.currentTime=at;v.play().catch(()=>{});return;}
      SH.pt[id]=at;card.querySelector(".shvid").innerHTML=shVid(it);return;}
    if(t.matches("[data-render]"))return await shAct(SP(`/${id}/render`),"POST",{},id);
    if(t.matches("[data-del]")){if(!confirm(`쇼츠 #${id}을(를) 지울까요? 이 PC의 영상 파일도 지웁니다(구글 드라이브와 유튜브에 올린 것은 그대로 둡니다).`))return;
      return await shAct(SP("/"+id),"DELETE");}
    if(t.matches("[data-yt]"))return await shAct(SP(`/${id}/youtube`),"POST",{},id);
    if(t.matches("[data-ytc]"))return await shAct(SP(`/${id}/youtube/cancel`),"POST",{},id);
  }catch(err){alert(err.message);}
});
$("#shMain").addEventListener("change",async e=>{
  const t=e.target,card=t.closest(".shcard");if(!card)return;const id=+card.dataset.id;
  try{
    if(t.matches("[data-title]")){const ins=card.querySelectorAll("[data-title]");await shAct(SP("/"+id),"POST",{title:[ins[0].value,ins[1].value]},id);}
    else if(t.matches("[data-xpos]"))await shAct(SP("/"+id),"POST",{xpos:+t.value/100},id);
  }catch(err){alert(err.message);}
});
