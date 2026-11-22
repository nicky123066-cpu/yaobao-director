import {useState} from 'react';
import {CheckCircle2,ChevronRight,Hand} from 'lucide-react';
import type {Project,Chapter,Page} from './types';
import './manual-workflow.css';

export function ManualWorkflow({project,chapter,navigate}:{project:Project;chapter:Chapter;navigate:(page:Page)=>void}){
 const [chosen,setChosen]=useState('story');
 const shots=project.shots.filter(s=>s.chapter_id===chapter.id&&!s.stale);
 const steps=[
  {id:'story',page:'story',title:'保存剧本',note:'编写、导入或手动改写',done:!!chapter.body.trim()},
  {id:'assets',page:'assets',title:'角色与场景',note:'提取资产、上传或生成定妆',done:project.assets.length>0},
  {id:'frames',page:'shots',title:'分镜与首帧',note:'编译、修改、逐镜生成画面',done:shots.length>0&&shots.every(s=>s.image)},
  {id:'voice',page:'voice',title:'角色配音',note:'选择音色、生成并试听',done:shots.length>0&&shots.every(s=>!s.dialogue||s.audio)},
  {id:'videos',page:'shots',title:'动态镜头',note:'选好首帧后手动生成或导入',done:shots.length>0&&shots.every(s=>s.video)},
  {id:'export',page:'export',title:'合成导出',note:'检查素材、点击合成、下载',done:false}
 ];
 return <section className="manual-workflow" aria-label="手动制作流程"><div className="manual-workflow-heading"><Hand size={15}/><b>手动制作</b><span>每步由你点击执行；完成后不会自动进入下一步</span></div><div className="manual-workflow-steps">{steps.map((step,index)=><button key={step.id} className={chosen===step.id?'selected':''} onClick={()=>{setChosen(step.id);navigate(step.page as Page)}}><span className="manual-step-index">{step.done?<CheckCircle2 size={17}/>:String(index+1).padStart(2,'0')}</span><span><b>{step.title}</b><small>{step.note}</small></span><ChevronRight size={13}/></button>)}</div></section>
}
