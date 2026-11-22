import {useState} from 'react';
import {Film,Image,KeyRound,ExternalLink,CheckCircle2} from 'lucide-react';
import type {Settings,State} from './types';
import './model-roles.css';

type Props={form:Settings;state:State;change:(key:string,value:unknown)=>void;saveKey:(provider:string,key:string)=>Promise<void>;notify:(message:string,error?:boolean)=>void};
const ark='https://ark.cn-beijing.volces.com/api/v3';
export function ModelRoles({form,state,change,saveKey,notify}:Props){
 const [key,setKey]=useState(''),[saving,setSaving]=useState(false);
 const presets=state.model_workflow?.recommendations||[];
 const apply=(role:string,model:string)=>{
  if(role==='image'){
   for(const [k,v]of Object.entries({image_provider:'ark',image_provider_url:ark,image_key_env:'ARK_API_KEY',image_protocol:'ark_images',image_reference_mode:'ark_images',image_model:model,image_size:'2K'}))change(k,v);
   if(model==='doubao-seedream-5-0-flash-260915')change('image_price',.12);
  }else if(role==='video'){
   for(const [k,v]of Object.entries({video_provider:'ark',video_provider_url:ark,video_key_env:'ARK_API_KEY',video_model:model,video_resolution:'720p',video_price:1.0}))change(k,v);
  }
  notify('已填入用途配置；请核对参考单价、保存连接并自行启用真实生成。');
 };
 const ready=state.providers.find(p=>p.id==='ark')?.key_available;
 const imageProvider=form.image_provider_url?(form.image_provider||'custom'):'inherit';
 return <div className="mr-workflow">
  <section className="mc-card mr-recommend"><h2>按工作环节选择模型</h2><p>看图、出图和生成视频是三种不同能力。当前推荐基于官方公开文档，具体权限以账户目录为准。</p><div className="mr-recommend-grid">{presets.map(p=><article key={p.role+p.model}><span>{({text:'沟通 / 剧本',vision:'视觉理解',image:'角色 / 分镜画面',video:'动态镜头'} as Record<string,string>)[p.role]}</span><h3>{p.name}</h3><code>{p.model}</code><p>{p.description}</p><div>{['image','video'].includes(p.role)&&<button className="mc-button" onClick={()=>apply(p.role,p.model)}>填入此用途</button>}<a href={p.source} target="_blank" rel="noreferrer">官方文档 <ExternalLink size={12}/></a></div></article>)}</div></section>
  <div className="mr-connections">
   <section className="mc-card"><div className="mr-card-title"><Image size={21}/><h2>图片生成连接</h2></div><p>只配置生图模型；千问VL等看图模型不能填在这里。</p>
    <label>图片供应商<select value={imageProvider} onChange={e=>{const p=e.target.value;if(p==='inherit'){change('image_provider_url','');change('image_provider','');change('image_key_env','');return;}const profile=state.providers.find(x=>x.id===p);change('image_provider',p);change('image_provider_url',profile?.base_url||ark);change('image_key_env',profile?.key_env||'MANJU_API_KEY');change('image_protocol',p==='ark'?'ark_images':'openai_images');change('image_reference_mode',p==='ark'?'ark_images':'openai_edits');}}><option value="inherit">沿用默认文本供应商（需支持生图）</option><option value="ark">火山方舟 · Seedream</option><option value="openai">OpenAI Images</option><option value="custom">自定义兼容图片接口</option></select></label>
    {!!form.image_provider_url&&<label>生图 API 地址<input value={form.image_provider_url} onChange={e=>change('image_provider_url',e.target.value)}/></label>}
    <label>图片模型 ID<input aria-label="独立图片模型" value={form.image_model} onChange={e=>change('image_model',e.target.value)} placeholder="使用推荐或填写账户实际开放的模型 / 接入点"/></label>
    <label>参考图协议<select value={form.image_protocol||'openai_images'} onChange={e=>{change('image_protocol',e.target.value);change('image_reference_mode',e.target.value==='ark_images'?'ark_images':'openai_edits');}}><option value="ark_images">Seedream 原生图片参考</option><option value="openai_images">OpenAI Images / Edits</option></select></label>
    <label>Seedream 输出尺寸<select value={form.image_size||'2K'} onChange={e=>change('image_size',e.target.value)}><option>1K</option><option>1.5K</option><option>2K</option></select></label>
    <p>参考单价与总预算统一在“用途与预算”设置。</p><label className="mr-check"><input type="checkbox" checked={form.image_watermark!==false} onChange={e=>change('image_watermark',e.target.checked)}/>Seedream 输出可见水印</label>
   </section>
   <section className="mc-card"><div className="mr-card-title"><Film size={21}/><h2>动态视频连接</h2></div><p>Seedance 首帧生成动态镜头，台词由独立配音混入，默认不生成视频原声。</p>
    <label>视频 API 地址<input value={form.video_provider_url||ark} onChange={e=>change('video_provider_url',e.target.value)}/></label>
    <label>即梦 Seedance 2.5 模型 ID<input aria-label="独立视频模型" value={form.video_model||'doubao-seedance-2-5-260628'} onChange={e=>change('video_model',e.target.value)} placeholder="默认标准版；也可填写账号实际开放的接入点"/></label>
    <label>分辨率<select value={form.video_resolution||'720p'} onChange={e=>change('video_resolution',e.target.value)}><option>480p</option><option>720p</option><option>1080p</option><option>4k</option></select><small>2.5 Flash 仅支持480p、720p；首帧模式使用自适应画幅。</small></label>
    <label>最长等待（秒）<input type="number" min="30" max="3600" value={form.video_timeout||1200} onChange={e=>change('video_timeout',Number(e.target.value))}/></label>
    <label className="mr-check"><input type="checkbox" checked={form.video_watermark!==false} onChange={e=>change('video_watermark',e.target.checked)}/>视频可见水印</label>
    <div className="mc-note">提交成功后保存任务编号；超时、断网和重启后查询原任务。结果未确认时不会自动重新创建。</div>
   </section>
  </div>
  <section className="mc-card"><div className="mr-card-title"><KeyRound size={20}/><h2>火山图片与视频密钥</h2><span>{ready?<><CheckCircle2 size={15}/>已保存</>:'尚未保存'}</span></div><p>图片和视频可共用同一账户的方舟密钥，不覆盖 DeepSeek 或其他供应商的密钥。</p><div className="mr-key"><input type="password" autoComplete="new-password" aria-label="火山图片视频密钥" value={key} onChange={e=>setKey(e.target.value)} placeholder={ready?'留空保留已保存密钥':'输入火山方舟API Key'}/><button className="mc-button" disabled={saving||!key.trim()} onClick={async()=>{setSaving(true);try{await saveKey('ark',key.trim());setKey('');notify('火山密钥已加密保存，尚未发起生成。');}catch(e){notify((e as Error).message,true);}finally{setSaving(false);}}}>{saving?'正在保存':'加密保存密钥'}</button></div></section>
 </div>;
}
