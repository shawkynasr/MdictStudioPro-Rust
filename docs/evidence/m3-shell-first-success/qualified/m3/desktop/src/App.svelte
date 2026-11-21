<script lang="ts">
  import { onMount } from 'svelte';
  import { open, save } from '@tauri-apps/plugin-dialog';
  import { listen } from '@tauri-apps/api/event';
  import { call, failure } from './bridge';
  import type { Converter, Encoding, Failure, NativeRequest, Page, Policy, Poll, Row, SessionReply } from './bridge';
  import { translate } from './i18n';
  import type { Label, Locale } from './i18n';

  type View = 'build' | 'extract' | 'converters' | 'tools' | 'jobs';
  let locale = $state<Locale>('en');
  let theme = $state('system');
  let view = $state<View>('build');
  let platform = $state('');
  let connected = $state(false);
  let pending = $state(0);
  let alert = $state<Failure | null>(null);
  let status = $state('');
  let settings = $state(false);
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
  let shuttingDown = $state(false);
  const t = (key: Label) => translate(locale, key);
  const terminal = (state: string) => ['succeeded', 'failed', 'cancelled'].includes(state);
  const converterOptions: [Converter, string][] = [['cc_cedict','CC-CEDICT'],['moe_mini','MOE Mini'],['moe_idioms','MOE Idioms'],['moe_concise','MOE Concise'],['moe_revised','MOE Revised'],['moe_revised_wfg','MOE Revised WFG']];
  const nav: [View, string][] = [['build','◇'],['extract','↓'],['converters','⇄'],['tools','▤'],['jobs','◷']];

  function applyAppearance() {
    const dark = theme === 'dark' || theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }
  $effect(() => {
    document.documentElement.lang = locale === 'zh' ? 'zh-Hans' : locale;
    document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr';
    applyAppearance();
    try { localStorage.setItem('studio-ui', JSON.stringify({ locale, theme })); } catch { /* optional preference persistence */ }
  });
  async function action(work: () => Promise<void>) {
    if (shuttingDown) return;
    pending += 1; alert = null;
    try { await work(); } catch (e) { alert = failure(e); }
    finally { pending -= 1; }
  }
  async function pickInput(target: 'source' | 'dictionary' | 'artifact' | 'root') {
    const result = await open({ directory: target === 'root', multiple: false });
    if (typeof result !== 'string') return;
    if (target === 'source') source = result;
    else if (target === 'dictionary') dictionary = result;
    else if (target === 'artifact') artifact = result;
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
    if (!dictionary || !artifact) throw { code:'invalid_input', message:t('required') };
    await call({ action:'submit', request:{ kind:'index', request:{ source:dictionary, destination:artifact, kind:'mdx', policy } } });
    view = 'jobs'; await refresh();
  }
  async function openReader() {
    if (!dictionary || !artifact) throw { code:'invalid_input', message:t('required') };
    const opened = await call<{session_id:string; job_id:string}>({ action:'open_reader', request:{ source:dictionary, artifact, kind:'mdx', policy } });
    sessionId = opened.session_id; sessionState = 'opening'; pageResult = null; selected = null;
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
        for (const job of item.jobs) {
          if (!terminal(job.state)) continue;
          if (job.error) { alert = job.error; queryPending = false; }
          if (job.result_available) {
            const reply = await call<SessionReply | null>({ action:'session_take', session_id:sid, job_id:job.job_id });
            if (reply?.operation === 'page' && sid === sessionId) {
              pageResult = reply.value as Page; selected = pageResult.rows[0] || null; queryPending = false;
            } else if (reply?.operation === 'opened') status = t('opened');
          }
          await call({ action:'session_forget', session_id:sid, job_id:job.job_id });
        }
        if (['closed','failed'].includes(item.session.state)) {
          try {
            await call({ action:'release_reader', session_id:sid });
            if (sid === sessionId) { sessionId=''; sessionState=''; queryPending=false; pageResult=null; selected=null; }
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
    return () => { alive=false; clearInterval(interval); stop?.(); media.removeEventListener('change',applyAppearance); };
  });
</script>

<div class:macos={platform === 'macos'} class="app">
  <header class="app-head" data-tauri-drag-region>
    <strong data-tauri-drag-region>Mdict Studio Pro</strong><span data-tauri-drag-region>{t('original')}</span>
    <button onclick={() => settings=!settings} aria-label={t('settings')}>⚙</button>
  </header>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span class="mark">M</span><div><b>Studio</b><small>{t('subtitle')}</small></div></div>
      <nav aria-label="Workspace">
        {#each nav as [key, icon]}
          <button class:active={view === key} aria-current={view === key ? 'page' : undefined} onclick={() => { view=key; alert=null; }}><span class="nav-icon" aria-hidden="true">{icon}</span>{t(key)}</button>
        {/each}
      </nav>
      <p class="deferred">{t('deferred')}</p>
    </aside>
    <main>
      <div class="heading"><div><small>Mdict Studio</small><h1>{t(view)}</h1></div><span class="badge">MDict v2</span></div>
      {#if !connected}<p class="notice">{alert ? t('nativeOnly') : t('loading')}</p>{/if}
      {#if alert}<div class="error" role="alert"><b>{alert.code}</b><span>{alert.message}</span></div>{/if}
      {#if settings}
        <section class="settings" aria-label={t('settings')}>
          <label>{t('language')}<select bind:value={locale}><option value="en">English</option><option value="zh">中文</option><option value="ar">العربية</option></select></label>
          <label>{t('appearance')}<select bind:value={theme}><option value="system">{t('system')}</option><option value="light">{t('light')}</option><option value="dark">{t('dark')}</option></select></label>
          <button onclick={() => settings=false}>{t('done')}</button>
        </section>
      {/if}
      {#if ['build','extract','converters'].includes(view)}
        <form onsubmit={e => { e.preventDefault(); void action(submit); }}>
          <fieldset disabled={!connected || pending > 0 || shuttingDown}>
            <section class="card">
              {#if view === 'build'}
                <label>{t('profile')}<select bind:value={pack}><option value="generic">{t('buildGeneric')}</option><option value="block">{t('buildBlock')}</option><option value="mdd">{t('buildMdd')}</option></select></label>
              {:else if view === 'extract'}
                <label>{t('operation')}<select bind:value={extraction}><option value="txt">{t('exportTxt')}</option><option value="jsonl">{t('exportJsonl')}</option><option value="mdd">{t('extractMdd')}</option></select></label>
              {:else}
                <label>{t('converter')}<select bind:value={converter}>{#each converterOptions as [value,name]}<option {value}>{name}</option>{/each}</select></label>
                {#if converter !== 'cc_cedict'}<label>{t('worksheet')}<input bind:value={worksheet} maxlength="1024" /></label>{/if}
              {/if}
              <div class="path-row"><label>{t('source')}<input bind:value={source} required dir="auto" /></label><button type="button" onclick={() => action(() => pickInput('source'))}>{t('choose')}</button></div>
              <div class="path-row"><label>{t('destination')}<input bind:value={destination} required dir="auto" /></label><button type="button" onclick={() => action(() => pickOutput())}>{t('choose')}</button></div>
              {#if view === 'build' && pack === 'mdd'}<div class="path-row"><label>{t('resourceRoot')}<input bind:value={resourceRoot} required dir="auto" /></label><button type="button" onclick={() => action(() => pickInput('root'))}>{t('choose')}</button></div>{/if}
              {#if view === 'build'}
                {#if pack !== 'mdd'}<label>{t('encoding')}<select bind:value={encoding}><option value="utf8">UTF-8</option><option value="utf16">UTF-16</option></select></label>{/if}
                <label>{t('title')}<input bind:value={title} /></label>
                <details><summary>{t('description')} / {t('stylesheet')}</summary>
                  <label>{t('description')}<textarea bind:value={description} rows="3"></textarea></label>
                  {#if pack !== 'mdd'}<label>{t('stylesheet')}<textarea bind:value={stylesheet} rows="4" dir="ltr"></textarea></label>{/if}
                </details>
              {/if}
            </section>
            <p class="hint">{t('noOverwrite')}</p>
            {#if view === 'build'}<p class="hint">{t('inputHint')}</p><details class="hint"><summary>JSONL</summary><pre>{t('manifestHint')}</pre></details>{/if}
            <div class="actions"><button class="primary" type="submit">{t('start')}</button></div>
          </fieldset>
        </form>
      {:else if view === 'jobs'}
        <div class="job-list">
          {#each poll?.jobs || [] as job (job.job_id)}
            <article class="card job">
              <div class="job-head"><b>{job.operation}</b><span>{t(job.state as Label)}</span></div>
              <small><bdi>{job.job_id}</bdi></small>
              {#if job.latest_progress}
                <p class="hint">{job.latest_progress.phase} · {job.latest_progress.completed} / {job.latest_progress.total || '—'}</p>
                {#if !terminal(job.state)}<progress max={Math.max(1,job.latest_progress.total)} value={job.latest_progress.total ? job.latest_progress.completed : undefined}></progress>{/if}
              {/if}
              {#if job.cancel_requested}<p class="hint">{t('cancelling')}</p>{/if}
              {#if job.error}<p class="job-error">{job.error.code}: {job.error.message}</p>{#if job.error.publication_uncertain}<p class="job-error">{t('uncertain')}</p>{/if}{/if}
              <div class="job-buttons">
                {#if !terminal(job.state)}<button disabled={pending > 0} onclick={() => action(async () => { await call({action:'cancel',job_id:job.job_id}); await refresh(); })}>{t('cancel')}</button>{/if}
                {#if job.result_available}<button disabled={pending > 0} onclick={() => action(() => collect(job.job_id))}>{t('take')}</button>{/if}
                {#if terminal(job.state)}<button disabled={pending > 0} onclick={() => action(() => forget(job.job_id))}>{t('forget')}</button>{/if}
              </div>
              {#if receipts[job.job_id]}<details><summary>{t('receipt')}</summary><pre>{JSON.stringify(receipts[job.job_id],null,2)}</pre></details>{/if}
            </article>
          {:else}<p class="empty">{t('noJobs')}</p>{/each}
        </div>
      {:else}
        <section class="card">
          <fieldset disabled={!connected || pending > 0 || shuttingDown}>
            <div class="path-row"><label>{t('source')}<input bind:value={dictionary} disabled={!!sessionId} /></label><button disabled={!!sessionId} onclick={() => action(() => pickInput('dictionary'))}>{t('choose')}</button></div>
            <div class="path-row"><label>{t('index')}<input bind:value={artifact} disabled={!!sessionId} /></label><button disabled={!!sessionId} onclick={() => action(() => pickInput('artifact'))}>{t('choose')}</button><button disabled={!!sessionId} onclick={() => action(() => pickOutput(true))}>+</button></div>
            <label>{t('policy')}<select bind:value={policy} disabled={!!sessionId}><option value="raw_exact">{t('exact')}</option><option value="header_ascii_v1">{t('header')}</option></select></label>
            <div class="job-buttons"><button disabled={!!sessionId} onclick={() => action(buildIndex)}>{t('createIndex')}</button><button disabled={!!sessionId} onclick={() => action(openReader)}>{t('open')}</button><button disabled={!sessionId || sessionState === 'closing'} onclick={() => action(async () => { await call({action:'close_reader',session_id:sessionId}); sessionState='closing'; })}>{t('close')}</button></div>
          </fieldset>
          <p class="hint">{t('indexHint')}</p>
          {#if sessionId}<p class="hint"><bdi>{sessionId}</bdi> · {sessionState}</p>{/if}
        </section>
        <form class="search-form" onsubmit={e => { e.preventDefault(); void action(() => lookup()); }}>
          <label>{t('query')}<input bind:value={query} maxlength="4096" /></label><button type="submit" class="primary" disabled={sessionState !== 'ready' || queryPending || pending > 0}>{t('search')}</button>
        </form>
        <p class="hint">{t('sourceOnly')}</p>
        <div class="dictionary">
          <div class="entry-list">{#each pageResult?.rows || [] as row}<button class:chosen={selected?.ordinal === row.ordinal} onclick={() => selected=row}><bdi>{row.key}</bdi><small>#{row.ordinal}</small></button>{:else}<p class="hint">{t('noEntries')}</p>{/each}
            {#if pageResult?.next_offset !== null && pageResult?.next_offset !== undefined}<button disabled={queryPending || pending > 0} onclick={() => action(() => lookup(pageResult!.next_offset!))}>{t('next')}</button>{/if}
          </div>
          <section class="source-pane"><h2>{t('sourceView')}</h2><pre>{selected ? selected.text?.slice(0,65536) ?? `${selected.bytes?.length || 0} bytes` : t('selectEntry')}</pre>{#if selected?.text && selected.text.length > 65536}<p class="hint">{t('clipping')}</p>{/if}</section>
        </div>
      {/if}
    </main>
  </div>
  <footer><span>{status || t(connected ? 'ready' : 'loading')}</span>{#if poll}<span>{t('active')}: {poll.admission.active_operations} / {poll.admission.max_operations}</span>{/if}</footer>
</div>
