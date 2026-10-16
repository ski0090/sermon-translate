// 새 화면(Vue)이 함께 쓰는 것: API, 글 형식, 단계 계산, 공용 상태. 규칙은 지금 화면(static/index.html)과 같다
import {reactive} from "./vendor/vue.esm-browser.prod.js";

export async function api(path,method="GET",body){
  const r=await fetch(path,{method,headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
  const j=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(j.error||("오류 "+r.status));
  return j;
}
export const fmt=t=>{t=Math.max(0,t||0);const m=Math.floor(t/60),s=Math.floor(t%60);return `${m}:${String(s).padStart(2,"0")}`;};
export const when=t=>new Date(t*1000).toLocaleString("ko-KR",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"});
export const ago=t=>{const m=Math.round((Date.now()/1000-t)/60);return m<1?"방금":m<60?m+"분 전":Math.round(m/60)+"시간 전";};
export const fsize=b=>b<0?"":b>=2**30?(b/2**30).toFixed(1)+"GB":Math.max(1,Math.round(b/2**20))+"MB";

// 프로젝트 목록을 거르는 단계, 쇼츠·음성 영상 목록을 거르는 상태
export const STAGES=[["todo","진행 전"],["review","정리와 검수"],["scan","자막 읽기"],["tts","음성"],["export","내보내기"]];
export const SH_STAGES=[["todo","진행 전"],["making","만드는 중"],["done","완성"]];
export const SV_STAGES=[["todo","아직 없음"],["making","만드는 중"],["done","완성"]];
export const stageName=k=>(STAGES.find(x=>x[0]===k)||[])[1];
// AI 도구 이름(스케줄, 프로젝트 설정, AI 도구, 사용량)
export const TOOLS={claude:"Claude",codex:"Codex",agy:"Antigravity"};

// 지금 돌고 있는 작업 이름(프로젝트 단계가 아니라)
export const jobName=j=>j.queued?"음성 대기":({scan:"자막 읽기",read:"자막 읽기",tidy:"문장 정리",tts:"음성",export:"내보내기"})[j.kind]||"작업";
export const jobMsg=j=>(j.msg||"작업 중")+(j.resumed?" · 재시작 후 다시 하는 중":"");
// 프로젝트가 머문 단계: 돌고 있는 작업 > 만든 결과. 서버는 review 단계를 따로 적지 않아 문장이 있으면 정리와 검수로 본다
export function projStage(p){
  const j=p.job;
  if(j)return j.queued?"tts":({tidy:"review",tts:"tts",export:"export"})[j.kind]||"scan";
  if(p.exported||p.step==="export")return "export";
  if(p.tts||p.step==="tts")return "tts";
  if(p.sentences)return "review";
  return p.captions||p.step==="scan"?"scan":"todo";
}
export function progressText(p){
  const parts=[];
  if(p.captions)parts.push(`자막 ${p.read}/${p.captions}장`);
  if(p.sentences)parts.push(`문장 ${p.sentences}개`);
  if(p.sentences)parts.push(`음성 ${p.tts}/${p.sentences}`);
  if(p.cuts)parts.push(`잘라내기 ${p.cuts}개`);
  if(p.exported)parts.push("내보내기 완료");
  return parts.join(" · ")||"아직 자막을 읽지 않음";
}
// 드라이브 영상 하나의 상태: 진행 중 > 내려받는 중 > 이 PC의 프로젝트 > 드라이브의 결과 > 이전 작업 > 시작 전
// group은 완료·진행 중·시작 전 묶음, job이 있으면 진행 막대로, 없으면 text를 보인다
export function libState(it){
  const p=it.project;
  if(p&&p.job)return {group:"run",label:"진행 중 · "+jobName(p.job),cls:"ok",job:p.job,stage:projStage(p)};
  if(it.importing)return {group:"run",label:"내려받는 중",cls:"ok",job:it.importing,stage:"todo"};
  if(p&&p.exported)return {group:"done",label:"완료",cls:"ok",text:progressText(p),stage:"export"};
  if(p){const k=projStage(p);return {group:"run",label:stageName(k),cls:"warn",text:progressText(p),stage:k};}
  if(it.drive_done)return {group:"done",label:"완료",cls:"ok",text:"구글 드라이브에 결과 있음",stage:"export"};
  if(it.legacy)return {group:"run",label:"이전 작업 있음",cls:"warn",text:"다른 PC에서 작업한 기록이 드라이브에 있음",stage:"todo"};
  return {group:"todo",label:"시작 전",cls:"",text:fsize(it.size),stage:"todo"};
}
// 영상의 쇼츠 상태: 진행 전(아직 없음) · 만드는 중(고르거나 만드는 중, 아직 안 만든 쇼츠가 있음) · 완성
export const shStage=x=>x.busy||x.done<x.count?"making":x.count?"done":"todo";
// 영상의 음성 영상 상태: 아직 없음 · 만드는 중(대기 포함) · 완성
export const svStage=x=>x.status==="queued"||x.status==="rendering"?"making":x.has_file?"done":"todo";

// 화면 사이에 함께 쓰는 상태. route는 주소의 # 뒤(app.js), 목록은 몇 초마다 서버에서 새로 받는다.
// listFilter는 마지막으로 본 프로젝트 목록의 거르기(프로젝트를 열어도 메뉴에 표시), workName은 연 프로젝트 이름
export const store=reactive({route:{view:"projects",filter:"all"},listFilter:"all",shPid:null,workName:null,lib:null,shorts:null,sleep:null,yt:null});

export const openProject=dir=>{location.hash="#/p/"+encodeURIComponent(dir);};

// fn을 ms마다 부른다. 앞 호출이 안 끝났으면 건너뛰고 탭이 숨어 있으면 쉰다. 멈추는 함수를 돌려준다
export function every(ms,fn){
  let busy=false;
  const tick=async()=>{if(busy||document.hidden)return;busy=true;try{await fn();}catch(e){}finally{busy=false;}};
  const vis=()=>{if(!document.hidden)tick();};
  tick();const t=setInterval(tick,ms);document.addEventListener("visibilitychange",vis);
  return ()=>{clearInterval(t);document.removeEventListener("visibilitychange",vis);};
}
