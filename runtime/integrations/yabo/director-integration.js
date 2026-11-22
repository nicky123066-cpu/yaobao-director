/* Shared Heli service, preserved iframe sessions, and a single Yabo model-center entry. */
(() => {
  const originalTopbar=renderTopbar;
  const originalRender=render;
  let service=null,ensurePromise=null;
  const sessions=new Map();
  const group={group:'内容创作',items:[{id:'heli',name:'幺爆导演台',icon:'image'}]};
  NAV.splice(1,0,group);
  NAV[NAV.length-1].items.unshift({id:'models',name:'模型中心',icon:'setting'});
  PAGES.heli=()=>'';PAGES.models=()=>'';
  const host=document.createElement('section');
  host.className='director-host';host.hidden=true;host.setAttribute('aria-label','Yabo 内容创作模块');
  document.querySelector('.main').appendChild(host);

  async function ensureBackend(){
    if(!ensurePromise)ensurePromise=(async()=>{
      if(window.electronAPI?.ensureDirector)return window.electronAPI.ensureDirector();
      if(!/^https?:$/.test(location.protocol))throw new Error('请通过 Yabo 桌面应用打开，或访问本地工作台地址。');
      const response=await fetch('/api/health');
      if(!response.ok)throw new Error('本地服务不可用，请先启动幺爆导演台。');
      const health=await response.json();
      if(health.app!=='mujian-workbench')throw new Error('当前网页未连接幺爆服务。');
      return {baseUrl:location.origin,existing:true,version:health.version};
    })().then(value=>{service=value;return value;}).catch(error=>{ensurePromise=null;throw error;});
    return ensurePromise;
  }
  function session(role){
    if(sessions.has(role))return sessions.get(role);
    const panel=document.createElement('div');panel.className='director-session';panel.dataset.role=role;
    panel.innerHTML='<div class="director-loader" role="status"><div class="director-loader-mark">Y</div><h2>正在连接'+(role==='models'?'模型中心':'幺爆导演台')+'</h2><p>读取本地项目与任务，连接同一个工作空间。</p></div>';
    host.appendChild(panel);sessions.set(role,panel);
    ensureBackend().then(connection=>{
      const base=new URL(connection.baseUrl);
      if(base.protocol!=='http:'||!['127.0.0.1','localhost'].includes(base.hostname))throw new Error('仅允许连接本机导演台服务。');
      const iframe=document.createElement('iframe');
      iframe.title=role==='models'?'Yabo 共享模型中心':'幺爆导演台内容创作';
      iframe.src=base.origin+'/?embed=yabo'+(role==='models'?'&module=models#settings':'#home');
      iframe.setAttribute('allow','clipboard-write');
      iframe.addEventListener('load',()=>panel.classList.add('loaded'));
      panel.replaceChildren(iframe);renderTopbar();
    }).catch(error=>{
      panel.innerHTML=`<div class="director-loader director-error" role="alert"><h2>本地服务暂未就绪</h2><p>${esc(error.message)}</p><button class="btn primary" data-retry-director="${role}">重新连接</button></div>`;
    });
    return panel;
  }
  renderTopbar=function(){
    if(!['heli','models'].includes(state.page))return originalTopbar();
    const title=state.page==='models'?'模型中心':'幺爆导演台';
    document.getElementById('topbar').innerHTML=`<div class="director-breadcrumb"><span>Yabo工作台</span>${I.arrow}<strong>${title}</strong><span class="director-module-tag">${state.page==='models'?'共享配置':'内容创作'}</span></div><div class="director-service-status"><i class="${service?'ready':''}"></i>${service?'本地工作空间已连接':'正在连接本地工作空间'}</div>${state.page==='heli'?'<button class="btn sm" data-page="models">模型中心</button>':'<button class="btn sm" data-page="heli">返回幺爆导演台</button>'}`;
  };
  render=function(){
    const integrated=['heli','models'].includes(state.page);
    document.querySelector('.main').classList.toggle('director-mode',integrated);
    document.getElementById('content').hidden=integrated;host.hidden=!integrated;
    if(integrated){
      renderSidebar();renderTopbar();
      for(const panel of sessions.values())panel.hidden=true;
      session(state.page).hidden=false;
    }else originalRender();
    document.querySelectorAll('.nav-item[data-page]').forEach(item=>{item.setAttribute('role','button');item.tabIndex=0;item.setAttribute('aria-label',item.textContent.trim());});
    sessionStorage.setItem('yabo.last-page',state.page);
  };
  const originalNavigate=navigate;
  navigate=function(page){originalNavigate(page);if(page!=='mini')history.replaceState(null,'','#'+page);};
  document.addEventListener('keydown',event=>{if((event.key==='Enter'||event.key===' ')&&event.target.matches('.nav-item[data-page]')){event.preventDefault();event.target.click();}});
  document.addEventListener('click',event=>{
    const retry=event.target.closest('[data-retry-director]');
    if(!retry)return;
    const role=retry.dataset.retryDirector;ensurePromise=null;const panel=sessions.get(role);if(panel)panel.remove();sessions.delete(role);render();
  });
  window.addEventListener('hashchange',()=>{const target=location.hash.slice(1);if(PAGES[target]&&target!==state.page){state.page=target;render();}});
  window.addEventListener('message',event=>{
    const studio=sessions.get('heli')?.querySelector('iframe');
    if(!service||!studio||event.source!==studio.contentWindow||event.origin!==new URL(service.baseUrl).origin)return;
    if(event.data?.type==='yabo:open-model-center')navigate('models');
  });
  const initial=location.hash.slice(1)||sessionStorage.getItem('yabo.last-page');
  if(PAGES[initial])state.page=initial;
  render();
})();
