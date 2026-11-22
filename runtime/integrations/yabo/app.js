/* ============================================================
   Yabo工作台 · 交互与页面渲染
   纯前端复刻，功能页面与微信助手保持一致，品牌替换为 Yabo工作台
   ============================================================ */

/* ---------- 图标库（内联 SVG） ---------- */
const I = {
  logo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg>',
  message:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.8-.9L3 21l1.9-5.2A8.4 8.4 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></svg>',
  todo:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="4" width="16" height="17" rx="2"/><path d="M9 4V3h6v1M8 10h8M8 14h8M8 18h5"/></svg>',
  chart:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  contacts:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 11a3 3 0 1 0-2-5.2M18 20a5 5 0 0 0-2-4"/></svg>',
  customer:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M6 16c.5-1.5 1.7-2 3-2s2.5.5 3 2M14 9h4M14 13h4"/></svg>',
  phone:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>',
  person:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  book:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
  history:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/></svg>',
  reply:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M9 17l-5-5 5-5M4 12h10a6 6 0 0 1 6 6v2"/></svg>',
  account:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>',
  shield:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>',
  log:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
  setting:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  mini:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3"/></svg>',
  search:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  chev:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="m6 9 6 6 6-6"/></svg>',
  arrow:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px"><path d="m9 6 6 6-6 6"/></svg>',
  plus:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M12 5v14M5 12h14"/></svg>',
  play:'<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
  image:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>',
  mic:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/></svg>',
  link:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M10 13a5 5 0 0 0 7 .5l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
  check:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 4 4L19 6"/></svg>',
  close:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  clock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  edit:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
  copy:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
};

/* ---------- 导航配置 ---------- */
const NAV = [
  { group:'工作', items:[
    {id:'message', name:'消息中心', icon:'message'},
    {id:'todo', name:'待办处理', icon:'todo', badge:7},
    {id:'stats', name:'数据统计', icon:'chart'},
  ]},
  { group:'客户', items:[
    {id:'contacts', name:'通讯管理', icon:'contacts'},
    {id:'customers', name:'客户档案', icon:'customer'},
    {id:'call', name:'语音通话', icon:'phone'},
  ]},
  { group:'智能', items:[
    {id:'persona', name:'人设管理', icon:'person'},
    {id:'knowledge', name:'知识管理', icon:'book'},
    {id:'history', name:'历史学习', icon:'history'},
  ]},
  { group:'系统', items:[
    {id:'replies', name:'回复记录', icon:'reply'},
    {id:'account', name:'微信账号', icon:'account'},
    {id:'auth', name:'自动授权', icon:'shield'},
    {id:'logs', name:'运行记录', icon:'log'},
    {id:'settings', name:'应用设置', icon:'setting'},
  ]},
];

/* ---------- 演示数据 ---------- */
const CONVS = [
  {name:'马先生·门店运营', tag:'同事', color:'#4a90d9', preview:'好友：我先整理一个接待案例，确认后回复你。', time:'00:53', unread:0},
  {name:'李娜·市场推广', color:'#e0912f', preview:'好友：好的，资料整理后一起核对。', time:'00:48', unread:3},
  {name:'陈工·产品对接', color:'#5aa9a0', preview:'好友：好的，资料整理后一起核对。', time:'00:47', unread:0},
  {name:'周周·培训学员', color:'#8a7fd0', preview:'好友：好的，资料整理后一起核对。', time:'00:46', unread:1},
  {name:'王经理·合作伙伴', color:'#c96f8a', preview:'好友：好的，资料整理后一起核对。', time:'00:45', unread:0},
  {name:'刘欣·运营支持', color:'#4a90d9', preview:'好友：好的，资料整理后一起核对。', time:'00:44', unread:0},
  {name:'张老师·课程顾问', color:'#5aa9a0', preview:'好友：好的，资料整理后一起核对。', time:'00:43', unread:0},
  {name:'黄宇·采购对接', color:'#e0912f', preview:'好友：好的，资料整理后一起核对。', time:'00:42', unread:0},
];

let state = {
  page:'message',
  msgSub:'全部',
  msgType:'全部',
  chat:'马先生·门店运营',
  contactOpen:true,
  todoTab:'reply',
  statTab:'overview',
  statRange:'近7天',
  personaTab:'voice',
  persona:'工作人设',
  historyTab:'self',
  authTab:'func',
  table:'演示账号',
};

/* ---------- 工具函数 ---------- */
const $ = (s,el=document)=>el.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(msg){
  const t=$('#toast'); t.textContent=msg; t.classList.add('show');
  clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),1800);
}
function avatar(name,color){return `<div class="avatar" style="background:${color}">${esc(name[0])}</div>`;}

/* ---------- 渲染导航 ---------- */
function renderSidebar(){
  let h='<div class="brand"><div class="brand-logo">'+I.logo+'</div><div class="brand-name">Yabo工作台</div></div>';
  NAV.forEach(g=>{
    h+=`<div class="nav-group"><div class="nav-group-title">${g.group}</div>`;
    g.items.forEach(it=>{
      h+=`<div class="nav-item ${state.page===it.id?'active':''}" data-page="${it.id}">${I[it.icon]}<span>${it.name}</span>${it.badge?`<span class="badge">${it.badge}</span>`:''}</div>`;
    });
    h+='</div>';
  });
  h+=`<div class="nav-foot"><div class="nav-item" data-page="mini">${I.mini}<span>小窗模式</span></div></div>`;
  $('#sidebar').innerHTML=h;
}

/* ---------- 渲染顶栏 ---------- */
function renderTopbar(){
  $('#topbar').innerHTML=`
    <div class="account-chip" data-act="accountMenu">
      <span class="wx">${I.logo}</span>
      <span class="txt">${esc(state.table)} · 微信号未获取</span>
      <span class="chev">${I.chev}</span>
    </div>
    <div class="demo-mode"><span>演示模式 · 不连接微信或模型</span>
      <button class="play-btn" data-act="demo" title="演示">${I.play}</button>
    </div>`;
}

/* ============================================================
   页面：消息中心
   ============================================================ */
function pageMessage(){
  const list = CONVS.filter(c=> state.msgType==='全部' || (state.msgType==='好友'))
                    .filter(c=> state.msgSub==='全部' || (state.msgSub==='未读' && c.unread>0));
  const listHtml = list.map(c=>`
    <div class="msg-item ${state.chat===c.name?'active':''}" data-chat="${esc(c.name)}">
      ${avatar(c.name,c.color)}
      <div class="msg-item-main">
        <div class="msg-item-top"><span class="msg-item-name">${esc(c.name)}</span><span class="msg-item-time">${c.time}</span></div>
        <div class="msg-item-preview">${esc(c.preview)}</div>
      </div>
      ${c.unread?`<span class="unread">${c.unread}</span>`:''}
    </div>`).join('');

  const msgs = [
    {side:'left', text:'我们下周准备做一场门店的 AI 应用培训，你这边能帮忙提供一个接待场景的案例吗？最好有完整的流程示例。', time:'11月15日 00:42'},
    {side:'right', text:'可以的。我这边有一个上周的培训现场案例，先发你看看整体氛围和讨论形式。', time:'11月15日 00:44'},
    {side:'right', img:true, time:'11月15日 00:45'},
    {side:'left', text:'看起来很合适👍 这个案例能补充下顾客常见问题的回复示例？', time:'11月15日 00:49'},
    {side:'right', sticker:true, time:'11月15日 00:51'},
    {side:'right', text:'我先整理一个接待案例，确认后回复你。', time:'11月15日 00:53'},
  ];
  const chatHtml = msgs.map(m=>{
    let body='';
    if(m.img) body=`<div class="bubble" style="padding:0;background:transparent"><div style="width:210px;height:120px;border-radius:6px;background:linear-gradient(135deg,#8fa08a,#5a6e63);display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;opacity:.9">培训现场 · 演示图片</div><span class="bubble-time">${m.time}</span></div>`;
    else if(m.sticker) body=`<div class="bubble" style="background:transparent;font-size:38px;line-height:1">🐱<span class="bubble-time">${m.time}</span></div>`;
    else body=`<div class="bubble">${esc(m.text)}<span class="bubble-time">${m.time}</span></div>`;
    return `<div class="bubble-row ${m.side==='right'?'right':''}">${body}</div>`;
  }).join('');

  return `
  <div class="msg-wrap">
    <div class="msg-list">
      <div class="msg-list-head">
        <h3>消息中心</h3>
        <div class="searchbox">${I.search}<input class="input" placeholder="搜索会话"></div>
        <div class="msg-tabb">
          ${['全部','未读','待处理'].map(t=>`<span class="${state.msgSub===t?'active':''}" data-msgs="${t}">${t}</span>`).join('')}
        </div>
        <div class="msg-subtabs">
          ${['全部','好友','群聊'].map(t=>`<span class="${state.msgType===t?'active':''}" data-msgtype="${t}">${t}</span>`).join('')}
        </div>
      </div>
      <div class="msg-items">${listHtml || '<div class="empty">暂无会话</div>'}</div>
    </div>
    <div class="chat-pane">
      <div class="chat-head">
        <span class="name">${esc(state.chat)}</span>
        ${state.chat.startsWith('马')?'<span class="mini-tag">同事</span>':''}
        <span class="spacer"></span>
        <span class="muted" style="font-size:11px">已暂停</span>
        <button class="btn sm" data-act="contactToggle">联系人资料</button>
        <button class="btn sm ghost" data-act="more">···</button>
      </div>
      <div class="chat-body">${chatHtml}</div>
      <div class="msg-toolbar">
        <span>${I.file}文件</span><span>${I.image}图片</span><span>${I.mic}语音</span><span>${I.link}链接</span>
      </div>
      <div class="chat-input">
        <textarea class="textarea" id="msgInput">我先整理一个接待案例，确认后回复你。</textarea>
        <div class="chat-input-foot">
          <span class="hint">⌘ Enter 发送</span>
          <span class="acts"><button class="btn sm" data-act="gen">生成建议</button><button class="btn sm primary" data-act="send">发送</button></span>
        </div>
      </div>
    </div>
    <div class="contact-panel ${state.contactOpen?'':'hide'}">
      <h4>联系人资料 <span class="x" data-act="contactClose">${I.close}</span></h4>
      <div class="section-label">下一步事项</div>
      <div class="follow-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span class="chip amber"><span class="tag-dot" style="background:var(--amber)"></span>待确认</span>
          <span class="x" style="cursor:pointer;color:var(--ink-3)">${I.close}</span>
        </div>
        <div style="font-size:12px;margin-bottom:10px">整理接待案例，确认周六沟通时间。</div>
        <div class="mini-field"><span class="k">日期</span><span>11月15日 周日</span></div>
        <div class="mini-field"><span class="k">时间</span><span>01:45</span></div>
        <button class="btn primary sm" data-act="remind">设置提醒</button>
      </div>
      <div class="section-label">与我关系</div>
      <select class="select" style="margin-bottom:10px"><option>工作 · 同事</option><option>私人 · 朋友</option></select>
      <div class="section-label">回复注意事项（可选）</div>
      <textarea class="textarea" style="min-height:56px;margin-bottom:10px">协作沟通，先确认排期。</textarea>
      <div class="section-label">回复策略</div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:10px">当前人设：团队协作</div>
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:14px">
        <span>关系：同事 · 手动</span><button class="btn sm" data-act="restore">恢复自动</button>
      </div>
      <button class="btn" style="width:100%" data-act="buildCustomer">建立客户档案</button>
    </div>
  </div>`;
}

/* ============================================================
   页面：待办处理
   ============================================================ */
const TODO_TABS=[['reply','回复决策',2],['error','系统异常',2],['follow','跟进提醒',3],['material','资料发送',0]];
const TODO_ITEMS={
  reply:[
    {t:'下周二的企业内训，能否安排？',d:'陈女士·演示　涉及具体排期，当前没有已确认的可用时间，需要本人判断',time:'11/15 00:54'},
    {t:'报价单已发出，请客户查收',d:'王经理·演示　发送结果待核对，避免重复发送',time:'11/15 00:52'},
  ],
  error:[
    {t:'原消息内容不可用，请人工查看',d:'Dream·演示　原消息未取得，媒体类型尚未确认，需人工打开原会话查看',time:'11/15 00:56'},
    {t:'发送结果待核对',d:'陈女士·演示　发送结果待核对，请先查看原会话，避免重复发送',time:'11/15 00:55'},
  ],
  follow:[
    {t:'整理接待案例回复',d:'马先生·演示　确认周六沟通时间后回复',time:'11/15 00:53'},
    {t:'发送产品资料包',d:'李娜·演示　待补充公司资料后发送',time:'11/15 00:50'},
    {t:'确认培训场地',d:'周周·演示　待确认场地与时间',time:'11/15 00:46'},
  ],
  material:[],
};
function pageTodo(){
  const items=TODO_ITEMS[state.todoTab];
  const item=items[0];
  let detail='';
  if(state.todoTab==='reply' && item){
    detail=`
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div><div style="font-size:17px;font-weight:700">${esc(item.t)}</div>
          <div style="font-size:11.5px;color:var(--ink-3);margin-top:4px">陈女士 · 演示 <span class="chip amber" style="margin-left:6px">待处理</span></div></div>
        <div style="display:flex;gap:8px"><select class="select" style="width:190px"><option>11/15 00:54 · 下周二的企…</option></select><button class="btn sm">打开会话</button></div>
      </div>
      <div class="reason-box" style="margin-bottom:14px"><div class="r-title">为什么交给你</div>涉及具体排期，当前没有已确认的可用时间，需要本人判断</div>
      <div class="section-label">对方原话 <span style="float:right">11/15 00:54</span></div>
      <div class="orig-quote" style="margin-bottom:14px">我们想下周二做一场企业内训，你有时间吗？</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px"><span class="strong" style="font-size:12.5px">回复草稿 · 未发送</span><button class="btn sm" data-act="refreshCtx">刷新上下文</button></div>
      <textarea class="textarea" style="min-height:96px">收到，你们预计多少人参加、希望重点解决什么问题？我先核对下下周二的时间，再跟你确认。</textarea>
      <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>近期上下文 · 1 条可用记录</div>
      <div class="collapse-body">11/15 00:40 陈女士：我们团队最近想做 AI 培训。</div>
      <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>交接摘要 · 判断供核对</div>
      <div class="collapse-body">涉及排期确认，建议本人核对日历后回复具体时间。</div>
      <div style="border-top:1px solid var(--line);margin-top:20px;padding-top:16px">
        <div style="font-size:11.5px;color:var(--ink-3);line-height:1.8;margin-bottom:12px">发送账号：演示账号 · 发送给：陈女士 · 演示（微信私聊）<br>演示模式不会发送聊天消息</div>
        <div style="display:flex;justify-content:space-between"><button class="btn" data-act="noReply">无需回复并结束</button>
          <span><button class="btn primary" data-act="confirmSend">确认发送回复</button> <button class="btn sm" data-act="more">更多处理 ${I.chev}</button></span></div>
      </div>`;
  } else if(state.todoTab==='error' && item){
    detail=`
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div><div style="font-size:17px;font-weight:700">${esc(item.t)}</div>
          <div style="font-size:11.5px;color:var(--ink-3);margin-top:4px">Dream · 演示 <span class="chip amber" style="margin-left:6px">待处理</span></div></div>
        <button class="btn sm" data-act="openChat">打开会话</button>
      </div>
      <div class="reason-box" style="margin-bottom:14px"><div class="r-title">异常原因</div>原消息未取得，媒体类型尚未确认，需人工打开原会话查看</div>
      <div style="font-size:12.5px;margin-bottom:6px">这条待办尚未完成核对；其他会话是否受影响，请查看运行记录。</div>
      <div style="font-size:12.5px;margin-bottom:12px"><span class="strong">建议下一步</span><div style="color:var(--ink-2);margin-top:4px">1. 打开原会话查看实际内容。<br>2. 返回刷新上下文，再决定如何处理。</div></div>
      <div class="section-label">对方原话 <span style="float:right">11/15 00:56</span></div>
      <div class="orig-quote" style="margin-bottom:14px">未取得可展示的原文，消息类型尚未确认；请打开原会话查看。</div>
      <button class="btn sm" data-act="refreshCtx" style="margin-bottom:10px">刷新上下文</button>
      <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>近期上下文 · 1 条可用记录</div>
      <div class="collapse-body">该会话最近一条消息为媒体消息，本机未保留可展示正文。</div>
      <div style="border-top:1px solid var(--line);margin-top:20px;padding-top:16px">
        <div style="font-size:11.5px;color:var(--ink-3);line-height:1.8;margin-bottom:12px">所属账号：演示账号 · 来源会话：Dream · 演示（微信私聊）<br>结束此项只更新待办状态，不代表消息已发送或故障已修复。</div>
        <div style="display:flex;justify-content:space-between"><button class="btn" data-act="checkChat">打开会话核对</button>
          <button class="btn sm" data-act="more">更多处理 ${I.chev}</button></div>
      </div>`;
  } else if(state.todoTab==='follow'){
    detail=`
      <div style="font-size:17px;font-weight:700;margin-bottom:4px">${esc(item?item.t:'暂无提醒事项')}</div>
      <div style="font-size:11.5px;color:var(--ink-3);margin-bottom:16px">${item?esc(item.d):''}</div>
      <div class="section-label">确认事项与时间</div>
      <div class="field"><div class="field-label">提醒事项</div><input class="input" value="${item?esc(item.t):''}"></div>
      <div class="kv-grid">
        <div class="field"><div class="field-label">日期</div><input class="input" type="date" value="2026-11-15"></div>
        <div class="field"><div class="field-label">时间</div><input class="input" type="time" value="09:00"></div>
      </div>
      <div class="reason-box" style="margin-bottom:14px"><div class="r-title">提醒与主动跟进</div>人工提醒只提醒你处理。自主跟进需单独授权，并受时段、间隔与停止条件约束。</div>
      <button class="btn primary" data-act="setRemind">设置提醒</button>`;
  } else {
    detail=`<div class="empty" style="padding:80px 0">暂无资料发送事项</div>`;
  }

  return `
  <div class="page-head">
    <div><div class="page-title">待办处理</div><div class="page-sub">看清事项与原因，再确认下一步</div></div>
    <div class="demo-tag">演示数据 · 不连接微信</div>
  </div>
  <div class="tabs">
    ${TODO_TABS.map(t=>`<div class="tab ${state.todoTab===t[0]?'active':''}" data-todotab="${t[0]}">${t[1]} <span class="cnt">${t[2]}</span></div>`).join('')}
  </div>
  <div class="workspace">
    <div class="ws-side">
      <div class="ws-side-head">
        <div class="searchbox">${I.search}<input class="input" placeholder="搜索联系人或事项"></div>
        <select class="select" style="margin-top:9px"><option>待处理</option><option>全部</option></select>
      </div>
      <div class="ws-side-list">
        ${(items||[]).map((it,idx)=>`<div class="ws-item ${idx===0?'active':''}"><div class="t">${esc(it.t)}</div><div class="d">${esc(it.d)}</div><div style="font-size:10px;color:var(--ink-3);margin-top:5px">${it.time}</div></div>`).join('') || '<div class="empty">暂无事项</div>'}
      </div>
      <div class="ws-side-foot"><span class="muted" style="font-size:11px">按当前微信账号独立建档</span></div>
    </div>
    <div class="ws-main">${detail}</div>
  </div>`;
}

/* ============================================================
   页面：数据统计
   ============================================================ */
const STAT_TABS=[['overview','总览'],['effect','工作成效'],['customer','客户经营'],['cost','用量成本']];
function pageStats(){
  let body='';
  if(state.statTab==='overview'){
    body=`
      <div class="metric-row">
        <div class="metric"><div class="lbl">已接收消息</div><div class="val">0<span class="unit">条</span></div></div>
        <div class="metric"><div class="lbl">已核实回复</div><div class="val green">0<span class="unit">条</span></div></div>
        <div class="metric"><div class="lbl">有效托管时长</div><div class="val green" style="font-size:22px">0小时0分</div></div>
        <div class="metric"><div class="lbl">当前待办</div><div class="val">0<span class="unit">项</span></div></div>
        <div class="metric"><div class="lbl">人工登记成交额</div><div class="val">¥0.00</div></div>
      </div>
      <div style="font-size:11.5px;color:var(--ink-3);padding-top:12px">在线且托管正常才计时；暂停、断线、休眠不计入。当前待办为此刻未处理量。</div>
      <div class="chart-head"><span class="chart-title">助手工作趋势</span>
        <div><span class="chip green" style="margin-right:6px">消息趋势</span><span class="chip">托管时长</span></div>
      </div>
      <div class="chart-legend"><span><i style="background:#c9d2cb"></i>已接收消息</span><span><i style="background:var(--green)"></i>已核实回复</span></div>
      <div class="chart-area"><div class="gridline" style="top:25%"></div><div class="gridline" style="top:50%"></div><div class="gridline" style="top:75%"></div><div class="gridline" style="bottom:0"></div></div>
      <div class="chart-x"><span>11月9日</span><span>11月10日</span><span>11月11日</span><span>11月12日</span><span>11月13日</span><span>11月14日</span><span>11月15日</span></div>
      <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--ink-2);margin:14px 0 4px"><span>本期新增待办记录 0 · 已处理记录 0</span><span class="link">查看每日明细 ›</span></div>
      <div class="two-cards">
        <div class="mini-card"><div class="h">客户经营 <span class="link">查看›</span></div>
          <div class="funnel"><span>人工确认线索<br><b>0</b></span><span class="arr">→</span><span>已跟进<br><b>0</b></span><span class="arr">→</span><span>已成交客户<br><b>0</b></span></div>
          <div class="muted" style="font-size:11px;margin-top:12px">线索和成交按人工登记统计。</div></div>
        <div class="mini-card"><div class="h">用量成本 <span class="link">查看›</span></div>
          <div style="font-size:12px;line-height:2">模型调用 <b>0</b> 次<br>已计量费用 <b>—</b><br>AI通话接通时长 <b>0小时0分</b></div></div>
      </div>`;
  } else if(state.statTab==='customer'){
    body=`<div class="metric-row">
        <div class="metric"><div class="lbl">人工确认线索</div><div class="val">0<span class="unit">条</span></div></div>
        <div class="metric"><div class="lbl">已跟进</div><div class="val">0<span class="unit">条</span></div></div>
        <div class="metric"><div class="lbl">已成交客户</div><div class="val green">0<span class="unit">位</span></div></div>
        <div class="metric"><div class="lbl">待确认资料</div><div class="val">0<span class="unit">项</span></div></div>
        <div class="metric"><div class="lbl">人工登记成交额</div><div class="val">¥0.00</div></div>
      </div>
      <div class="empty" style="padding:60px 0">演示数据 · 线索与成交按人工登记统计，截图为空数据，不代表实际经营成果。</div>`;
  } else if(state.statTab==='cost'){
    body=`
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
        <div><div style="font-size:15px;font-weight:600">用量与费用估算</div>
          <div style="color:var(--green);font-size:22px;font-weight:700;margin-top:10px">已计量费用 —</div>
          <div class="muted" style="font-size:11px">可计价 0 / 0 次调用</div></div>
        <select class="select" style="width:180px"><option>全部模型</option></select>
      </div>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">免费额度、资源包、优惠未扣减；缺失用量不按零费用处理。</div>
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">单价配置</div>
      <div class="card card-pad" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
        <div><div style="font-weight:600;font-size:12.5px">实时通话 · qwen3.8-omni-flash-realtime</div><div class="muted" style="font-size:11px">百度 · cn-beijing</div></div>
        <button class="btn sm" data-act="configPrice">配置单价</button></div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><span style="font-size:13px;font-weight:600">逐次调用明细</span>
        <span><select class="select" style="width:120px;display:inline-block"><option>全部用途</option></select> <button class="btn sm" data-act="export">导出明细</button></span></div>
      <div class="card"><div style="display:flex;justify-content:space-between;background:#fafbfc;padding:9px 12px;font-size:11px;color:var(--ink-3)"><span>时间 / 用途</span><span>模型 / 估算费用</span></div>
        <div class="empty" style="padding:30px">此范围暂无调用记录。新版本开始逐次计量，不回退历史消耗。</div></div>
      <div class="muted" style="font-size:11px;margin-top:14px">仅统计本机已记录数据；旧版本未记录时长、用量和处理时间不补算。</div>`;
  } else {
    body=`<div class="empty" style="padding:80px 0">工作成效数据（演示）</div>`;
  }
  return `
  <div class="page-head">
    <div><div class="page-title">数据统计</div><div class="page-sub">${esc(state.table)} · 本地记录 · 演示数据</div></div>
    <div class="head-actions"><button class="btn" data-act="refresh">刷新</button><button class="btn primary" data-act="export">导出报表</button></div>
  </div>
  <div class="stat-filters">
    <select class="select" style="width:130px"><option>${esc(state.table)}</option></select>
    ${['今日','近7天','近30天','自定义'].map(r=>`<span class="chip ${state.statRange===r?'green':''}" data-range="${r}" style="cursor:pointer">${r}</span>`).join('')}
    <span class="muted" style="margin-left:auto;font-size:11.5px">2026-11-09 — 2026-11-15</span>
  </div>
  <div class="tabs">
    ${STAT_TABS.map(t=>`<div class="tab ${state.statTab===t[0]?'active':''}" data-stattab="${t[0]}">${t[1]}</div>`).join('')}
  </div>
  ${body}`;
}

/* ============================================================
   页面：客户档案
   ============================================================ */
const CUSTOMERS=[
  {name:'陈女士·演示',co:'星河外贸',stage:'潜在客户',phone:'13800006280',job:'负责人',area:'杭州',email:'chen@example.com',note:'重点了解国际站业务提效'},
  {name:'林先生·演示',co:'启明科技',stage:'未标记',phone:'13900001234',job:'采购经理',area:'深圳',email:'lin@example.com',note:'云帆供应链'},
  {name:'王女士·演示',co:'',stage:'未标记',phone:'',job:'',area:'',email:'',note:'云帆供应链'},
];
function pageCustomers(){
  const c=CUSTOMERS[0];
  return `
  <div class="page-head">
    <div><div class="page-title">客户档案</div></div>
    <div class="head-actions"><button class="btn primary sm" data-act="newCustomer">＋</button></div>
  </div>
  <div class="workspace">
    <div class="ws-side">
      <div class="ws-side-head">
        <div class="searchbox">${I.search}<input class="input" placeholder="搜索姓名、手机号、公司"></div>
        <div style="display:flex;gap:6px;margin-top:9px;flex-wrap:wrap">
          <span class="chip green">✓ 自动识别</span><span class="chip green">✓ 自动跟进</span><span class="chip">已移出</span>
        </div>
        <div class="muted" style="font-size:10.5px;margin-top:8px">09:00–20:00 · 至少间隔48小时 · 再次未回复停止</div>
      </div>
      <div class="ws-side-list">
        ${CUSTOMERS.map((x,i)=>`<div class="ws-item ${i===0?'active':''}"><div class="t">${esc(x.name)}</div><div class="d">${x.stage} · ${x.co||'未标记'}</div></div>`).join('')}
      </div>
      <div class="ws-side-foot"><span class="muted" style="font-size:11px">按当前微信账号独立建档</span></div>
    </div>
    <div class="ws-main">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div><div style="font-size:20px;font-weight:700">${esc(c.name)}</div>
          <div style="display:flex;align-items:center;gap:10px;margin-top:6px"><select class="select" style="width:110px"><option>${c.stage}</option></select><span class="muted" style="font-size:11.5px">微信联系人：${esc(c.name)}</span></div></div>
        <div class="head-actions"><button class="btn primary" data-act="edit">编辑资料</button><button class="btn" data-act="deal">登记成交</button><button class="btn" data-act="more">更多</button></div>
      </div>
      <div class="divider"></div>
      <div class="info-block">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><h3>基本资料 <span class="muted" style="font-size:11px;font-weight:400">人工维护</span></h3><span class="link">${I.edit} 编辑</span></div>
        <div class="kv-grid">
          <div class="kv"><div class="k">姓名称呼</div><div>${esc(c.name)}</div></div>
          <div class="kv"><div class="k">手机号</div><div>${c.phone} ${I.copy}</div></div>
          <div class="kv"><div class="k">公司</div><div>${esc(c.co)}</div></div>
          <div class="kv"><div class="k">职位</div><div>${esc(c.job)}</div></div>
          <div class="kv"><div class="k">所在地区</div><div>${esc(c.area)}</div></div>
          <div class="kv"><div class="k">邮箱</div><div>${c.email} ${I.copy}</div></div>
          <div class="kv"><div class="k">客户来源</div><div>微信咨询</div></div>
          <div class="kv"><div class="k">备注</div><div>${esc(c.note)}</div></div>
        </div>
      </div>
      <div class="divider"></div>
      <div class="info-block">
        <div style="display:flex;justify-content:space-between"><h3>待确认资料</h3><span class="link">从已有聊天提取</span></div>
        <div class="muted" style="font-size:11.5px">客户自述先核对，逐项确认后才补充空白字段；已有人工资料保留。</div>
        <div class="muted" style="font-size:11.5px;margin-top:5px">暂无待确认资料。新来信息会自动发现，也可检查已有保存聊天。</div>
      </div>
      <div class="divider"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
        <div class="info-block"><h3>需求与判断</h3>
          <div class="section-label">需求与计划</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px"><span class="chip green">AI 功能咨询</span><span class="chip green">外贸业务</span><span class="chip green">国际站店铺</span></div>
          <div style="font-size:12px;color:var(--ink-2)">阶段判断 · 了解需求</div>
          <div style="font-size:11.5px;color:var(--ink-3);margin-top:6px">聊天提取：自动判断 <span class="link">查看原话</span> <span class="link">编辑标签</span></div>
        </div>
        <div class="info-block" style="background:var(--green-soft2);border:1px solid var(--line);border-radius:7px;padding:14px"><h3>下一步跟进</h3>
          <div style="display:flex;justify-content:space-between;align-items:center"><span>${I.clock} 尚未安排</span><button class="btn sm" data-act="arrange">安排跟进</button></div>
          <div class="muted" style="font-size:11px;margin:12px 0 6px">按客户需求设置下一次联系提醒。</div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px"><span>自动跟进：已开启</span><span class="link">暂停跟进</span></div>
          <div style="font-size:11.5px;margin-top:6px">微信备注建议</div>
        </div>
      </div>
      <div class="divider"></div>
      <div class="info-block"><div style="display:flex;justify-content:space-between"><h3>跟进记录</h3><span class="link">管理提醒</span></div>
        <div style="font-size:12px;margin-top:8px"><span class="muted">2026年11月15日 00:54</span> <b style="margin-left:14px">了解 AI 功能</b><div class="muted" style="font-size:11.5px">已取消 · 客户有新消息，等待下一步需求</div></div>
        <div style="font-size:12px;margin-top:10px"><span class="muted">2026年11月14日 09:31</span> <b style="margin-left:14px">客户咨询</b></div>
      </div>
    </div>
  </div>`;
}

/* ============================================================
   页面：通讯管理
   ============================================================ */
function pageContacts(){
  const rows=CUSTOMERS.concat([
    {name:'马先生·演示',co:'同事',stage:'工作关系',phone:'—',job:'—',area:'—',email:'—',note:''},
    {name:'李娜·演示',co:'市场推广',stage:'工作关系',phone:'—',job:'—',area:'—',email:'—',note:''},
  ]);
  return `
  <div class="page-head">
    <div><div class="page-title">通讯管理</div><div class="page-sub">统一管理联系人与沟通关系</div></div>
    <div class="head-actions"><button class="btn" data-act="import">导入联系人</button><button class="btn primary" data-act="newCustomer">＋ 新建</button></div>
  </div>
  <div class="card">
    <div style="padding:14px 16px;border-bottom:1px solid var(--line)">
      <div class="searchbox" style="max-width:320px">${I.search}<input class="input" placeholder="搜索联系人、公司、手机号"></div>
    </div>
    <div style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1fr;gap:10px;padding:10px 16px;background:#fafbfc;font-size:11px;color:var(--ink-3)">
      <span>联系人</span><span>公司 / 来源</span><span>阶段</span><span>手机号</span><span>地区</span>
    </div>
    ${rows.map((r,i)=>`<div style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1fr;gap:10px;padding:13px 16px;border-top:1px solid var(--line-2);font-size:12.5px;align-items:center">
      <span style="display:flex;align-items:center;gap:9px">${avatar(r.name,i%2?'#e0912f':'#4a90d9')}<b>${esc(r.name)}</b></span>
      <span class="muted">${esc(r.co||'—')}</span><span><span class="chip ${r.stage==='潜在客户'?'green':''}">${esc(r.stage)}</span></span>
      <span class="muted">${r.phone}</span><span class="muted">${r.area}</span></div>`).join('')}
  </div>`;
}

/* ============================================================
   页面：语音通话
   ============================================================ */
function pageCall(){
  return `
  <div class="page-head">
    <div><div class="page-title">语音通话</div></div>
    <div class="head-actions"><button class="btn" data-act="connectMon">连接监听</button><button class="btn" data-act="disconnect">断开</button></div>
  </div>
  <div class="muted" style="font-size:11.5px;margin-bottom:16px">已接通 · 演示</div>
  <div style="font-size:14px;font-weight:600;margin-bottom:12px">当前通话 <span class="muted" style="font-weight:400">· 已接通</span></div>
  <div style="display:flex;gap:9px;margin-bottom:18px"><button class="btn" data-act="takeover">人工接管</button><button class="btn" data-act="mute">静音</button><button class="btn danger" data-act="hangup">挂断</button></div>
  <div class="divider"></div>
  <div style="font-size:14px;font-weight:600;margin-bottom:10px">实时字幕</div>
  <div class="muted" style="font-size:12px;margin-bottom:18px">暂无字幕</div>
  <div class="divider"></div>
  <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>群语音</div><div class="collapse-body">暂无群语音通话。</div>
  <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>连接诊断</div><div class="collapse-body">实时语音单独沟通配置与服务范围，模型及语音费用另计。</div>
  <div class="muted" style="font-size:11px;margin-top:20px">实时语音需完成云服务、本人音色及授权配置后体验连续问答、打断和人工接管。</div>`;
}

/* ============================================================
   页面：人设管理
   ============================================================ */
const PERSONA_TABS=[['voice','人设口吻'],['scene','业务场景'],['self','本人资料']];
const PERSONAS=[
  {name:'工作人设',tag:'默认',desc:'直接、友好、专业，避免客服套话'},
  {name:'日常人设',desc:'自然、简短、有分寸，不强行推销'},
  {name:'团队协作',desc:'直接、清晰，先确认口径与下一步'},
];
function pagePersona(){
  let main='';
  if(state.personaTab==='voice'){
    main=`
      <div class="collapse" style="border-top:none;padding-top:0"><span class="arrow">${I.arrow}</span>自动选择人设</div>
      <h3 style="font-size:16px;margin:12px 0 18px">${esc(state.persona)}</h3>
      <div class="field"><div class="field-label">名称</div><input class="input" value="${esc(state.persona)}"></div>
      <div class="field"><div class="field-label">身份与沟通场景</div><textarea class="textarea" style="min-height:58px">以本人身份进行客户咨询和工作沟通</textarea></div>
      <div class="field"><div class="field-label">语气与表达方式</div><textarea class="textarea" style="min-height:58px">直接、友好、专业，避免客服套话</textarea></div>
      <div class="kv-grid">
        <div class="field"><div class="field-label">称呼方式</div><input class="input" value="按对方称呼"></div>
        <div class="field"><div class="field-label">回复长度</div><input class="input" value="1-3 句"></div>
        <div class="field"><div class="field-label">表情偏好</div><input class="input" value="少量使用"></div>
      </div>
      <div class="field"><div class="field-label">表达禁忌与承诺边界</div><textarea class="textarea" style="min-height:56px">不编造事实，不擅自承诺时间、价格或付款</textarea></div>
      <div class="field"><div class="field-label">本人口吻样例（每行一条）</div><textarea class="textarea" style="min-height:70px"></textarea></div>
      <button class="btn primary" data-act="save">保存人设</button>`;
  } else if(state.personaTab==='scene'){
    main=`
      <h3 style="font-size:16px;margin-bottom:6px">业务场景</h3>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">为业务场景设置目标、必问信息与转人工条件，可用合成问题试聊。</div>
      <div class="field"><div class="field-label">场景名称</div><input class="input" value="客户咨询接待"></div>
      <div class="field"><div class="field-label">沟通目标</div><textarea class="textarea" style="min-height:52px">了解客户需求，给出准确回复</textarea></div>
      <div class="field"><div class="field-label">必问信息</div><input class="input" value="需求、数量、时间"></div>
      <div class="field"><div class="field-label">转人工条件</div><input class="input" value="涉及报价、收款、排期"></div>
      <button class="btn" data-act="tryChat">合成问题试聊</button> <button class="btn primary" data-act="save">保存场景</button>`;
  } else {
    main=`
      <h3 style="font-size:16px;margin-bottom:6px">本人资料</h3>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">常用联系方式按确认资料使用，敏感内容先人工确认。</div>
      <div class="kv-grid">
        <div class="field"><div class="field-label">业务电话</div><input class="input" value="138 0000 6280"></div>
        <div class="field"><div class="field-label">办公地址</div><input class="input" value="杭州市 · 演示地址"></div>
        <div class="field"><div class="field-label">微信号</div><input class="input" value="未获取"></div>
        <div class="field"><div class="field-label">资料链接</div><input class="input" placeholder="添加链接"></div>
      </div>
      <button class="btn primary" data-act="save">保存资料</button>`;
  }
  return `
  <div class="tabs" style="justify-content:center;gap:80px">
    ${PERSONA_TABS.map(t=>`<div class="tab ${state.personaTab===t[0]?'active':''}" data-personatab="${t[0]}">${t[1]}</div>`).join('')}
  </div>
  <div class="workspace" style="border-top-left-radius:0;border-top-right-radius:0">
    <div class="ws-side">
      <div class="ws-side-head" style="display:flex;justify-content:space-between;align-items:center;font-weight:600">人设 <span class="link">${I.plus}</span></div>
      <div class="ws-side-list">
        ${PERSONAS.map(p=>`<div class="ws-item ${state.persona===p.name?'active':''}" data-persona="${p.name}">
          <div class="t">${esc(p.name)} ${p.tag?`<span class="mini-tag">${p.tag}</span>`:''}</div><div class="d">${esc(p.desc)}</div></div>`).join('')}
      </div>
    </div>
    <div class="ws-main">${main}</div>
  </div>`;
}

/* ============================================================
   页面：知识管理
   ============================================================ */
function pageKnowledge(){
  return `
  <div class="workspace">
    <div class="ws-side">
      <div class="ws-side-head">
        <div style="display:flex;gap:8px;align-items:center"><div class="searchbox" style="flex:1">${I.search}<input class="input" placeholder="搜索知识"></div><span class="link" data-act="newKnowledge">${I.plus}</span></div>
      </div>
      <div class="ws-side-list"><div class="empty" style="margin-top:60px">暂无知识<br>可新建条目或导入文档</div></div>
      <div class="ws-side-foot"><button class="btn" style="width:100%" data-act="importDoc">导入文档…</button></div>
    </div>
    <div class="ws-main">
      <h3 style="font-size:16px;margin-bottom:18px">知识库</h3>
      <div class="field"><div class="field-label">标题</div><input class="input" placeholder="知识标题"></div>
      <div class="field"><div class="field-label">适用人设</div><select class="select"><option>所有人设</option></select></div>
      <div class="field"><div class="field-label">来源</div><input class="input" value="手工录入"></div>
      <div class="field"><div class="field-label">适用业务</div><select class="select"><option>全部业务</option></select></div>
      <div class="field"><div class="field-label">正文</div><textarea class="textarea" style="min-height:170px"></textarea></div>
      <label class="check-row"><span class="check-box" data-check data-act="chkApprove"></span>我已核对内容，批准作为事实依据</label>
      <label class="check-row"><span class="check-box on" data-check data-act="chkEnable">${I.check}</span>启用此条知识</label>
      <label class="check-row"><span class="check-box" data-check data-act="chkExpire"></span>设置有效期</label>
      <div style="margin:14px 0"><button class="btn" data-act="saveKnowledge" disabled>保存知识</button></div>
      <div class="muted" style="font-size:11px">支持 UTF-8 TXT、Markdown、文字型 PDF；扫描 PDF、图片和视频不会被当作已解析知识。</div>
    </div>
  </div>`;
}

/* ============================================================
   页面：历史学习
   ============================================================ */
const HIST_TABS=[['self','本人样本'],['knowledge','知识候选'],['tone','口吻与技巧']];
const HIST_ITEMS=[
  {t:'客户 A · 演示',d:'可以先找项目负责人确认一下，…',time:'11/15'},
  {t:'同事 B · 演示',d:'我这边先整理个初稿，晚点再和…',time:'11/14'},
  {t:'工作群 · 演示',d:'大家有时间的话，今天下午开个…',time:'11/13'},
];
function pageHistory(){
  let main='';
  if(state.historyTab==='self'){
    main=`
      <div style="font-size:17px;font-weight:700;margin-bottom:4px">这段原话是你亲自写的吗？</div>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">客户 A · 演示 · 私聊 · 2026年11月15日</div>
      <div class="section-label">此前对方消息</div><div class="orig-quote" style="margin-bottom:14px">资料找谁确认？</div>
      <div class="section-label">本人账号出站</div><div class="orig-quote" style="margin-bottom:18px">可以先找项目负责人确认一下，弄清楚再往下走。</div>
      <div class="divider"></div>
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">可能的表达习惯</div>
      <div style="font-size:12.5px;line-height:2">• 通常用短句，按需再展开<br>• 先直接回答核心问题</div>
      <div class="muted" style="font-size:11.5px;margin:8px 0 0">尚未作为你的长期口吻使用</div>
      <div style="border-top:1px solid var(--line);margin-top:40px;padding-top:16px;display:flex;align-items:center;gap:10px">
        <button class="btn primary" data-act="confirmSelf">确认是本人原话</button><button class="btn" data-act="skip">跳过这条</button><span class="link">查看完整来源</span>
      </div>
      <div class="muted" style="font-size:11px;margin-top:10px">确认样本后再提炼口吻；不会把原话当作事实或授权。</div>`;
  } else if(state.historyTab==='knowledge'){
    main=`
      <div style="font-size:17px;font-weight:700;margin-bottom:4px">聊天里的新事实，确认后才复用</div>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">表达习惯和业务事实分别管理</div>
      <div class="section-label">候选内容</div><div class="orig-quote" style="margin-bottom:12px">我们国际站店铺主要做欧美市场，旺季在 Q4。</div>
      <div class="section-label">原话来源</div><div class="muted" style="font-size:12px;margin-bottom:16px">陈女士 · 演示 · 11月15日 00:41</div>
      <div class="reason-box" style="margin-bottom:14px"><div class="r-title">明确适用范围</div>默认用于原会话；需要本账号其他会话使用时再明确允许，不自动跨账号共享。</div>
      <div style="display:flex;gap:10px"><button class="btn primary" data-act="adopt">采纳候选</button><button class="btn" data-act="skip">忽略</button><button class="btn" data-act="edit">自行编辑</button></div>`;
  } else {
    main=`
      <div style="font-size:17px;font-weight:700;margin-bottom:4px">从你的改稿里，学习怎么说</div>
      <div class="muted" style="font-size:11.5px;margin-bottom:18px">查看已整理的表达规律和来源</div>
      <div class="card" style="padding:14px 16px;margin-bottom:12px"><div class="strong" style="font-size:13px;margin-bottom:6px">先回答核心问题</div><div class="muted" style="font-size:12px">来自 4 条已确认样本 · 当前启用</div></div>
      <div class="card" style="padding:14px 16px;margin-bottom:12px"><div class="strong" style="font-size:13px;margin-bottom:6px">用短句，按需展开</div><div class="muted" style="font-size:12px">来自 3 条已确认样本 · 当前启用</div></div>
      <div class="reason-box"><div class="r-title">随时纠正和停用</div>发现归纳不符合习惯时，可以纠正或不再参考；长期贴合效果仍需本人核对。</div>`;
  }
  return `
  <div class="page-head">
    <div><div class="page-title">历史学习 <span class="tag-dot" style="margin-left:6px"></span><span class="muted" style="font-size:12px;font-weight:400">自动学习已开启</span></div>
      <div class="page-sub">本人样本待确认 · 闲时自动提炼</div></div>
    <div class="head-actions"><span class="link">学习范围与用量 ›</span><button class="btn" data-act="pauseLearn">暂停学习</button></div>
  </div>
  <div class="tabs">
    ${HIST_TABS.map(t=>`<div class="tab ${state.historyTab===t[0]?'active':''}" data-histtab="${t[0]}">${t[1]} ${t[0]==='knowledge'?'<span class="cnt">3</span>':''}</div>`).join('')}
    <span class="link" style="margin-left:auto;align-self:center">记录与版本 ›</span>
  </div>
  <div class="workspace">
    <div class="ws-side">
      <div class="ws-side-head">
        <div class="searchbox">${I.search}<input class="input" placeholder="搜索联系人或关键词"></div>
        <div style="display:flex;gap:8px;margin-top:9px"><select class="select" style="flex:1"><option>待确认</option></select><span class="chip">3 多选</span></div>
      </div>
      <div class="ws-side-list">
        ${HIST_ITEMS.map((it,i)=>`<div class="ws-item ${i===0?'active':''}"><div class="t">${esc(it.t)}</div><div class="d">${esc(it.d)}</div><div style="font-size:10px;color:var(--ink-3);margin-top:5px">${it.time}</div></div>`).join('')}
      </div>
    </div>
    <div class="ws-main">${main}</div>
  </div>`;
}

/* ============================================================
   页面：回复记录
   ============================================================ */
function pageReplies(){
  const rows=[
    ['马先生·门店运营','生成建议','先整理接待案例，确认后回复你','11/15 00:53','已核实'],
    ['李娜·市场推广','自动回复','好的，资料整理后一起核对','11/15 00:48','已核实'],
    ['陈女士·演示','建议采纳','收到，我先核对下时间再确认','11/15 00:44','已核实'],
    ['Dream·演示','人工处理','原消息不可用，转人工查看','11/15 00:56','需核对'],
  ];
  return `
  <div class="page-head">
    <div><div class="page-title">回复记录</div><div class="page-sub">查看已生成、已核实与需核对的回复</div></div>
    <div class="head-actions"><button class="btn" data-act="export">导出明细</button></div>
  </div>
  <div style="display:flex;gap:10px;margin-bottom:14px"><div class="searchbox" style="width:260px">${I.search}<input class="input" placeholder="搜索会话或内容"></div><select class="select" style="width:140px"><option>全部来源</option></select></div>
  <div class="card">
    <div style="display:grid;grid-template-columns:1.2fr .8fr 2fr .9fr .7fr;gap:10px;padding:10px 16px;background:#fafbfc;font-size:11px;color:var(--ink-3)"><span>会话</span><span>来源</span><span>回复内容</span><span>时间</span><span>状态</span></div>
    ${rows.map(r=>`<div style="display:grid;grid-template-columns:1.2fr .8fr 2fr .9fr .7fr;gap:10px;padding:13px 16px;border-top:1px solid var(--line-2);font-size:12.5px;align-items:center">
      <b>${esc(r[0])}</b><span class="muted">${r[1]}</span><span style="color:var(--ink-2)">${esc(r[2])}</span><span class="muted">${r[3]}</span>
      <span class="chip ${r[4]==='需核对'?'amber':'green'}">${r[4]}</span></div>`).join('')}
  </div>`;
}

/* ============================================================
   页面：微信账号
   ============================================================ */
function pageAccount(){
  return `
  <div class="page-head">
    <div><div class="page-title">微信账号</div></div>
    <div class="head-actions"><button class="btn" data-act="connectBackend">连接后台</button><button class="btn" data-act="refresh">刷新</button></div>
  </div>
  <div class="acct-card">
    <div class="acct-top">
      <div class="acct-id"><div class="acct-avatar">${I.logo}</div><div><div style="font-size:15px;font-weight:700">${esc(state.table)}</div><div class="muted" style="font-size:11.5px">微信号未获取</div></div></div>
      <div class="muted" style="font-size:11.5px">已登录</div>
    </div>
    <div class="acct-actions"><button class="btn primary" data-act="startHost">开启托管</button><button class="btn" data-act="pauseHost">暂停托管</button>
      <div style="flex:1"></div><button class="btn" data-act="scanLogin">扫码登录</button><button class="btn" data-act="more">更多操作</button></div>
    <div class="acct-status">原生通道尚未启动</div>
    <div class="divider"></div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>账号详情</div>
    <div class="collapse-body">账号身份、连接和托管状态；按账号管理暂停、恢复及相关配置。</div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>下载设置</div>
    <div class="collapse-body">账号资料与规则分别保存。当前服务套餐含 1 个账号，多账号并发需另行验证。</div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>后台能力</div>
    <div class="collapse-body">查看当前账号可用的后台能力与授权范围。</div>
    <div class="divider"></div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>添加账号</div>
    <div class="collapse-body">本套餐包含 1 个账号；多账号同时在线和额外设备需单独评估与验证。</div>
  </div>`;
}

/* ============================================================
   页面：自动授权
   ============================================================ */
const AUTH_TABS=[['func','功能授权'],['media','媒体服务']];
function pageAuth(){
  const funcs=['发送文字','发送媒体','撤回消息','会话置顶','消息免打扰','标记已读','发送链接卡片'];
  let main=`
    <div class="section-label">工作目标</div>
    <textarea class="textarea" style="min-height:70px;margin-bottom:8px"></textarea>
    <div class="muted" style="font-size:11.5px;margin-bottom:16px">按对象授权：AI 接听可选择全部私聊来电。起止时间相同为全天。</div>
    <div class="collapse open" data-toggle><span class="arrow">${I.arrow}</span>消息处理</div>
    <div class="collapse-body show">${funcs.map(f=>`<label class="check-row"><span class="check-box" data-check>${I.check&&''}</span>${f}</label>`).join('')}</div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>群聊管理</div>
    <div class="collapse-body">普通群聊仅处理真实 @ 本人的消息；待办审批群使用已绑定成员的专用确认流程。</div>
    <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>语音通话</div>
    <div class="collapse-body">按实际需要设置功能、对象、时段、限额及排除范围，随时暂停或撤销。</div>`;
  if(state.authTab==='media'){
    main=`
      <div class="muted" style="font-size:12.5px;margin-bottom:16px">媒体服务需单独配置与授权，并按实际场景验收。</div>
      <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>图片识别</div><div class="collapse-body">识别聊天中的图片与表情包。</div>
      <div class="collapse" data-toggle><span class="arrow">${I.arrow}</span>实时语音</div><div class="collapse-body">用本人音色体验连续问答、打断和人工接管。</div>`;
  }
  return `
  <div class="page-head"><div><div class="page-title">自动授权</div></div></div>
  <div class="tabs">${AUTH_TABS.map(t=>`<div class="tab ${state.authTab===t[0]?'active':''}" data-authtab="${t[0]}">${t[1]}</div>`).join('')}</div>
  <div class="card" style="padding:20px 22px">${main}</div>
  <div style="display:flex;justify-content:space-between;margin-top:16px;padding-top:16px;border-top:1px solid var(--line)">
    <button class="btn" data-act="saveAuth">保存授权</button>
    <span><button class="btn primary" data-act="enableAuto">开启自主执行</button> <button class="btn" data-act="pauseAuto">暂停执行</button></span>
  </div>`;
}

/* ============================================================
   页面：运行记录
   ============================================================ */
function pageLogs(){
  const rows=[
    ['11/15 00:56','系统异常','原消息内容不可用，媒体类型尚未确认','Dream·演示','待核对'],
    ['11/15 00:54','转人工','涉及具体排期，交本人判断','陈女士·演示','已转交'],
    ['11/15 00:53','生成建议','整理接待案例回复建议','马先生·演示','成功'],
    ['11/15 00:48','自动回复','按已配置范围生成回复','李娜·演示','成功'],
    ['11/15 00:44','知识引用','引用已批准知识条目','陈女士·演示','成功'],
    ['11/15 00:40','会话同步','同步本机已保存会话','演示账号','成功'],
  ];
  return `
  <div class="page-head">
    <div><div class="page-title">运行记录</div><div class="page-sub">查看本机工作记录与异常线索</div></div>
    <div class="head-actions"><button class="btn" data-act="refresh">刷新</button><button class="btn" data-act="export">导出</button></div>
  </div>
  <div style="display:flex;gap:10px;margin-bottom:14px"><select class="select" style="width:140px"><option>全部类型</option></select><select class="select" style="width:140px"><option>当前账号</option></select></div>
  <div class="card">
    <div style="display:grid;grid-template-columns:.8fr .9fr 2.2fr 1.1fr .8fr;gap:10px;padding:10px 16px;background:#fafbfc;font-size:11px;color:var(--ink-3)"><span>时间</span><span>类型</span><span>事项</span><span>会话 / 账号</span><span>结果</span></div>
    ${rows.map(r=>`<div style="display:grid;grid-template-columns:.8fr .9fr 2.2fr 1.1fr .8fr;gap:10px;padding:12px 16px;border-top:1px solid var(--line-2);font-size:12.5px;align-items:center">
      <span class="muted">${r[0]}</span><span>${r[1]}</span><span style="color:var(--ink-2)">${esc(r[2])}</span><span class="muted">${esc(r[3])}</span>
      <span class="chip ${r[4]==='待核对'?'amber':r[4]==='成功'?'green':''}">${r[4]}</span></div>`).join('')}
  </div>`;
}

/* ============================================================
   页面：应用设置
   ============================================================ */
function pageSettings(){
  const sec=(title,body)=>`<div class="info-block"><h3 style="font-size:14px;margin-bottom:12px">${title}</h3>${body}<div class="divider"></div></div>`;
  return `
  <div class="page-head"><div><div class="page-title">应用设置</div><div class="page-sub">在应用内管理账号、待办、回复记录、用量与费用估算</div></div></div>
  <div class="form-card">
    ${sec('通用',`<div class="kv-grid">
      <div class="field"><div class="field-label">界面语言</div><select class="select"><option>简体中文</option></select></div>
      <div class="field"><div class="field-label">开机自启</div><select class="select"><option>关闭</option></select></div>
    </div>`)}
    ${sec('回复与托管',`<label class="check-row"><span class="check-box on">${I.check}</span>自动生成回复建议</label>
      <label class="check-row"><span class="check-box" data-check></span>自动采用已核实回复</label>
      <label class="check-row"><span class="check-box on">${I.check}</span>关键决定转待办处理</label>`)}
    ${sec('数据与隐私',`<label class="check-row"><span class="check-box on">${I.check}</span>会话与知识保存在本机</label>
      <label class="check-row"><span class="check-box on">${I.check}</span>模型中心管理密钥（Windows 本机加密）</label>
      <div class="muted" style="font-size:11.5px;margin-top:8px">人设、知识和会话管理资料保存在本机；生成回复会按授权调用云模型。</div>`)}
    ${sec('关于',`<div style="font-size:12.5px;line-height:1.9">
      <div>版本 Yabo工作台 2.7.0</div>
      <div>本地工作空间 · 幺爆导演台已接入</div>
      <div class="muted">截图来自演示数据，使用合成资料；多账号并发、长期稳定及经营效果尚未完成完整验收。</div></div>`)}
    <button class="btn primary" data-act="saveSettings">保存设置</button>
  </div>`;
}

/* ============================================================
   主渲染 / 路由
   ============================================================ */
const PAGES={
  message:pageMessage, todo:pageTodo, stats:pageStats, contacts:pageContacts,
  customers:pageCustomers, call:pageCall, persona:pagePersona, knowledge:pageKnowledge,
  history:pageHistory, replies:pageReplies, account:pageAccount, auth:pageAuth,
  logs:pageLogs, settings:pageSettings,
};
function render(){
  renderSidebar();
  renderTopbar();
  const fn=PAGES[state.page]||pageMessage;
  $('#content').innerHTML=fn();
  // 恢复折叠状态绑定
  window.scrollTo(0,0);
  $('#content').scrollTop=0;
}
function navigate(page){
  if(page==='mini'){toast('已切换到小窗模式（演示）');return;}
  state.page=page;
  render();
}

/* ---------- 事件委托 ---------- */
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-page],[data-act],[data-chat],[data-msgs],[data-msgtype],[data-todotab],[data-stattab],[data-range],[data-personatab],[data-persona],[data-histtab],[data-authtab],[data-toggle],[data-check]');
  if(!t) return;
  // 导航
  if(t.dataset.page){navigate(t.dataset.page);return;}
  // 折叠
  if(t.hasAttribute('data-toggle')){t.classList.toggle('open');const b=t.nextElementSibling;if(b&&b.classList.contains('collapse-body'))b.classList.toggle('show');return;}
  // 勾选框
  if(t.hasAttribute('data-check')){const on=t.classList.toggle('on');t.innerHTML=on?I.check:'';return;}
  // 会话切换
  if(t.dataset.chat){state.chat=t.dataset.chat;render();return;}
  if(t.dataset.msgs){state.msgSub=t.dataset.msgs;render();return;}
  if(t.dataset.msgtype){state.msgType=t.dataset.msgtype;render();return;}
  if(t.dataset.todotab){state.todoTab=t.dataset.todotab;render();return;}
  if(t.dataset.stattab){state.statTab=t.dataset.stattab;render();return;}
  if(t.dataset.range){state.statRange=t.dataset.range;render();return;}
  if(t.dataset.personatab){state.personaTab=t.dataset.personatab;render();return;}
  if(t.dataset.persona){state.persona=t.dataset.persona;render();return;}
  if(t.dataset.histtab){state.historyTab=t.dataset.histtab;render();return;}
  if(t.dataset.authtab){state.authTab=t.dataset.authtab;render();return;}
  // 动作
  const a=t.dataset.act;
  const MAP={
    contactToggle:()=>{state.contactOpen=!state.contactOpen;render();},
    contactClose:()=>{state.contactOpen=false;render();},
    gen:()=>toast('已生成回复建议（演示）'),
    send:()=>toast('演示模式 · 消息不会真实发送'),
    remind:()=>toast('提醒已设置（演示）'),
    restore:()=>toast('已恢复自动回复策略（演示）'),
    buildCustomer:()=>{navigate('customers');toast('已根据会话建立客户档案（演示）');},
    refreshCtx:()=>toast('上下文已刷新（演示）'),
    confirmSend:()=>toast('演示模式 · 回复不会真实发送'),
    noReply:()=>toast('已标记无需回复并结束（演示）'),
    openChat:()=>navigate('message'),
    checkChat:()=>navigate('message'),
    setRemind:()=>toast('提醒已设置（演示）'),
    refresh:()=>toast('数据已刷新（演示）'),
    export:()=>toast('演示模式 · 已模拟导出'),
    exportDetail:()=>toast('演示模式 · 已模拟导出明细'),
    configPrice:()=>toast('打开单价配置（演示）'),
    newCustomer:()=>toast('新建客户档案（演示）'),
    edit:()=>toast('进入编辑模式（演示）'),
    deal:()=>toast('登记成交（演示）'),
    arrange:()=>toast('安排跟进提醒（演示）'),
    import:()=>toast('导入联系人（演示）'),
    connectMon:()=>toast('已连接监听（演示）'),
    disconnect:()=>toast('已断开（演示）'),
    takeover:()=>toast('已切换人工接管（演示）'),
    mute:()=>toast('已静音（演示）'),
    hangup:()=>toast('通话已挂断（演示）'),
    tryChat:()=>toast('合成问题试聊（演示）'),
    save:()=>toast('已保存（演示）'),
    newKnowledge:()=>toast('新建知识条目（演示）'),
    importDoc:()=>toast('导入文档（演示）'),
    saveKnowledge:()=>toast('保存知识前请勾选批准（演示）'),
    pauseLearn:()=>toast('学习已暂停（演示）'),
    confirmSelf:()=>toast('已确认本人原话（演示）'),
    skip:()=>toast('已跳过（演示）'),
    adopt:()=>toast('已采纳知识候选（演示）'),
    connectBackend:()=>toast('连接后台（演示）'),
    startHost:()=>toast('托管已开启（演示）'),
    pauseHost:()=>toast('托管已暂停（演示）'),
    scanLogin:()=>toast('演示模式 · 扫码登录不可用'),
    saveAuth:()=>toast('授权已保存（演示）'),
    enableAuto:()=>toast('自主执行已开启（演示）'),
    pauseAuto:()=>toast('自主执行已暂停（演示）'),
    saveSettings:()=>toast('设置已保存（演示）'),
    savePrice:()=>toast('单价已保存（演示）'),
    accountMenu:()=>toast('当前账号：演示账号（演示）'),
    demo:()=>toast('演示模式 · 不连接微信或模型'),
    more:()=>toast('更多操作（演示）'),
  };
  if(a && MAP[a]){MAP[a]();return;}
  if(a) toast('演示功能：'+a);
});

/* ---------- 桌面窗口控制（Electron 桥接，浏览器下优雅降级） ---------- */
const isDesktop = !!(window.electronAPI && window.electronAPI.isElectron);
if(isDesktop) document.body.classList.add('desktop');

document.querySelectorAll('.dot[data-win]').forEach(dot=>{
  dot.addEventListener('click',()=>{
    const act=dot.dataset.win;
    if(isDesktop && window.electronAPI[act]){
      window.electronAPI[act]();
    }else{
      const names={close:'关闭',minimize:'最小化',maximize:'缩放'};
      toast('浏览器预览模式 · '+names[act]+'仅在桌面应用可用');
    }
  });
});

/* ---------- 启动 ---------- */
render();
