import {useEffect,useRef,useState} from 'react';
import {ShoppingBag,Upload,Film,FileText,Download,Plus,Save,LoaderCircle} from 'lucide-react';
import {api,stateNames} from './types';
import type {State} from './types';
import './commerce.css';

type Draft={id:string;revision:number;name:string;price:string;selling_points:string;audience:string;cta:string;script:string;subtitles:string;mode:string;ratio:string;duration:number;start:number;media_ids:string[]};
type Media={id:string;name:string;url:string;kind:string;duration:number;audio:boolean};
type Summary={drafts:Draft[];media:Media[];ffmpeg:boolean;avatar_connected:boolean};
const empty=():Draft=>({id:'',revision:0,name:'',price:'',selling_points:'',audience:'',cta:'',script:'',subtitles:'',mode:'real',ratio:'9:16',duration:30,start:0,media_ids:[]});

export function CommerceVideos({state,refresh,notify}:{state:State;refresh:()=>Promise<void>;notify:(text:string,error?:boolean)=>void}){
 const [summary,setSummary]=useState<Summary|null>(null),[draft,setDraft]=useState<Draft>(empty),[busy,setBusy]=useState(''),[dirty,setDirty]=useState(false);
 const ready=useRef(false),files=useRef<HTMLInputElement>(null),mounted=useRef(true);
 async function load(){const value=await api<Summary>('/api/commerce');if(!mounted.current)return;setSummary(value);if(!ready.current){ready.current=true;if(value.drafts[0])setDraft(value.drafts[0]);}}
 useEffect(()=>{mounted.current=true;load().catch(e=>notify(e.message,true));const timer=setInterval(()=>load().catch(()=>{}),3000);return()=>{mounted.current=false;clearInterval(timer)}},[]);
 function change<K extends keyof Draft>(key:K,value:Draft[K]){setDraft(d=>({...d,[key]:value}));setDirty(true);}
 async function action(label:string,fn:()=>Promise<void>){if(busy)return;setBusy(label);try{await fn()}catch(e){notify((e as Error).message,true)}finally{setBusy('')}}
 async function save(){const saved=await api<Draft>('/api/commerce/save',draft);setDraft(saved);setDirty(false);await load();await refresh();return saved;}
 async function upload(selected:FileList|null){if(!selected)return;const chosen=Array.from(selected);await action('正在上传素材',async()=>{const ids=[...draft.media_ids];for(const file of chosen){if(file.size>250*1024*1024)throw Error('单个素材不能超过250MB');if(ids.length>=8)throw Error('每个带货项目最多选择8项素材');const response=await fetch('/api/commerce/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-File-Name':encodeURIComponent(file.name)},body:file});const value=await response.json();if(!response.ok)throw Error(value.error||'上传失败');ids.push(value.id);setDraft(d=>({...d,media_ids:[...ids]}));setDirty(true);}await load();notify('素材已上传，保存后可用于合成');});if(files.current)files.current.value='';}
 const jobs=state.jobs.filter(j=>j.kind==='commerce'&&j.project_id===draft.id),active=jobs.some(j=>['PENDING','RUNNING','PAUSED'].includes(j.state));
 const current=jobs.find(j=>j.state==='SUCCEEDED'&&j.result.commerce_revision===draft.revision),latest=current||jobs.find(j=>j.state==='SUCCEEDED');
 const sourceKind=draft.mode==='real'?'video':'image';
 return <section className="commerce-page">
  <div className="page-heading"><div><span className="eyebrow">COMMERCE VIDEO</span><h1>带货视频<span className="title-dot">.</span></h1><p>商品资料 → 真人素材 → 带货文案 → 合成导出。每步由你手动启动。</p></div><button className="secondary" onClick={()=>{if(dirty&&!confirm('尚有未保存资料，确定新建吗？'))return;setDraft(empty());setDirty(false)}}><Plus size={16}/>新建带货项目</button></div>
  <div className="commerce-layout"><aside className="commerce-library"><h3><ShoppingBag size={17}/>带货项目</h3>{summary?.drafts.map(item=><button key={item.id} className={item.id===draft.id?'selected':''} onClick={()=>{if(dirty&&!confirm('尚有未保存资料，确定切换吗？'))return;setDraft(item);setDirty(false)}}><b>{item.name}</b><small>{item.mode==='real'?'真人实拍':item.mode==='product'?'商品图配音':'照片口播方案'} · {item.duration} 秒</small></button>)}{!summary?.drafts.length&&<p>先填写商品资料，保存第一个带货项目。</p>}</aside>
   <div className="commerce-editor"><fieldset disabled={!!busy}>
    <section className="commerce-card"><h2>01 商品与制作方式</h2><div className="commerce-fields">
     <label>商品名称<input aria-label="商品名称" maxLength={80} value={draft.name} onChange={e=>change('name',e.target.value)}/></label>
     <label>价格 / 优惠说明<input aria-label="价格说明" maxLength={100} placeholder="填写已确认的价格，可留空" value={draft.price} onChange={e=>change('price',e.target.value)}/></label>
     <label>制作方式<select aria-label="带货制作方式" value={draft.mode} onChange={e=>change('mode',e.target.value)}><option value="real">真人实拍 · 保留原声</option><option value="product">商品图片 · 中文配音</option><option value="avatar">人物照片口播 · 待接入数字人</option></select></label>
     <label>画面比例<select aria-label="带货画面比例" value={draft.ratio} onChange={e=>change('ratio',e.target.value)}><option>9:16</option><option>16:9</option><option>1:1</option></select></label>
     <label>成片时长（秒）<input aria-label="带货时长" type="number" min={3} max={120} value={draft.duration} onChange={e=>change('duration',+e.target.value)}/></label>
     <label>真人视频起点（秒）<input aria-label="素材起点" type="number" min={0} max={3600} step={.1} disabled={draft.mode!=='real'} value={draft.start} onChange={e=>change('start',+e.target.value)}/></label>
     <label className="wide">已确认的核心卖点<textarea aria-label="商品卖点" rows={3} maxLength={2000} placeholder="材质、规格、使用场景等真实信息" value={draft.selling_points} onChange={e=>change('selling_points',e.target.value)}/></label>
     <label>适用人群 / 需求<input aria-label="适用人群" maxLength={300} value={draft.audience} onChange={e=>change('audience',e.target.value)}/></label>
     <label>结尾引导<input aria-label="结尾引导" maxLength={300} placeholder="例如：规格与实时优惠见商品页面" value={draft.cta} onChange={e=>change('cta',e.target.value)}/></label>
    </div>{draft.mode==='avatar'&&<p className="commerce-note">人物照片可用于保存出镜方案。数字人驱动和精确口型尚未接入，此方式暂不能生成口播成片。</p>}
    </section>
    <section className="commerce-card"><div className="commerce-card-head"><h2>02 出镜与商品素材</h2><button className="secondary" onClick={()=>files.current?.click()}><Upload size={15}/>上传本机素材</button></div>
     <input ref={files} type="file" hidden multiple accept="video/mp4,video/quicktime,image/png,image/jpeg,image/webp" aria-label="上传带货素材" onChange={e=>upload(e.target.files)}/>
     <p>支持MP4/MOV、PNG/JPEG/WebP，单个文件最大250MB。真人模式使用第一项勾选的视频，保留其真实声音；图片模式按所选图片顺序展示。</p>
     <div className="commerce-media">{summary?.media.map(item=><label key={item.id} className={draft.media_ids.includes(item.id)?'selected':''}><input type="checkbox" aria-label={'选择素材 '+item.name} checked={draft.media_ids.includes(item.id)} disabled={item.kind!==sourceKind||!draft.media_ids.includes(item.id)&&draft.media_ids.length>=8} onChange={e=>change('media_ids',e.target.checked?[...draft.media_ids,item.id]:draft.media_ids.filter(id=>id!==item.id))}/>{item.kind==='image'?<img src={item.url} alt={item.name}/>:<Film size={26}/>}<span><b>{item.name}</b><small>{item.kind==='video'?`${item.duration.toFixed(1)} 秒 · ${item.audio?'有原声':'无音轨'}`:'图片'}</small></span></label>)}</div>
     {!summary?.media.length&&<div className="commerce-empty">上传真人讲解视频，或商品图片开始制作。</div>}
    </section>
    <section className="commerce-card"><div className="commerce-card-head"><h2>03 带货文案与字幕</h2><button className="secondary" onClick={()=>action('正在整理文案',async()=>{const result=await api('/api/commerce/script',draft);change('script',result.script);notify('已依据商品资料整理文案，请核对后保存');})}><FileText size={15}/>按商品资料整理文案</button></div>
     <label>口播文案<textarea aria-label="带货口播文案" rows={5} maxLength={6000} value={draft.script} onChange={e=>change('script',e.target.value)}/></label><p>本地整理，不调用付费模型。真人视频保留原声，文案可供拍摄参考；商品图模式会将此文案合成本地配音。</p>
     <label>画面字幕（选填，每行一句）<textarea aria-label="带货字幕" rows={3} maxLength={2000} value={draft.subtitles} onChange={e=>change('subtitles',e.target.value)} placeholder="可填写商品卖点，按行均分显示时长"/></label><p>字幕按行均分成片时长，并非语音识别对齐；下载后请核对。</p>
    </section>
    <div className="commerce-actions"><span>{dirty?'有未保存修改':draft.id?'商品资料已保存':'尚未保存项目'}</span><button className="secondary" onClick={()=>action('正在保存',async()=>{await save();notify('带货项目已保存');})}><Save size={15}/>保存商品资料</button><button className="primary" disabled={draft.mode==='avatar'||active||!summary?.ffmpeg} onClick={()=>action('正在提交合成',async()=>{const saved=await save();await api('/api/commerce/export',{id:saved.id,revision:saved.revision,manual_action:true,idempotency_key:crypto.randomUUID()});await refresh();notify('已提交带货合成，可在任务中心查看进度');})}>{busy?<LoaderCircle className="spin" size={16}/>:<Film size={16}/>}导出带货 MP4</button></div>
   </fieldset>{busy&&<p role="status">{busy}…</p>}
   {jobs.length>0&&<section className="commerce-card"><h2>04 成片与任务</h2>{active&&<p className="commerce-note">当前有合成任务。暂停或取消可到“任务中心”操作；不会自动启动后续步骤。</p>}{jobs.slice(0,4).map(job=><p className="commerce-job" key={job.id}><b>{stateNames[job.state]||job.state}</b><span>{job.error||(job.state==='SUCCEEDED'&&job.result.commerce_revision!==draft.revision?'历史任务：商品资料已更新，请核对版本':'本机素材合成')}</span></p>)}{latest&&<><p>{latest===current&&!dirty?'当前保存版本成片':'历史版本成片；与当前资料可能不同'}</p><video src={latest.result.video} controls preload="metadata" aria-label="带货成片预览"/><div className="commerce-downloads"><a className="primary" href={latest.result.video} download><Download size={15}/>下载MP4</a><a className="secondary" href={latest.result.subtitles} download>下载字幕</a><a className="secondary" href={latest.result.report} download>制作核验记录</a></div></>}</section>}
   </div></div>
 </section>
}
