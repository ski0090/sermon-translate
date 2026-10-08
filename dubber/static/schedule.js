/* ---------- 스케줄 화면 ----------
   날마다 자동 작업(자동 진행의 자막 읽기·문장 정리, 쇼츠 자동 후보)이 쓸 수 있는 Claude 사용량(5시간·주간 %)을
   달력에서 정한다. 정하지 않은 날은 기본값을 쓴다. index.html의 $, api, esc, S, showView, when을 쓴다. */
const SC={d:null,y:null,m:null,sel:new Set(),last:null,poll:null};
const scPad=n=>String(n).padStart(2,"0");
const scKey=(y,m,d)=>`${y}-${scPad(m+1)}-${scPad(d)}`;
const scLabel=k=>{const [y,m,d]=k.split("-").map(Number);const w="일월화수목금토"[new Date(y,m-1,d).getDay()];return `${m}/${d}(${w})`;};

async function showSchedule(){
  stopPoll();S.pid=null;S.d=null;
  showView("sched");$("#steps").innerHTML="";$("#title").textContent="스케줄";
  history.replaceState(null,"","#schedule");
  if(SC.y==null){const t=new Date();SC.y=t.getFullYear();SC.m=t.getMonth();}
  try{SC.d=await api("/api/schedule");}catch(e){$("#scTop").innerHTML=`<div class="err">${esc(e.message)}</div>`;return;}
  scRender();
  clearInterval(SC.poll);
  SC.poll=setInterval(async()=>{if(S.view!=="sched"){clearInterval(SC.poll);SC.poll=null;return;}
    try{SC.d=await api("/api/schedule");scTopRender();}catch(e){}},30000);
}
$("#btnSched").onclick=()=>showSchedule();

function scRender(){scTopRender();scCalRender();scSelRender();}
function scTopRender(){
  const d=SC.d,L=d.limits,u=d.usage;
  const pct=x=>x==null?"모름":Math.round(x*100)+"%";
  const age=d.usage_t?Math.round((Date.now()/1000-d.usage_t)/60):null;
  const st=d.pause?`<span class="badge warn">자동 작업 쉬는 중</span> <span class="muted">${esc(d.pause.reason)} ${when(d.pause.until)}까지</span>`
    :`<span class="badge ok">자동 작업 가능</span>`;
  const html=`<div class="row" style="justify-content:space-between;margin:0"><strong>오늘 ${scLabel(d.today)} 한도: 5시간 ${L.five_hour}% · 주간 ${L.seven_day}%</strong>
      <span class="muted">지금 사용량: 5시간 ${pct(u.five_hour.utilization)} · 주간 ${pct(u.seven_day.utilization)}${age!=null?` (${age<1?"방금":age<60?age+"분 전":Math.round(age/60)+"시간 전"} 기준)`:""}</span></div>
    <div class="row">${st}</div>
    <div class="muted">자동 진행(자막 읽기·문장 정리)과 쇼츠 자동 후보 고르기는 그날의 Claude 사용량이 한도에 닿으면 쉬고, 사용량이 초기화되거나 한도가 더 높은 날이 되면 이어 갑니다. 0%로 정한 날은 자동 작업을 하지 않습니다. 화면에서 직접 누른 작업은 한도와 상관없이 합니다. 사용량은 마지막 Claude 호출 때의 값입니다(위의 "확인"으로 새로 읽습니다).</div>
    <div class="row" style="margin-top:10px">기본 한도 <label>5시간 <input type="number" min="0" max="100" step="5" id="scDef5" value="${d.default.five_hour}" style="width:70px">%</label>
      <label>주간 <input type="number" min="0" max="100" step="5" id="scDef7" value="${d.default.seven_day}" style="width:70px">%</label>
      <button class="small" id="scDefSave">기본값 저장</button><span class="muted">달력에서 정하지 않은 날에 씁니다.</span></div>`;
  const a=document.activeElement;if(a&&(a.id==="scDef5"||a.id==="scDef7"))return;  // 입력 중이면 덮지 않는다
  $("#scTop").innerHTML=html;
  $("#scDefSave").onclick=async()=>{try{SC.d=await api("/api/schedule","POST",{default:{five_hour:+$("#scDef5").value,seven_day:+$("#scDef7").value}});scRender();}catch(e){alert(e.message);}};
}
// 주간 사용량이 초기화되는 날(다음 초기화 시각부터 7일마다)
function scResets(){
  const r=SC.d.usage.seven_day.resetsAt;if(!r)return {};
  const out={};for(let k=0;k<10;k++){const t=new Date((r+k*7*86400)*1000);out[scKey(t.getFullYear(),t.getMonth(),t.getDate())]=t.toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"});}
  return out;
}
function scCalRender(){
  const d=SC.d,y=SC.y,m=SC.m,first=new Date(y,m,1).getDay(),n=new Date(y,m+1,0).getDate(),resets=scResets();
  let cells="일월화수목금토".split("").map((w,i)=>`<div class="cw ${i===0?"sun":i===6?"sat":""}">${w}</div>`).join("");
  for(let i=0;i<first;i++)cells+=`<div class="cd blank"></div>`;
  for(let day=1;day<=n;day++){
    const k=scKey(y,m,day),v=d.days[k],lim=v||d.default,wd=(first+day-1)%7;
    const cls=["cd",wd===0?"sun":wd===6?"sat":"",k<d.today?"past":"",k===d.today?"today":"",v?"set":"",SC.sel.has(k)?"sel":""].join(" ");
    cells+=`<div class="${cls}" data-day="${k}"><div class="cdn">${day}${k===d.today?' <span class="badge ok">오늘</span>':""}</div>
      <div class="cdv">5시간 ${lim.five_hour}%<br>주간 ${lim.seven_day}%</div>${resets[k]?`<div class="cdr" title="Claude 주간 사용량이 초기화되는 시각">↻ 주간 초기화 ${resets[k]}</div>`:""}</div>`;
  }
  $("#scCal").innerHTML=`<div class="row" style="justify-content:space-between;margin:0">
      <span class="row" style="margin:0"><button class="small" id="scPrev">◀</button><strong style="min-width:7em;text-align:center">${y}년 ${m+1}월</strong><button class="small" id="scNext">▶</button><button class="small" id="scToday">이번 달</button></span>
      <span class="row" style="margin:0"><button class="small" id="scWeekend">이 달 주말 고르기</button><span class="muted"><span class="badge" style="background:var(--accent2);color:var(--accent)">파란 날</span>은 따로 정한 날</span></span></div>
    <div class="cal">${cells}</div>`;
  $("#scPrev").onclick=()=>{SC.m--;if(SC.m<0){SC.m=11;SC.y--;}scCalRender();};
  $("#scNext").onclick=()=>{SC.m++;if(SC.m>11){SC.m=0;SC.y++;}scCalRender();};
  $("#scToday").onclick=()=>{const t=new Date();SC.y=t.getFullYear();SC.m=t.getMonth();scCalRender();};
  $("#scWeekend").onclick=()=>{for(let day=1;day<=n;day++){const k=scKey(y,m,day),wd=(first+day-1)%7;if((wd===0||wd===6)&&k>=d.today)SC.sel.add(k);}scCalRender();scSelRender();};
  document.querySelectorAll("#scCal .cd[data-day]").forEach(c=>c.onclick=e=>{
    const k=c.dataset.day;if(k<SC.d.today)return;
    if(e.shiftKey&&SC.last){const [a,b]=[SC.last,k].sort();for(let t=new Date(a+"T12:00");;t.setDate(t.getDate()+1)){const kk=scKey(t.getFullYear(),t.getMonth(),t.getDate());if(kk>b)break;SC.sel.add(kk);}}
    else if(SC.sel.has(k))SC.sel.delete(k);else SC.sel.add(k);
    SC.last=k;scCalRender();scSelRender();});
}
function scSelRender(){
  const days=[...SC.sel].sort();
  if(!days.length){$("#scSel").innerHTML=`<span class="muted">날짜를 누르면 고릅니다. Shift를 누른 채 누르면 그 사이의 날을 모두 고릅니다. 고른 날의 한도를 정하고 "적용"을 누르세요.</span>`;return;}
  const v=SC.d.days[days[0]]||SC.d.default;
  $("#scSel").innerHTML=`<div class="row" style="margin:0"><strong>고른 날 ${days.length}일</strong><span class="muted">${days.slice(0,8).map(scLabel).join(", ")}${days.length>8?" …":""}</span></div>
    <div class="row"><label>5시간 <input type="number" min="0" max="100" step="5" id="scV5" value="${v.five_hour}" style="width:70px">%</label>
      <label>주간 <input type="number" min="0" max="100" step="5" id="scV7" value="${v.seven_day}" style="width:70px">%</label>
      <button class="primary small" id="scApply">적용</button><button class="small" id="scReset">기본값으로</button><button class="small" id="scClear">고르기 취소</button></div>`;
  const send=async days2=>{try{SC.d=await api("/api/schedule","POST",{days:days2});SC.sel.clear();scRender();}catch(e){alert(e.message);}};
  $("#scApply").onclick=()=>send(Object.fromEntries(days.map(k=>[k,{five_hour:+$("#scV5").value,seven_day:+$("#scV7").value}])));
  $("#scReset").onclick=()=>send(Object.fromEntries(days.map(k=>[k,null])));
  $("#scClear").onclick=()=>{SC.sel.clear();scCalRender();scSelRender();};
}
