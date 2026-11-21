<script lang="ts">
  import { onMount } from 'svelte';
  import { renderPreview, resourceCandidates } from './preview';
  import type { Appearance, Preview } from './preview';
  import { previewLabel } from './preview-labels';
  import Icon from './Icon.svelte';
  import { studioLabel } from './studio-labels';
  import type { StudioLabel } from './studio-labels';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { listen } from '@tauri-apps/api/event';
  import { call, failure } from './bridge';
  import type { Converter, Encoding, Failure, NativeRequest, Page, Policy, Poll, Row, SessionReply, ReaderDetails } from './bridge';
  import { translate } from './i18n';
  import type { Label, Locale } from './i18n';

  type View = 'build' | 'extract' | 'converters' | 'tools' | 'jobs' | 'database' | 'morphology';
  let locale = $state<Locale>('en');
  let theme = $state('system');
  let view = $state<View>('build');
  let platform = $state('');
  let connected = $state(false);
  let pending = $state(0);
  let alert = $state<Failure | null>(null);
  let status = $state('');
  let settings = $state(false);
  let converterSetup = $state(false);
  let preferencesReady = $state(false);
  let source = $state('');
  let destination = $state('');
  let resourceRoot = $state('');
  let title = $state('');
  let description = $state('');
  let stylesheet = $state('');
  let encoding = $state<Encoding>('utf8');
  let pack = $state('generic');
  let extraction = $state('txt');
  let converter = $state<Converter>('cc_cedict');
  let worksheet = $state('');
  let poll = $state<Poll | null>(null);
  let receipts = $state<Record<string, unknown>>({});
  let dictionary = $state('');
  let artifact = $state('');
  let policy = $state<Policy>('raw_exact');
  let sessionId = $state('');
  let sessionState = $state('');
  let query = $state('');
  let queryPending = $state(false);
  let pageResult = $state<Page | null>(null);
  let selected = $state<Row | null>(null);
  let mddSource = $state('');
  let mddIndex = $state('');
  let mddId = $state('');
  let mddState = $state('');
  let mddOpenJob = ''; 
  let info = $state<ReaderDetails | null>(null);
  let infoError = $state('');
  let previewMode = $state<'rendered' | 'split' | 'html'>('rendered');
  let previewAppearance = $state<Appearance>('original');
  let detailsOpen = $state(false);
  let preview = $state<Preview | null>(null);
  let previewBusy = $state(false);
  let previewError = $state('');
  const resourceWaiters = new Map<string, {sid:string; resolve:(page:Page)=>void; reject:(e:unknown)=>void; cleanup:()=>void}>();
  const p = (key: Parameters<typeof previewLabel>[1]) => previewLabel(locale,key);
  $effect(() => {
    const row=selected, metadata=info, appearance=previewAppearance, ready=mddState==='ready', sid=mddId, mode=previewMode;
    const controller=new AbortController();
    preview=null;previewError='';previewBusy=!!row && mode!=='html';
    if(row?.text !== undefined && mode!=='html' && metadata) {
      const style=Object.entries(metadata.attributes).find(([k])=>k.toLowerCase()==='stylesheet')?.[1] || '';
      const format=Object.entries(metadata.attributes).find(([k])=>k.toLowerCase()==='format')?.[1] || '';
      // Plain-text dictionaries must not acquire HTML semantics in the preview.
      const text=format.toLowerCase()==='text' ? '<pre>'+row.text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')+'</pre>' : row.text;
      void (async()=>{
        if(ready) {
          // Show this entry immediately while admitted MDD requests resolve.
          const initial=await renderPreview(text,style,appearance,null,controller.signal);
          if(!controller.signal.aborted)preview={...initial,warnings:initial.warnings.filter(w=>!w.startsWith('Attach a matching MDD'))};
        }
        const result=await renderPreview(text,style,appearance,ready ? (key,signal)=>loadResource(sid,key,signal) : null,controller.signal);
        if(!controller.signal.aborted){preview=result;previewBusy=false;}
      })().catch(e=>{if(!controller.signal.aborted){previewError=failure(e).message;previewBusy=false;}});
    } else if(!row || mode==='html' || infoError) previewBusy=false;
    return ()=>controller.abort();
  });
  let shuttingDown = $state(false);
  const t = (key: Label) => translate(locale, key);
  const terminal = (state: string) => ['succeeded', 'failed', 'cancelled'].includes(state);
  const converterOptions: [Converter, string][] = [['cc_cedict','CC-CEDICT'],['moe_mini','MOE Mini'],['moe_idioms','MOE Idioms'],['moe_concise','MOE Concise'],['moe_revised','MOE Revised'],['moe_revised_wfg','MOE Revised WFG']];
  const u = (key: StudioLabel) => studioLabel(locale,key);
  const workspaceNav: [View,string][] = [['build','box'],['extract','extract'],['converters','convert']];
  const dataNav: [View,string][] = [['database','database'],['morphology','leaf']];
  const activeJob = $derived(poll?.jobs.find(job => !terminal(job.state)));
  const fileName = (path:string) => path.split(/[\\/]/).pop() || '';
  const viewLabel = (key:View) => key === 'database' || key === 'morphology' ? u(key) : t(key);
  function selectView(key:View) { view=key; alert=null; if(key === 'converters')converterSetup=false; }
  function heading() { return view === 'build' ? u('buildTitle') : view === 'extract' ? u('extractTitle') : view === 'converters' && converterSetup ? u('convertTitle') : viewLabel(view); }
  function lead() { return view === 'build' ? u('buildLead') : view === 'extract' ? u('extractLead') : view === 'converters' ? u('convertersLead') : view === 'tools' ? u('toolsLead') : view === 'jobs' ? u('jobsLead') : u('laterText'); }
  function sourceType() { return view === 'build' ? u(pack === 'mdd' ? 'resourceManifest' : 'jsonl') : view === 'extract' ? u('archive') : u('converterSource'); }
  function outputKind() { return view === 'build' ? u(pack === 'mdd' ? 'mdd' : 'mdx') : view === 'extract' ? u(extraction === 'mdd' ? 'folder' : extraction === 'jsonl' ? 'jsonlOutput' : 'txt') : u('txt'); }
  function outputFormat() { return view === 'build' ? pack === 'mdd' ? 'MDD' : 'MDX v2' : view === 'extract' ? extraction === 'mdd' ? u('folder') : extraction.toUpperCase() : 'TXT'; }
  function outputEncoding() { return view === 'build' ? pack === 'mdd' ? 'UTF-16' : encoding === 'utf16' ? 'UTF-16' : 'UTF-8' : view === 'extract' && extraction === 'mdd' ? '—' : 'UTF-8'; }
  function operationLabel(operation?:string) { return operation === 'extract_mdd' || operation?.startsWith('export_') ? u('extractTitle') : operation === 'build_index' ? t('createIndex') : operation === 'convert_to_txt' ? u('convertTitle') : u('buildTitle'); }


  function applyAppearance() {
    const dark = theme === 'dark' || theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }
  $effect(() => {
    document.documentElement.lang = locale === 'zh' ? 'zh-Hans' : locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.dataset.os=platform;
    applyAppearance();
    if (!preferencesReady) return;
    try { localStorage.setItem('studio-ui', JSON.stringify({ locale, theme })); } catch { /* optional preference persistence */ }
  });
  async function action(work: () => Promise<void>) {
    if (shuttingDown) return;
    pending += 1; alert = null;
    try { await work(); } catch (e) { alert = failure(e); }
    finally { pending -= 1; }
  }
  async function pickInput(target: 'source' | 'dictionary' | 'artifact' | 'root' | 'mddSource' | 'mddIndex') {
    const result = await open({ directory: target === 'root', multiple: false });
    if (typeof result !== 'string') return;
    if (target === 'source') source = result;
    else if (target === 'dictionary') dictionary = result;
    else if (target === 'artifact') artifact = result;
    else if(target === 'mddSource') mddSource=result;
    else if(target === 'mddIndex') mddIndex=result;
    else resourceRoot = result;
  }
  async function pickOutput(index = false) {
    // Directory extraction requires a *new* directory: choose its name with save.
    const result = await save({ title: index ? t('index') : t('destination') });
    if (result) { if (index) artifact = result; else destination = result; }
  }
  async function submit() {
    if (!source || !destination) throw { code: 'invalid_input', message: t('required') };
    let request: NativeRequest;
    const metadata = { title, description, stylesheet: view === 'build' && pack === 'mdd' ? '' : stylesheet, extra: {} };
    if (view === 'build') {
      if (pack === 'mdd') {
        if (!resourceRoot) throw { code: 'invalid_input', message: t('resourceRoot') };
        request = { kind:'dictionary', request:{ operation:'pack_mdd', source, destination, resource_root:resourceRoot, metadata } };
      } else if (pack === 'block') request = { kind:'cc_packing', request:{ source, destination, encoding, metadata } };
      else request = { kind:'dictionary', request:{ operation:'pack_mdx', source, destination, encoding, metadata } };
    } else if (view === 'extract') {
      request = extraction === 'mdd' ? { kind:'extraction', request:{ source, destination } }
        : { kind:'dictionary', request:{ operation:extraction === 'txt' ? 'export_txt' : 'export_jsonl', source, destination } };
    } else {
      const profile = converter === 'cc_cedict' ? 'cc' : converter === 'moe_concise' ? 'concise' : ['moe_mini','moe_idioms'].includes(converter) ? 'small_moe' : 'grouped_moe';
      request = { kind:'conversion', request:{ profile, request:{ input:source, destination, converter, worksheet:converter === 'cc_cedict' ? null : worksheet.trim() || null } } };
    }
    await call({ action:'submit', request });
    view = 'jobs'; await refresh();
  }
  async function buildIndex() {
    if(sessionId || mddId) throw {code:'not_ready',message:p('closeFirst')};
    if (!dictionary || !artifact) throw { code:'invalid_input', message:t('required') };
    await call({ action:'submit', request:{ kind:'index', request:{ source:dictionary, destination:artifact, kind:'mdx', policy } } });
    view = 'jobs'; await refresh();
  }
  async function openReader() {
    if (!dictionary || !artifact) throw { code:'invalid_input', message:t('required') };
    const opened = await call<{session_id:string; job_id:string}>({ action:'open_reader', request:{ source:dictionary, artifact, kind:'mdx', policy } });
    sessionId = opened.session_id; sessionState = 'opening'; pageResult = null; selected = null; info=null; infoError='';
  }
  async function buildMddIndex() {
    if(sessionId || mddId) throw {code:'not_ready',message:p('closeFirst')};
    if(!mddSource || !mddIndex) throw {code:'invalid_input',message:t('required')};
    await call({action:'submit',request:{kind:'index',request:{source:mddSource,destination:mddIndex,kind:'mdd',policy:'raw_exact'}}});
    view='jobs';await refresh();
  }
  async function attachMdd() {
    if(!mddSource || !mddIndex) throw {code:'invalid_input',message:t('required')};
    const result=await call<{session_id:string;job_id:string}>({action:'open_reader',request:{source:mddSource,artifact:mddIndex,kind:'mdd',policy:'raw_exact'}});
    mddId=result.session_id;mddOpenJob=result.job_id;mddState='opening';
  }
  async function pickMddIndex() { const path=await save({title:p('mddIndex')});if(path)mddIndex=path; }
  async function resourcePage(sid:string,key:string,signal:AbortSignal):Promise<Page> {
    if(signal.aborted) throw new DOMException('Preview cancelled','AbortError');
    const result=await call<{job_id:string}>({action:'page',session_id:sid,request:{query:key,offset:0,limit:1}});
    return new Promise((resolve,reject)=>{
      const cancel=()=>{void call({action:'session_cancel',session_id:sid,job_id:result.job_id}).catch(()=>{});reject(new DOMException('Preview cancelled','AbortError'));};
      const timer=setTimeout(cancel,15000);
      const cleanup=()=>{clearTimeout(timer);signal.removeEventListener('abort',cancel);};
      // Keep ownership until the sole poll consumer takes/forgets the terminal
      // native job, even if this request is cancelled or its promise times out.
      resourceWaiters.set(result.job_id,{sid,resolve,reject,cleanup});
      signal.addEventListener('abort',cancel,{once:true});if(signal.aborted)cancel();
    });
  }
  async function loadResource(sid:string,key:string,signal:AbortSignal):Promise<Uint8Array|null> {
    for(const candidate of resourceCandidates(key)) {
      const page=await resourcePage(sid,candidate,signal);
      if(page.total>1) throw new Error('Ambiguous MDD resource: '+key);
      const bytes=page.rows[0]?.bytes;
      if(bytes) {if(bytes.length>524288)throw new Error('Resource exceeds 512 KiB: '+key);return Uint8Array.from(bytes);}
    }
    return null;
  }
  async function readDetails(sid:string) {
    try {const result=await call<ReaderDetails>({action:'reader_details',session_id:sid});if(sid===sessionId)info=result;}
    catch(e) {if(sid===sessionId)infoError=failure(e).message;}
  }
  async function lookup(offset = 0) {
    if (!query.trim() || !sessionId || queryPending) return;
    await call({ action:'page', session_id:sessionId, request:{ query, offset, limit:32 } });
    queryPending = true;
  }
  let refreshing = false;
  async function refresh() {
    if (!connected || refreshing || shuttingDown) return;
    refreshing = true;
    try {
      const next = await call<Poll>({ action:'poll' });
      poll = next;
      for (const item of next.sessions) {
        const sid = item.session.session_id;
        if (sid === sessionId) sessionState = item.session.state;
        if (sid === mddId) mddState = item.session.state;
        if(sid!==sessionId && sid!==mddId)continue;
        for (const job of item.jobs) {
          if (!terminal(job.state)) continue;
          if(sid===mddId && job.job_id!==mddOpenJob && !resourceWaiters.has(job.job_id))continue;
          const waiter=resourceWaiters.get(job.job_id);
          if(sid===sessionId && !job.result_available)queryPending=false;
          if (job.error) {if(waiter)waiter.reject(job.error);else {alert = job.error; queryPending = false;} }
          if (job.result_available) {
            const reply = await call<SessionReply | null>({ action:'session_take', session_id:sid, job_id:job.job_id });
            if(reply?.operation==='page' && waiter) waiter.resolve(reply.value as Page);
            else if (reply?.operation === 'page' && sid === sessionId) {
              pageResult = reply.value as Page; selected = pageResult.rows[0] || null; queryPending = false;
            } else if (reply?.operation === 'opened') {status = t('opened');if(sid===sessionId)void readDetails(sid);}
          }
          if(waiter){if(!job.result_available&&!job.error)waiter.reject(new Error('Resource job cancelled'));waiter.cleanup();resourceWaiters.delete(job.job_id);}
          await call({ action:'session_forget', session_id:sid, job_id:job.job_id });
        }
        if (['closed','failed'].includes(item.session.state)) {
          try {
            await call({ action:'release_reader', session_id:sid });
            if (sid === sessionId) { sessionId=''; sessionState=''; queryPending=false; pageResult=null; selected=null; info=null;infoError=''; }
            if(sid===mddId){mddId='';mddOpenJob='';mddState='';}
            for(const [id,waiter] of resourceWaiters){if(waiter.sid===sid){waiter.cleanup();waiter.reject(new Error('Resource reader closed'));resourceWaiters.delete(id);}}
          } catch (e) { if (failure(e).code !== 'still_running') throw e; }
        }
      }
    } finally { refreshing = false; }
  }
  async function collect(jobId: string) {
    const receipt = await call<unknown>({ action:'take', job_id:jobId });
    if (receipt !== null) { receipts = { ...receipts, [jobId]:receipt }; status=t('received'); }
    await refresh();
  }
  async function forget(jobId: string) {
    await call({ action:'forget', job_id:jobId });
    const next = { ...receipts }; delete next[jobId]; receipts=next; await refresh();
  }
  onMount(() => {
    let alive = true;
    let stop: (() => void) | undefined;
    try {
      const stored = JSON.parse(localStorage.getItem('studio-ui') || '{}');
      if (['en','zh','ar'].includes(stored.locale)) locale=stored.locale;
      if (['system','light','dark'].includes(stored.theme)) theme=stored.theme;
    } catch { /* use defaults */ }
    preferencesReady=true;
    const media = matchMedia('(prefers-color-scheme: dark)');
    media.addEventListener('change', applyAppearance);
    void (async () => {
      try {
        const info = await call<{platform:string}>({ action:'capabilities' });
        if (!alive) return;
        platform=info.platform; connected=true; status=''; await refresh();
        const unlisten = await listen<Failure>('studio-shutdown-error', event => { alert=event.payload; shuttingDown=true; });
        if (alive) stop=unlisten; else unlisten();
      } catch (e) { if (alive) alert=failure(e); }
    })();
    const interval = setInterval(() => { if (alive) void refresh().catch(e => { alert=failure(e); }); },400);
    return () => { for(const w of resourceWaiters.values()){w.cleanup();w.reject(new Error('Window closed'));}resourceWaiters.clear();alive=false; clearInterval(interval); stop?.(); media.removeEventListener('change',applyAppearance); };
  });
</script>

<div class="window" class:macos={platform === 'macos'}>
  <header class="titlebar" dir="ltr" data-tauri-drag-region>
    <div class="windowidentity" data-tauri-drag-region><span class="appname" data-tauri-drag-region>Mdict Studio Pro</span></div>
    <div class="controls">
      <span class="titlemeta">{t('original')}</span>
      <select bind:value={locale} aria-label={t('language')} dir="ltr"><option value="en">English</option><option value="zh">中文</option><option value="ar">العربية</option></select>
      <select bind:value={theme} aria-label={t('appearance')}><option value="system">{t('system')}</option><option value="light">{t('light')}</option><option value="dark">{t('dark')}</option></select>
    </div>
  </header>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="logo"><Icon name="book" /></div><div class="brandcopy"><strong>Studio</strong><small>{u('personal')}</small></div></div>
      <div class="section">{u('workspace')}</div>
      {#each workspaceNav as [key,icon]}
        <button class="nav" class:active={view === key} aria-current={view === key ? 'page' : undefined} onclick={() => selectView(key)} title={viewLabel(key)}><Icon name={icon}/><span class="navtext">{viewLabel(key)}</span></button>
      {/each}
      <div class="section">{u('data')}</div>
      {#each dataNav as [key,icon]}
        <button class="nav" class:active={view === key} aria-current={view === key ? 'page' : undefined} onclick={() => selectView(key)} title={viewLabel(key)+' · '+u('later')}><Icon name={icon}/><span class="navtext">{viewLabel(key)}</span><span class="soon">{u('later')}</span></button>
      {/each}
      <div class="section">{u('inspect')}</div>
      <button class="nav" class:active={view === 'tools'} aria-current={view === 'tools' ? 'page' : undefined} onclick={() => selectView('tools')} title={t('tools')}><Icon name="book"/><span class="navtext">{t('tools')}</span></button>
      <div class="sidebarbottom">
        <button class="nav" class:active={view === 'jobs'} aria-current={view === 'jobs' ? 'page' : undefined} onclick={() => selectView('jobs')} title={t('jobs')}><Icon name="jobs"/><span class="navtext">{t('jobs')}</span>{#if activeJob}<span class="job-dot"></span>{/if}</button>
        <button class="nav" class:active={settings} onclick={() => settings=!settings} title={t('settings')} aria-expanded={settings}><Icon name="settings"/><span class="navtext">{t('settings')}</span></button>
        <div class="local"><span class="dot"></span><span>{u('local')}</span></div>
      </div>
    </aside>
    <main class="main">
      <header class="top"><div><div class="eyebrow">{u('workspace')}</div><h1>{heading()}</h1><p>{lead()}</p></div><span class="tag">{view === 'tools' ? 'MDX + MDD' : 'MDX / MDD'}</span></header>
      <div class="body">
        {#if settings}
          <section class="settings-panel" aria-label={t('settings')}>
            <div><b>{t('settings')}</b><p class="note">{t('deferred')}</p></div>
            <label for="settings-language">{t('language')}</label><select id="settings-language" bind:value={locale}><option value="en">English</option><option value="zh">中文</option><option value="ar">العربية</option></select>
            <label for="settings-theme">{t('appearance')}</label><select id="settings-theme" bind:value={theme}><option value="system">{t('system')}</option><option value="light">{t('light')}</option><option value="dark">{t('dark')}</option></select><button class="smallbutton" onclick={() => settings=false}>{t('done')}</button>
          </section>
        {/if}
        {#if !connected}<p class="notice" role="status">{alert ? t('nativeOnly') : t('loading')}</p>{/if}
        {#if alert}<div class="error" role="alert"><b>{alert.code}</b><span>{alert.message}</span></div>{/if}
        {#if view === 'build' || view === 'extract' || view === 'converters' && converterSetup}
          <div class="buildlayout">
            <form class="form" onsubmit={e => {e.preventDefault();void action(submit);}}>
              <fieldset disabled={!connected || pending > 0 || shuttingDown}>
                {#if view === 'converters'}<button class="backbutton" type="button" onclick={() => converterSetup=false}><Icon name="back"/>{u('selectConverter')}</button>{/if}
                <div class="formsection"><span>{u('source')}</span><small>{u('stepOne')}</small></div>
                <div class="sourcecard"><div class="fileicon"><Icon name="file"/></div><div class="filetext"><b><bdi>{fileName(source) || u('chooseSource')}</bdi></b><small>{sourceType()}</small></div><button class="smallbutton" type="button" onclick={() => action(() => pickInput('source'))}>{t('choose')}</button></div>
                <div class="note sourcehint">{#if source}<Icon name="check"/>{/if}<span>{source ? u('sourceHint') : u('noSource')}</span></div>
                <div class="formsection"><span>{view === 'converters' ? u('configureConverter') : u('dictionary')}</span><small>{u('stepTwo')}</small></div>
                <div class="fields">
                  {#if view === 'build'}
                    <div class="field"><label for="dictionary-name">{u('name')}</label><input id="dictionary-name" bind:value={title} autocomplete="off" /></div>
                    <div class="field"><label for="dictionary-format">{u('format')}</label><select id="dictionary-format" value={pack === 'mdd' ? 'mdd' : 'mdx'} onchange={e => pack=e.currentTarget.value === 'mdd' ? 'mdd' : 'generic'}><option value="mdx">MDX</option><option value="mdd">MDD</option></select></div>
                    {#if pack !== 'mdd'}<div class="field"><label for="dictionary-encoding">{t('encoding')}</label><select id="dictionary-encoding" bind:value={encoding}><option value="utf8">UTF-8</option><option value="utf16">UTF-16</option></select></div>{/if}
                  {:else if view === 'extract'}
                    <div class="field"><label for="extract-operation">{t('operation')}</label><select id="extract-operation" bind:value={extraction}><option value="txt">{t('exportTxt')}</option><option value="jsonl">{t('exportJsonl')}</option><option value="mdd">{t('extractMdd')}</option></select></div>
                  {:else}
                    <div class="field"><label for="converter-name">{t('converter')}</label><select id="converter-name" bind:value={converter}>{#each converterOptions as [value,name]}<option {value}>{name}</option>{/each}</select></div>
                    {#if converter !== 'cc_cedict'}<div class="field"><label for="converter-worksheet">{t('worksheet')}</label><input id="converter-worksheet" bind:value={worksheet} maxlength="1024" /></div>{/if}
                    <div class="field"><span class="field-label">{u('format')}</span><span class="field-value">TXT · UTF-8</span></div>
                  {/if}
                  {#if view === 'build' && pack === 'mdd'}<div class="field path-field"><label for="resource-root">{t('resourceRoot')}</label><input id="resource-root" bind:value={resourceRoot} required dir="auto"/><button type="button" class="smallbutton iconbutton" aria-label={t('resourceRoot')} onclick={() => action(() => pickInput('root'))}><Icon name="folder"/></button></div>{/if}
                  <div class="field path-field"><label for="output-path">{u('saveTo')}</label><input id="output-path" bind:value={destination} required dir="auto" placeholder={u('chooseDestination')}/><button type="button" class="smallbutton iconbutton" aria-label={t('destination')} onclick={() => action(() => pickOutput())}>…</button></div>
                </div>
                <details class="advanced">
                  <summary>{u('more')}{#if view === 'build' && pack !== 'mdd'}<span class="profile-caption"> · {u(pack === 'block' ? 'block' : 'bounded')}</span>{/if}</summary>
                  <div class="advanced-content">
                    <label for="source-path">{u('inputDetails')}</label><input id="source-path" bind:value={source} dir="auto" />
                    {#if view === 'build'}
                      {#if pack !== 'mdd'}<label for="pack-profile">{u('profile')}</label><select id="pack-profile" bind:value={pack}><option value="generic">{t('buildGeneric')}</option><option value="block">{t('buildBlock')}</option></select>{/if}
                      <label for="dictionary-description">{t('description')}</label><textarea id="dictionary-description" bind:value={description} rows="3"></textarea>
                      {#if pack !== 'mdd'}<label for="dictionary-stylesheet">{t('stylesheet')}</label><textarea id="dictionary-stylesheet" bind:value={stylesheet} rows="4" dir="ltr"></textarea>{/if}
                      <p class="note">{t('inputHint')}</p><pre class="manifest-help">{t('manifestHint')}</pre>
                    {/if}
                  </div>
                </details>
                <p class="note publication-note">{t('noOverwrite')}</p>
                <div class="actions"><span class="note">{u('local')}</span><button class="primary" type="submit">{u(view === 'build' ? 'buildTitle' : view === 'extract' ? 'extractTitle' : 'convertTitle')}</button></div>
              </fieldset>
            </form>
            <aside class="summary">
              <h2>{u('output')}</h2><div class="outputtile"><Icon name={view === 'extract' ? 'extract' : 'book'}/><b><bdi>{fileName(destination) || u('noOutput')}</bdi></b><small>{outputKind()}</small></div>
              <div class="stat"><span>{u('format')}</span><bdi>{outputFormat()}</bdi></div><div class="stat"><span>{t('encoding')}</span><bdi>{outputEncoding()}</bdi></div><div class="stat"><span>{u('location')}</span><span>{u('localFolder')}</span></div>
              {#if view === 'build' && pack !== 'mdd'}<div class="stat"><span>{u('profile')}</span><span>{u(pack === 'block' ? 'block' : 'bounded')}</span></div>{/if}
              <div class="checklist">{#if view === 'build'}<p><Icon name="check"/><span>{u('duplicate')}</span></p>{/if}<p><Icon name="check"/><span>{u('noClobber')}</span></p><p><Icon name="check"/><span>{u('background')}</span></p></div><p class="note" style="margin-top:25px">{u('outputHint')}</p>
            </aside>
          </div>
        {:else if view === 'converters'}
          <section class="page"><h2>{u('selectConverter')}</h2><p>{u('convertersLead')}</p><div class="convertergrid">{#each converterOptions as [value,name]}<button class="converter" onclick={() => {converter=value;converterSetup=true;}}><Icon name="convert"/><strong>{name}</strong><small>{u('configureConverter')} → TXT</small></button>{/each}</div></section>
        {:else if view === 'database' || view === 'morphology'}
          <section class="page"><span class="tag">{u('later')}</span><h2 style="margin-top:18px">{viewLabel(view)}</h2><p>{u('laterText')}</p><p>{t('deferred')}</p></section>
        {:else if view === 'jobs'}
          <section class="page jobs-page">
            {#each poll?.jobs || [] as job (job.job_id)}
              <article class="jobcard job">
                <div class="job-head"><div class="jobmark"><Icon name="jobs"/></div><div class="job-description"><b>{operationLabel(job.operation)}</b><small><bdi>{job.job_id}</bdi></small></div><span class="jobstate">{t(job.state as Label)}</span></div>
                {#if job.latest_progress}<p class="note">{job.latest_progress.phase} · {job.latest_progress.completed} / {job.latest_progress.total || '—'}</p>{#if !terminal(job.state)}<progress max={Math.max(1,job.latest_progress.total)} value={job.latest_progress.total ? job.latest_progress.completed : undefined}></progress>{/if}{/if}
                {#if job.cancel_requested}<p class="note">{t('cancelling')}</p>{/if}
                {#if job.error}<p class="job-error">{job.error.code}: {job.error.message}</p>{#if job.error.publication_uncertain}<p class="job-error">{t('uncertain')}</p>{/if}{/if}
                <div class="job-buttons">{#if !terminal(job.state)}<button class="smallbutton" disabled={pending > 0} onclick={() => action(async () => {await call({action:'cancel',job_id:job.job_id});await refresh();})}>{t('cancel')}</button>{/if}{#if job.result_available}<button class="smallbutton" disabled={pending > 0} onclick={() => action(() => collect(job.job_id))}>{t('take')}</button>{/if}{#if terminal(job.state)}<button class="smallbutton" disabled={pending > 0} onclick={() => action(() => forget(job.job_id))}>{t('forget')}</button>{/if}</div>
                {#if receipts[job.job_id]}<details><summary>{u('receipt')}</summary><pre>{JSON.stringify(receipts[job.job_id],null,2)}</pre></details>{/if}
              </article>
            {:else}<div class="empty"><Icon name="jobs"/><p>{t('noJobs')}</p></div>{/each}
          </section>
        {:else if view === 'tools'}
          <div class="tools-workspace">
            <details class="reader-setup" open={!sessionId}>
              <summary>{t('open')}{#if sessionId}<bdi> · {fileName(dictionary)}</bdi>{/if}</summary>
              <fieldset disabled={!connected || pending > 0 || shuttingDown}>
                <div class="fields">
                  <div class="field path-field"><label for="reader-source">{u('source')}</label><input id="reader-source" bind:value={dictionary} disabled={!!sessionId} dir="auto"/><button class="smallbutton" disabled={!!sessionId} onclick={() => action(() => pickInput('dictionary'))}>{t('choose')}</button></div>
                  <div class="field path-field"><label for="reader-index">{t('index')}</label><input id="reader-index" bind:value={artifact} disabled={!!sessionId} dir="auto"/><button class="smallbutton" disabled={!!sessionId} onclick={() => action(() => pickInput('artifact'))}>{t('choose')}</button><button class="smallbutton" disabled={!!sessionId} aria-label={u('newIndex')} onclick={() => action(() => pickOutput(true))}>+</button></div>
                  <div class="field"><label for="reader-policy">{t('policy')}</label><select id="reader-policy" bind:value={policy} disabled={!!sessionId}><option value="raw_exact">{t('exact')}</option><option value="header_ascii_v1">{t('header')}</option></select></div>
                </div>
                <div class="job-buttons"><button class="smallbutton" disabled={!!sessionId || !!mddId} onclick={() => action(buildIndex)}>{t('createIndex')}</button><button class="smallbutton" disabled={!!sessionId} onclick={() => action(openReader)}>{t('open')}</button><button class="smallbutton" disabled={!sessionId || sessionState === 'closing'} onclick={() => action(async () => {await call({action:'close_reader',session_id:sessionId});sessionState='closing';})}>{t('close')}</button></div>
              </fieldset><p class="note">{t('indexHint')}</p>
            </details>
            <details class="reader-setup mdd-setup">
              <summary>{p('resources')} · <bdi>{mddId ? fileName(mddSource) : p('missing')}</bdi></summary>
              <fieldset disabled={!connected || pending > 0 || shuttingDown}>
                <div class="fields">
                  <div class="field path-field"><label for="mdd-source">{p('mddSource')}</label><input id="mdd-source" bind:value={mddSource} disabled={!!mddId} dir="auto"/><button class="smallbutton" disabled={!!mddId} onclick={()=>action(()=>pickInput('mddSource'))}>{t('choose')}</button></div>
                  <div class="field path-field"><label for="mdd-index">{p('mddIndex')}</label><input id="mdd-index" bind:value={mddIndex} disabled={!!mddId} dir="auto"/><button class="smallbutton" disabled={!!mddId} onclick={()=>action(()=>pickInput('mddIndex'))}>{t('choose')}</button><button class="smallbutton" disabled={!!mddId} aria-label={u('newIndex')} onclick={()=>action(pickMddIndex)}>+</button></div>
                </div>
                <div class="job-buttons"><button class="smallbutton" disabled={!!sessionId || !!mddId} onclick={()=>action(buildMddIndex)}>{p('build')}</button><button class="smallbutton" disabled={!!mddId} onclick={()=>action(attachMdd)}>{p('attach')}</button><button class="smallbutton" disabled={!mddId || mddState==='closing'} onclick={()=>action(async()=>{await call({action:'close_reader',session_id:mddId});mddState='closing';})}>{p('detach')}</button></div>
              </fieldset><p class="note">{p('indexHint')}</p>
            </details>
            <form class="lookup-form" onsubmit={e => {e.preventDefault();void action(() => lookup());}}><label class="search"><Icon name="search"/><input bind:value={query} maxlength="4096" placeholder={t('query')} aria-label={t('query')}/></label><button type="submit" class="smallbutton" disabled={sessionState !== 'ready' || queryPending || pending > 0}>{t('search')}</button></form>
            <div class="tools">
              <aside class="wordpanel"><div class="wordslabel">{u('records')}<bdi>{pageResult?.total ?? 0}</bdi></div><div class="wordlist">{#each pageResult?.rows || [] as row}<button class="word" class:active={selected?.ordinal === row.ordinal} onclick={() => selected=row}><b><bdi>{row.key}</bdi></b><small>#{row.ordinal}</small></button>{:else}<p class="note">{t('noEntries')}</p>{/each}</div>{#if pageResult?.next_offset !== null && pageResult?.next_offset !== undefined}<button class="smallbutton" disabled={queryPending || pending > 0} onclick={() => action(() => lookup(pageResult!.next_offset!))}>{t('next')}</button>{/if}</aside>
              <section class="reading">
                <div class="readingbar"><div class="segment" aria-label={t('tools')}>
                  {#each ['rendered','split','html'] as mode}<button class:active={previewMode===mode} aria-pressed={previewMode===mode} onclick={()=>previewMode=mode as typeof previewMode}>{p(mode as 'rendered'|'split'|'html')}</button>{/each}
                </div><div class="preview-controls"><select bind:value={previewAppearance} aria-label={p('appearance')}><option value="original">{p('original')}</option><option value="paper">{p('paper')}</option><option value="dark">{p('dark')}</option></select><button class="smallbutton" class:active={detailsOpen} aria-expanded={detailsOpen} onclick={()=>detailsOpen=!detailsOpen}>{p('details')}</button></div></div>
                <div class="reading-content" class:has-details={detailsOpen}>
                  <div class="entry-views" class:split={previewMode==='split'}>
                    {#if previewMode!=='html'}<div class="preview-pane">
                      {#if preview}<iframe class="dictionary-preview" title={p('rendered')} sandbox="" referrerpolicy="no-referrer" srcdoc={preview.document}></iframe>
                      {:else}<div class="preview-placeholder">{!selected?p('empty'):previewBusy?p('loading'):p('unavailable')}{#if previewError || infoError}<p class="note">{previewError || infoError}</p>{/if}</div>{/if}
                    </div>{/if}
                    {#if previewMode!=='rendered'}<pre class="definition-source">{selected ? selected.text?.slice(0,65536) ?? `${selected.bytes?.length || 0} bytes` : t('selectEntry')}</pre>{/if}
                  </div>
                  {#if detailsOpen}<aside class="entry-inspector" aria-label={p('details')}>
                    <h3>{p('record')}</h3><dl><dt>{t('query')}</dt><dd dir="auto">{selected?.key || '—'}</dd><dt>{p('ordinal')}</dt><dd>{selected?.ordinal ?? '—'}</dd><dt>{p('characters')}</dt><dd>{selected?.text?.length ?? 0}</dd><dt>{p('records')}</dt><dd>{String(info?.manifest.records ?? '—')}</dd><dt>{p('sourceHash')}</dt><dd class="hash">{info?.source_sha256 || '—'}</dd><dt>{p('count')}</dt><dd>{preview?.resources || 0}</dd><dt>{p('bytes')}</dt><dd>{preview?.bytes || 0}</dd></dl>
                    <h3>{p('metadata')}</h3>{#if info}<dl>{#each Object.entries(info.attributes) as [key,value]}<dt>{key}</dt><dd dir="auto"><pre>{value.slice(0,4096)}</pre>{#if value.length>4096}…{/if}</dd>{/each}</dl>{:else}<p class="note">{infoError || p('noMetadata')}</p>{/if}
                    <h3>{p('warnings')}</h3>{#each preview?.warnings || [] as warning}<p class="note">{warning}</p>{:else}<p class="note">{previewError || infoError || p('noWarnings')}</p>{/each}<p class="note">{p('profile')}</p>
                  </aside>{/if}
                </div>
                <div class="readingfoot"><span>{previewBusy?p('loading'):p('staticHint')}</span>{#if selected?.text && selected.text.length>65536 && previewMode!=='rendered'}<span>{t('clipping')}</span>{/if}</div>
              </section>
            </div>
          </div>
        {/if}
      </div>
    </main>
  </div>
  {#if activeJob}
    <div class="jobbar"><Icon name="jobs"/><div class="progress"><div class="progresshead"><span>{operationLabel(activeJob.operation)}</span><span>{t(activeJob.state as Label)}</span></div>{#if activeJob.latest_progress}<progress max={Math.max(1,activeJob.latest_progress.total)} value={activeJob.latest_progress.total ? activeJob.latest_progress.completed : undefined}></progress>{:else}<progress></progress>{/if}</div><button class="smallbutton" disabled={pending > 0 || activeJob.cancel_requested} onclick={() => action(async () => {if(activeJob)await call({action:'cancel',job_id:activeJob.job_id});await refresh();})}>{t(activeJob.cancel_requested ? 'cancelling' : 'cancel')}</button></div>
  {/if}
  <footer class="footer"><div class="footerleft"><span class="dot" class:offline={!connected}></span><span>{status || t(connected ? 'ready' : 'loading')}</span></div><span>{poll ? `${t('active')}: ${poll.admission.active_operations} / ${poll.admission.max_operations}` : t('original')}</span></footer>
</div>
