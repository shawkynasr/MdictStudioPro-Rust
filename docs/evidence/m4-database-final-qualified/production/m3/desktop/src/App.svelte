<script lang="ts">
  import { databaseLabel } from './database-labels';
  import { databaseOutputPath } from './database-path';
  import { DatabaseBrowser } from './database-reader';
  import { databasePreviewInput } from './database-preview';
  import type { DatabaseOperation } from './database-path';
  import { stylesheetLabel } from './stylesheet-labels';
  import { pluginLabel } from './plugin-labels';
  import { redirectLabel } from './redirect-labels';
  import { entryCopyRequest, entryDeleteRequest, entryAddRequest } from './database-entry';
  import { metadataCopyRequest } from './database-metadata';
  import { metadataLabel } from './metadata-labels';
  import { extractLabel } from './extract-labels';
  import { exportFilePath, sourceParent, resourceFolderName, resourceDestination } from './extract-path';
  import type { ExtractOperation } from './extract-path';
  import { mddLabel } from './mdd-labels';
  import { dictionaryOutputPath } from './output-path';
  import { buildLabel } from './build-labels';
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
  import type { Converter, Encoding, Failure, NativeRequest, Page, Policy, Poll, Row, SessionReply, ReaderDetails, TxtProfile, Resolved, DatabasePage, DatabaseRow, DatabaseReaderSnapshot } from './bridge';
  import { translate } from './i18n';
  import type { Label, Locale } from './i18n';

  type View = 'build' | 'extract' | 'converters' | 'tools' | 'jobs' | 'database' | 'morphology' | 'plugins';
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
  let pluginPython = $state('');
  let pluginFile = $state('');
  let pluginClass = $state('NoisyPlugin');
  let pluginSource = $state('');
  let pluginParent = $state('');
  let pluginFolder = $state('plugin-result');
  let pluginTrusted = $state(false);
  const y = (key: Parameters<typeof pluginLabel>[1]) => pluginLabel(locale,key);
  async function pickPluginFile(kind:'python'|'plugin'|'source'|'parent') {
    const path=await open({directory:kind==='parent',multiple:false,...(kind==='plugin'?{filters:[{name:'Python',extensions:['py']}]}:{})});
    if(typeof path!=='string')return;
    if(kind==='python')pluginPython=path;
    if(kind==='plugin'){pluginFile=path;pluginTrusted=false;}
    if(kind==='source')pluginSource=path;
    if(kind==='parent')pluginParent=path;
  }
  async function runPlugin() {
    const destination=resourceDestination(pluginParent,pluginFolder);
    if(!destination || !pluginPython || !pluginFile || !pluginSource || !pluginClass || !pluginTrusted)throw {code:'invalid_input',message:y('required')};
    if(sessionId || mddId)throw {code:'resource_limit',message:y('close')};
    await call({action:'submit',request:{kind:'python_plugin',request:{python:pluginPython,plugin:pluginFile,class_name:pluginClass,source:pluginSource,destination,trusted:pluginTrusted}}});
    view='jobs';await refresh();
  }

  let databaseOperation = $state<DatabaseOperation>('txt_to_db');
  let databaseSource = $state('');
  let databaseDestination = $state('');
  let databaseProfile = $state<TxtProfile>('canonical_v1');
  const d = (key: Parameters<typeof databaseLabel>[1]) => databaseLabel(locale,key);
  function changeDatabaseOperation() {databaseSource='';databaseDestination='';}
  async function pickDatabaseSource() {
    const path=await open({multiple:false,filters:[{name:databaseOperation==='jsonl_to_db'?'JSONL':databaseOperation==='txt_to_db'?'TXT':databaseOperation==='mdx_to_db'?'MDX':'SQLite',extensions:databaseOperation==='jsonl_to_db'?['jsonl']:databaseOperation==='txt_to_db'?['txt']:databaseOperation==='mdx_to_db'?['mdx']:['db','sqlite','sqlite3']}]});
    if(typeof path==='string')databaseSource=path;
  }
  async function pickDatabaseDestination() {
    const extension=databaseOperation==='db_to_mdx'?'mdx':databaseOperation==='db_to_txt'?'txt':databaseOperation==='db_to_jsonl'?'jsonl':'db';
    const path=await save({defaultPath:'dictionary.'+extension,filters:[{name:extension.toUpperCase(),extensions:[extension]}]});
    if(path)databaseDestination=databaseOutputPath(path,databaseOperation);
  }
  async function runDatabase() {
    await closeDatabaseRead();
    const destination=databaseOutputPath(databaseDestination,databaseOperation);
    if(!databaseSource || !destination || databaseSource===destination)throw {code:'invalid_input',message:d('required')};
    if(sessionId || mddId)throw {code:'resource_limit',message:d('closed')};
    databaseDestination=destination;
    const request:NativeRequest={kind:'database',request:databaseOperation==='txt_to_db'?{operation:'txt_to_db',source:databaseSource,destination,profile:databaseProfile}:{operation:databaseOperation,source:databaseSource,destination}};
    await call({action:'submit',request});view='jobs';await refresh();
  }

  let databaseReadSource = $state('');
  let databaseReadQuery = $state('');
  let databaseReadMode = $state<'all'|'exact'|'prefix'|'pattern'|'definition'>('all');
  let databaseReadLimit = $state(16);
  let databaseMatching = $state<'literal'|'unicode16_lower'>('literal');
  let databaseReadPage = $state<DatabasePage|null>(null);
  let databaseSelected = $state<DatabaseRow|null>(null);
  let databaseEntryEditing=$state<DatabaseRow|null>(null),databaseEntryText=$state(''),databaseEntryKey=$state(''),databaseRenameKey=$state(false),databaseEntryDeleting=$state(false),databaseEntryAdding=$state(false);
  let databaseReadBusy = $state(false);
  let databaseSnapshotOpen = $state(false);
  let databaseEditTitle=$state(''),databaseEditDescription=$state(''),databaseEditStyle=$state('');
  let databaseReplaceTitle=$state(false),databaseReplaceDescription=$state(false),databaseReplaceStyle=$state(false);
  const databaseBrowser = new DatabaseBrowser(command=>call(command));
  let databaseReadEpoch = 0;
  function resetDatabaseRead(close=false) {
    databaseReadEpoch++;databaseReadPage=null;databaseSelected=null;databaseEntryEditing=null;databaseEntryAdding=false;databaseEntryDeleting=false;databaseRenameKey=false;databaseReplaceTitle=false;databaseReplaceDescription=false;databaseReplaceStyle=false;
    void databaseBrowser.invalidate(close).then(()=>{if(close)databaseSnapshotOpen=false;}).catch(e=>alert=failure(e));
  }
  async function closeDatabaseRead() {
    databaseReadEpoch++;databaseReadPage=null;databaseSelected=null;databaseEntryEditing=null;databaseEntryAdding=false;databaseEntryDeleting=false;databaseRenameKey=false;databaseReplaceTitle=false;databaseReplaceDescription=false;databaseReplaceStyle=false;
    await databaseBrowser.close();databaseSnapshotOpen=false;await refresh();
  }
  function selectDatabaseRow(row:DatabaseRow) {databaseSelected=row;databaseEntryEditing=null;databaseEntryAdding=false;databaseEntryDeleting=false;databaseRenameKey=false;}
  function editDatabaseEntry() {databaseEntryAdding=false;databaseEntryDeleting=false;if(databaseSelected){databaseEntryEditing={...databaseSelected};databaseEntryText=databaseSelected.text;databaseEntryKey=databaseSelected.key;databaseRenameKey=false;}}
  function deleteDatabaseEntry() {databaseEntryAdding=false;if(databaseSelected){databaseEntryEditing={...databaseSelected};databaseEntryDeleting=true;}}
  function addDatabaseEntry() {databaseEntryEditing={rowid:'0',key:'',text:''};databaseEntryKey='';databaseEntryText='';databaseRenameKey=false;databaseEntryDeleting=false;databaseEntryAdding=true;}
  async function saveDatabaseEntryCopy() {
    const page=databaseReadPage,row=databaseEntryEditing,source=databaseReadSource,epoch=databaseReadEpoch,text=databaseEntryText,key=databaseEntryAdding||databaseRenameKey?databaseEntryKey:undefined,deleting=databaseEntryDeleting,adding=databaseEntryAdding,selectedId=databaseSelected?.rowid;
    if(!page||!row)return;
    const makeRequest=(destination:string)=>adding?entryAddRequest(source,destination,page.source_sha256,key??'',text):deleting?entryDeleteRequest(source,destination,page.source_sha256,row):entryCopyRequest(source,destination,page.source_sha256,row,text,key);
    makeRequest(source+'-edited.db');
    const path=await save({title:d(adding?'saveAdditionCopy':deleting?'saveDeletionCopy':'saveEntryCopy'),defaultPath:source.replace(/\.(db|sqlite|sqlite3)$/i,'')+(adding?'-entry-added.db':deleting?'-entry-deleted.db':'-entry-edited.db'),filters:[{name:'SQLite',extensions:['db']}]});
    if(!path)return;
    if(epoch!==databaseReadEpoch||databaseSelected?.rowid!==selectedId)throw {code:'invalid_input',message:d('reloadMetadata')};
    const request=makeRequest(databaseOutputPath(path,'txt_to_db'));
    await closeDatabaseRead();await call({action:'submit',request});view='jobs';await refresh();
  }
  async function saveDatabaseMetadataCopy() {
    const page=databaseReadPage, source=databaseReadSource, epoch=databaseReadEpoch;
    if(!page?.dictionary_metadata)return;
    const edits={...(databaseReplaceTitle?{title:databaseEditTitle}:{}),...(databaseReplaceDescription?{description:databaseEditDescription}:{}),...(databaseReplaceStyle?{stylesheet:databaseEditStyle}:{})};
    // Validate before opening the save dialog or releasing the current snapshot.
    metadataCopyRequest(source,source+'-edited.db',page.source_sha256,page.dictionary_metadata,edits);
    const path=await save({title:d('saveMetadataCopy'),defaultPath:source.replace(/\.(db|sqlite|sqlite3)$/i,'')+'-edited.db',filters:[{name:'SQLite',extensions:['db']}]});
    if(!path)return;
    if(epoch!==databaseReadEpoch)throw {code:'invalid_input',message:d('reloadMetadata')};
    const destination=databaseOutputPath(path,'txt_to_db');
    const request=metadataCopyRequest(source,destination,page.source_sha256,page.dictionary_metadata,edits);
    await closeDatabaseRead();
    await call({action:'submit',request});view='jobs';await refresh();
  }
  async function pickDatabaseReadSource() {
    const path=await open({multiple:false,filters:[{name:'SQLite',extensions:['db','sqlite','sqlite3']}]});
    if(typeof path==='string'){resetDatabaseRead(true);databaseReadSource=path;}
  }
  async function loadDatabasePage(offset=0) {
    if(!databaseReadSource || databaseReadBusy)return;
    if(sessionId || mddId)throw {code:'resource_limit',message:d('closed')};
    if(databaseReadMode!=='all' && !databaseReadQuery)throw {code:'invalid_input',message:d('headword')};
    const epoch=++databaseReadEpoch;databaseReadBusy=true;
    databaseReadPage=null;databaseSelected=null;databaseEntryEditing=null;databaseEntryAdding=false;databaseEntryDeleting=false;databaseRenameKey=false;
    try {
      const page=await databaseBrowser.load(databaseReadSource,{query:databaseReadMode==='all'?null:databaseReadQuery,prefix:databaseReadMode==='prefix',wildcard:databaseReadMode==='pattern',definition:databaseReadMode==='definition',matching:databaseMatching,offset,limit:databaseReadLimit});
      if(epoch===databaseReadEpoch && page){databaseReadPage=page;databaseSelected=page.rows[0] || null;databaseSnapshotOpen=true;databaseEditTitle=page.dictionary_metadata?.Title || '';databaseEditDescription=page.dictionary_metadata?.Description || '';databaseEditStyle=page.dictionary_metadata?.StyleSheet || '';databaseReplaceTitle=false;databaseReplaceDescription=false;databaseReplaceStyle=false;}
    } finally {databaseReadBusy=false;const state=await call<DatabaseReaderSnapshot>({action:'database_poll'});databaseSnapshotOpen=state.state==='ready' || state.state==='busy';await refresh();}
  }

  let source = $state('');
  let destination = $state('');
  let resourceRoot = $state('');
  let mddInput = $state<'folder'|'manifest'>('folder');
  let title = $state('');
  let description = $state('');
  let stylesheet = $state('');
  let encoding = $state<Encoding>('utf8');
  let pack = $state('generic');
  let sourceFormat = $state<'txt'|'jsonl'>('txt');
  let txtProfile = $state<TxtProfile>('canonical_v1');
  let extraction = $state<ExtractOperation>('txt');
  let exportProfile = $state<'large'|'bounded'>('large');
  let extractParent = $state('');
  let extractFolder = $state('resources');
  $effect(()=>{if(view==='extract' && extraction==='mdd')destination=resourceDestination(extractParent,extractFolder) || '';});
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
  let resolved = $state<Resolved|null>(null);
  let resolvedIndex = $state(0);
  let showResolved = $state(false);
  let resolveJob = $state('');
  let redirectError = $state('');
  let resolveSubmitting = false;
  let selectionEpoch = 0;
  const redirectJobs = new Set<string>();
  const displayed = $derived(showResolved ? resolved?.results[resolvedIndex]?.row || selected : selected);
  const r = (key: Parameters<typeof redirectLabel>[1]) => redirectLabel(locale,key);
  function selectEntry(row:Row|null) {
    selectionEpoch++;resolved=null;showResolved=false;resolvedIndex=0;redirectError='';
    if(resolveJob && sessionId)void call({action:'session_cancel',session_id:sessionId,job_id:resolveJob}).catch(()=>{});
    resolveJob='';selected=row;
  }
  async function followRedirect() {
    const row=selected,sid=sessionId,epoch=selectionEpoch;
    if(!row || !sid || resolveJob || resolveSubmitting)return;
    resolveSubmitting=true;redirectError='';resolved=null;showResolved=false;
    try {
      const result=await call<{job_id:string}>({action:'resolve',session_id:sid,request:{query:row.key,ordinal:row.ordinal}});
      redirectJobs.add(result.job_id);
      if(epoch!==selectionEpoch || sid!==sessionId)await call({action:'session_cancel',session_id:sid,job_id:result.job_id});
      else resolveJob=result.job_id;
    } finally {resolveSubmitting=false;}
  }

  let mddSource = $state('');
  let mddIndex = $state('');
  let mddId = $state('');
  let mddState = $state('');
  let mddOpenJob = ''; 
  let info = $state<ReaderDetails | null>(null);
  let infoError = $state('');
  const z = (key: Parameters<typeof stylesheetLabel>[1]) => stylesheetLabel(locale,key);
  const numericStylesheet = $derived(info ? Object.entries(info.attributes).find(([key])=>key.toLowerCase()==='stylesheet')?.[1] || '' : '');
  async function exportStylesheet() {
    if(mddId)throw {code:'resource_limit',message:z('detach')};
    if(!info || !numericStylesheet || !sessionId)throw {code:'not_found',message:z('missing')};
    const path=await save({title:z('export'),defaultPath:dictionary.replace(/\.mdx$/i,'')+'_style.txt',filters:[{name:'UTF-8 text',extensions:['txt']}]});
    if(!path)return;
    await call({action:'export_stylesheet',session_id:sessionId,destination:exportFilePath(path,'txt')});
    view='jobs';await refresh();
  }

  let metadataSource = $state('');
  let metadataKind = $state<'mdx'|'mdd'>('mdx');
  let metadataTitle = $state('');
  let metadataDescription = $state('');
  let metadataStyle = $state('');
  let replaceTitle = $state(false);
  let replaceDescription = $state(false);
  let replaceStyle = $state(false);
  const e = (key: Parameters<typeof metadataLabel>[1]) => metadataLabel(locale,key);
  async function pickMetadata() {
    const path=await open({multiple:false,filters:[{name:'MDX / MDD',extensions:['mdx','mdd']}]});
    if(typeof path==='string'){metadataSource=path;metadataKind=/\.mdd$/i.test(path)?'mdd':'mdx';replaceTitle=false;replaceDescription=false;replaceStyle=false;metadataTitle='';metadataDescription='';metadataStyle='';}
  }
  function loadMetadata() {
    if(!info)return;
    metadataSource=dictionary;metadataKind='mdx';
    metadataTitle=info.attributes.Title || '';metadataDescription=info.attributes.Description || '';metadataStyle=info.attributes.StyleSheet || '';
    replaceTitle=false;replaceDescription=false;replaceStyle=false;
  }
  async function saveMetadata() {
    if(sessionId || mddId)throw {code:'resource_limit',message:e('close')};
    if(!metadataSource || !(replaceTitle || replaceDescription || (metadataKind==='mdx' && replaceStyle)))throw {code:'invalid_input',message:e('choose')};
    const edits={...(replaceTitle?{title:metadataTitle}:{}),...(replaceDescription?{description:metadataDescription}:{}),...(metadataKind==='mdx' && replaceStyle?{stylesheet:metadataStyle}: {})};
    const path=await save({title:e('save'),defaultPath:metadataSource.replace(/\.(mdx|mdd)$/i,'')+'-edited.'+metadataKind,filters:[{name:metadataKind.toUpperCase(),extensions:[metadataKind]}]});
    if(!path)return;
    await call({action:'submit',request:{kind:'metadata',request:{source:metadataSource,destination:dictionaryOutputPath(path,metadataKind),kind:metadataKind,edits}}});
    view='jobs';await refresh();
  }
  let previewMode = $state<'rendered' | 'split' | 'html'>('rendered');
  let previewAppearance = $state<Appearance>('original');
  let detailsOpen = $state(false);
  let preview = $state<Preview | null>(null);
  let previewBusy = $state(false);
  let previewError = $state('');
  let databasePreviewMode = $state<'rendered'|'split'|'html'>('rendered');
  let databasePreviewAppearance = $state<Appearance>('original');
  let databasePreview = $state<Preview|null>(null);
  let databasePreviewBusy = $state(false);
  let databasePreviewError = $state('');
  const resourceWaiters = new Map<string, {sid:string; resolve:(page:Page)=>void; reject:(e:unknown)=>void; cleanup:()=>void}>();
  const p = (key: Parameters<typeof previewLabel>[1]) => previewLabel(locale,key);
  $effect(() => {
    const active=view==='database', row=databaseSelected, metadata=databaseReadPage?.dictionary_metadata;
    const mode=databasePreviewMode, appearance=databasePreviewAppearance;
    const controller=new AbortController();
    databasePreview=null;databasePreviewError='';databasePreviewBusy=active && !!row && mode!=='html';
    if(active && row && mode!=='html') {
      const input=databasePreviewInput(row.text,metadata);
      // Database previews cannot borrow the Dictionary Tools MDD session.
      void renderPreview(input.text,input.sheet,appearance,null,controller.signal).then(result=>{
        if(!controller.signal.aborted){databasePreview=result;databasePreviewBusy=false;}
      }).catch(error=>{
        if(!controller.signal.aborted){databasePreviewError=failure(error).message;databasePreviewBusy=false;}
      });
    }
    return ()=>controller.abort();
  });
  $effect(() => {
    const row=displayed, metadata=info, appearance=previewAppearance, ready=mddState==='ready', sid=mddId, mode=previewMode;
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
  const x = (key: Parameters<typeof extractLabel>[1]) => extractLabel(locale,key);
  const m = (key: Parameters<typeof mddLabel>[1]) => mddLabel(locale,key);
  const folderBuild = () => view==='build' && pack==='mdd' && mddInput==='folder';
  const selectedSource = () => folderBuild()?resourceRoot:source;
  const b = (key: Parameters<typeof buildLabel>[1]) => buildLabel(locale,key);
  const u = (key: StudioLabel) => studioLabel(locale,key);
  const workspaceNav: [View,string][] = [['build','box'],['extract','extract'],['converters','convert']];
  const dataNav: [View,string][] = [['database','database'],['morphology','leaf']];
  const activeJob = $derived(poll?.jobs.find(job => !terminal(job.state)));
  const fileName = (path:string) => path.split(/[\\/]/).pop() || '';
  const viewLabel = (key:View) => key === 'plugins' ? y('heading') : key === 'database' || key === 'morphology' ? u(key) : t(key);
  function selectView(key:View) { view=key; alert=null; if(key === 'converters')converterSetup=false; }
  function heading() { return view === 'build' ? u('buildTitle') : view === 'extract' ? u('extractTitle') : view === 'converters' && converterSetup ? u('convertTitle') : viewLabel(view); }
  function lead() { return view === 'database' ? d('lead') : view === 'plugins' ? y('lead') : view === 'build' ? u('buildLead') : view === 'extract' ? u('extractLead') : view === 'converters' ? u('convertersLead') : view === 'tools' ? u('toolsLead') : view === 'jobs' ? u('jobsLead') : u('laterText'); }
  function sourceType() { return view === 'build' ? (pack==='mdd'?(mddInput==='folder'?m('folder'):u('resourceManifest')):sourceFormat==='txt'?b('txt'):u('jsonl')) : view === 'extract' ? x(extraction==='mdd'?'mdd':'mdx') : u('converterSource'); }
  function outputKind() { return view === 'build' ? u(pack === 'mdd' ? 'mdd' : 'mdx') : view === 'extract' ? u(extraction === 'mdd' ? 'folder' : extraction === 'jsonl' ? 'jsonlOutput' : 'txt') : u('txt'); }
  function outputFormat() { return view === 'build' ? pack === 'mdd' ? 'MDD' : 'MDX v2' : view === 'extract' ? extraction === 'mdd' ? u('folder') : extraction.toUpperCase() : 'TXT'; }
  function outputEncoding() { return view === 'build' ? pack === 'mdd' ? 'UTF-16' : encoding === 'utf16' ? 'UTF-16' : 'UTF-8' : view === 'extract' && extraction === 'mdd' ? '—' : 'UTF-8'; }
  function operationLabel(operation?:string) { return operation === 'db_add_entry' ? d('saveAdditionCopy') : operation === 'db_delete_entry' ? d('saveDeletionCopy') : operation === 'db_edit_entry' ? d('saveEntryCopy') : operation === 'db_edit_metadata' ? d('saveMetadataCopy') : operation === 'jsonl_to_db' ? d('fromJsonl') : operation === 'db_to_mdx' ? d('dbToMdx') : operation === 'mdx_to_db' ? d('mdxToDb') : operation === 'db_to_jsonl' ? d('toJsonl') : operation === 'database_page' ? d('browse') : operation === 'txt_to_db' ? d('toDb') : operation === 'db_to_txt' ? d('toTxt') : operation === 'export_stylesheet' ? z('export') : operation === 'python_converter' ? y('heading') : operation === 'rebuild_metadata' ? e('heading') : operation === 'extract_mdd' ? x('extract') : operation?.startsWith('export_') ? x('export') : operation === 'pack_txt_mdx' ? u('buildTitle') : operation === 'build_index' ? t('createIndex') : operation === 'convert_to_txt' ? u('convertTitle') : u('buildTitle'); }


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
    try { await work(); } catch (e) { const issue=failure(e);alert=issue.code==='retention_full'?{...issue,message:m('retention')}:issue;if(issue.code==='retention_full')view='jobs'; }
    finally { pending -= 1; }
  }
  async function pickInput(target: 'source' | 'dictionary' | 'artifact' | 'root' | 'mddSource' | 'mddIndex') {
    const result = await open({ directory: target === 'root', multiple: false, ...(target==='source' && view==='extract'?{filters:[{name:'MDX / MDD',extensions:['mdx','mdd']}]}:{}) });
    if (typeof result !== 'string') return;
    if (target === 'source') {source = result;if(view==='extract'){destination='';if(/\.mdd$/i.test(result)){extraction='mdd';extractParent=sourceParent(result);extractFolder=resourceFolderName(result);}else if(/\.mdx$/i.test(result) && extraction==='mdd'){extraction='txt';}}if(view==='build' && pack!=='mdd') {if(/\.jsonl$/i.test(result))sourceFormat='jsonl';else if(/\.txt$/i.test(result))sourceFormat='txt';}}
    else if (target === 'dictionary') dictionary = result;
    else if (target === 'artifact') artifact = result;
    else if(target === 'mddSource') mddSource=result;
    else if(target === 'mddIndex') mddIndex=result;
    else resourceRoot = result;
  }
  function changeExtraction(value:ExtractOperation) {extraction=value;destination='';if(value==='mdd' && source){extractParent=sourceParent(source);extractFolder=resourceFolderName(source);}}
  async function chooseExtractParent() {const path=await open({directory:true,multiple:false,title:x('chooseParent')});if(typeof path==='string')extractParent=path;}
  async function pickOutput(index = false) {
    if(!index && view==='extract' && extraction==='mdd'){await chooseExtractParent();return;}
    const entryExport=!index && view==='extract' && extraction!=='mdd';
    const format=pack==='mdd'?'mdd':'mdx';
    const archive=view==='build' && !index;
    const result = await save({ title: index ? t('index') : t('destination'),
      ...(archive ? {filters:[{name:format.toUpperCase(),extensions:[format]}],defaultPath:dictionaryOutputPath(destination || 'dictionary',format)} : entryExport ? {filters:[{name:extraction.toUpperCase(),extensions:[extraction]}],defaultPath:exportFilePath(destination || fileName(source) || 'dictionary',extraction as 'txt'|'jsonl')} : {}) });
    if (result) { if (index) artifact = result; else destination = archive ? dictionaryOutputPath(result,format) : entryExport ? exportFilePath(result,extraction as 'txt'|'jsonl') : result; }
  }
  async function submit() {
    if(view==='extract' && extraction==='mdd' && !resourceDestination(extractParent,extractFolder))throw {code:'invalid_input',message:extractParent?x('nameHint'):x('chooseParent')};
    if (!selectedSource() || !destination) throw { code: 'invalid_input', message: t('required') };
    if(view==='build')destination=dictionaryOutputPath(destination,pack==='mdd'?'mdd':'mdx');
    if(view==='extract' && extraction!=='mdd')destination=exportFilePath(destination,extraction);
    let request: NativeRequest;
    const metadata = { title, description, stylesheet: view === 'build' && pack === 'mdd' ? '' : stylesheet, extra: {} };
    if (view === 'build') {
      if (pack === 'mdd') {
        if (!resourceRoot) throw { code: 'invalid_input', message: t('resourceRoot') };
        if(mddInput==='folder') {
          if(sessionId || mddId)throw {code:'not_ready',message:m('close')};
          request={kind:'folder_packing',request:{resource_root:resourceRoot,destination,metadata}};
        } else request = { kind:'dictionary', request:{ operation:'pack_mdd', source, destination, resource_root:resourceRoot, metadata } };
      } else if (sourceFormat === 'txt') {
        if(sessionId || mddId)throw {code:'not_ready',message:b('closeHint')};
        request={kind:'txt_packing',request:{source,destination,encoding,metadata,profile:txtProfile,packing:pack==='block'?'block':'bounded'}};
      } else if (pack === 'block') request = { kind:'cc_packing', request:{ source, destination, encoding, metadata } };
      else request = { kind:'dictionary', request:{ operation:'pack_mdx', source, destination, encoding, metadata } };
    } else if (view === 'extract') {
      if(extraction!=='mdd' && exportProfile==='large') {
        if(sessionId || mddId)throw {code:'not_ready',message:x('close')};
        request={kind:'large_export',request:{source,destination,format:extraction}};
      } else request = extraction === 'mdd' ? { kind:'extraction', request:{ source, destination } }
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
    await closeDatabaseRead();
    if (!dictionary || !artifact) throw { code:'invalid_input', message:t('required') };
    const opened = await call<{session_id:string; job_id:string}>({ action:'open_reader', request:{ source:dictionary, artifact, kind:'mdx', policy } });
    sessionId = opened.session_id; sessionState = 'opening'; pageResult = null; selectEntry(null); info=null; infoError='';
  }
  async function buildMddIndex() {
    if(sessionId || mddId) throw {code:'not_ready',message:p('closeFirst')};
    if(!mddSource || !mddIndex) throw {code:'invalid_input',message:t('required')};
    await call({action:'submit',request:{kind:'index',request:{source:mddSource,destination:mddIndex,kind:'mdd',policy:'raw_exact'}}});
    view='jobs';await refresh();
  }
  async function attachMdd() {
    await closeDatabaseRead();
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
    selectEntry(null);
    await call({ action:'page', session_id:sessionId, request:{ query, offset, limit:32 } });
    queryPending = true;
  }
  let refreshing = false;
  async function refresh() {
    if (!connected || refreshing || shuttingDown || resolveSubmitting) return;
    refreshing = true;
    try {
      const next = await call<Poll>({ action:'poll' });
      if(resolveSubmitting)return;
      poll = next;
      for (const item of next.sessions) {
        const sid = item.session.session_id;
        if (sid === sessionId) sessionState = item.session.state;
        if (sid === mddId) mddState = item.session.state;
        if(sid!==sessionId && sid!==mddId)continue;
        for (const job of item.jobs) {
          if (!terminal(job.state)) continue;
          if(sid===mddId && job.job_id!==mddOpenJob && !resourceWaiters.has(job.job_id))continue;
          if(redirectJobs.has(job.job_id)) {
            if(job.result_available) {
              const reply=await call<SessionReply|null>({action:'session_take',session_id:sid,job_id:job.job_id});
              if(job.job_id===resolveJob && reply?.operation==='resolved') {
                const result=reply.value as Resolved;
                if(result.source_ordinal===selected?.ordinal && result.source_key===selected?.key){resolved=result;resolvedIndex=0;showResolved=true;}
              }
            }
            if(job.job_id===resolveJob){redirectError=job.error?r('error')+' '+(job.error.detail || job.error.code)+': '+job.error.message:job.state==='cancelled'?t('cancelled'):'';resolveJob='';}
            await call({action:'session_forget',session_id:sid,job_id:job.job_id});redirectJobs.delete(job.job_id);continue;
          }
          const waiter=resourceWaiters.get(job.job_id);
          if(sid===sessionId && !job.result_available)queryPending=false;
          if (job.error) {if(waiter)waiter.reject(job.error);else {alert = job.error; queryPending = false;} }
          if (job.result_available) {
            const reply = await call<SessionReply | null>({ action:'session_take', session_id:sid, job_id:job.job_id });
            if(reply?.operation==='page' && waiter) waiter.resolve(reply.value as Page);
            else if (reply?.operation === 'page' && sid === sessionId) {
              pageResult = reply.value as Page; selectEntry(pageResult.rows[0] || null); queryPending = false;
            } else if (reply?.operation === 'opened') {status = t('opened');if(sid===sessionId)void readDetails(sid);}
          }
          if(waiter){if(!job.result_available&&!job.error)waiter.reject(new Error('Resource job cancelled'));waiter.cleanup();resourceWaiters.delete(job.job_id);}
          await call({ action:'session_forget', session_id:sid, job_id:job.job_id });
        }
        if (['closed','failed'].includes(item.session.state)) {
          try {
            await call({ action:'release_reader', session_id:sid });
            if (sid === sessionId) { selectEntry(null);redirectJobs.clear();sessionId=''; sessionState=''; queryPending=false; pageResult=null; info=null;infoError=''; }
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
  async function dismissFinished() {
    const jobs=poll?.jobs.filter(job=>terminal(job.state)) || [];
    for(const job of jobs)await forget(job.job_id);
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
        <button class="nav" class:active={view === key} aria-current={view === key ? 'page' : undefined} onclick={() => selectView(key)} title={viewLabel(key)}><Icon name={icon}/><span class="navtext">{viewLabel(key)}</span>{#if key === 'morphology'}<span class="soon">{u('later')}</span>{/if}</button>
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
      <header class="top"><div><div class="eyebrow">{u('workspace')}</div><h1>{heading()}</h1><p>{lead()}</p></div><span class="tag">{view === 'database' ? 'TXT / SQLite' : view === 'tools' ? 'MDX + MDD' : 'MDX / MDD'}</span></header>
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
                <div class="sourcecard"><div class="fileicon"><Icon name={folderBuild()?'folder':'file'}/></div><div class="filetext"><b><bdi>{fileName(selectedSource()) || (folderBuild()?m('choose'):u('chooseSource'))}</bdi></b><small>{sourceType()}</small></div><button class="smallbutton" type="button" onclick={() => action(() => pickInput(folderBuild()?'root':'source'))}>{t('choose')}</button></div>
                <div class="note sourcehint">{#if selectedSource()}<Icon name="check"/>{/if}<span>{folderBuild()?m('hint'):view==='extract'?x('sourceHint'):selectedSource()?u('sourceHint'):u('noSource')}</span></div>
                <div class="formsection"><span>{view === 'converters' ? u('configureConverter') : view==='extract'?x('settings'):u('dictionary')}</span><small>{u('stepTwo')}</small></div>
                <div class="fields">
                  {#if view === 'build'}
                    <div class="field"><label for="dictionary-name">{u('name')}</label><input id="dictionary-name" bind:value={title} autocomplete="off" /></div>
                    <div class="field"><label for="dictionary-format">{u('format')}</label><select id="dictionary-format" value={pack === 'mdd' ? 'mdd' : 'mdx'} onchange={e => pack=e.currentTarget.value === 'mdd' ? 'mdd' : 'generic'}><option value="mdx">MDX</option><option value="mdd">MDD</option></select></div>
                    {#if pack !== 'mdd'}<div class="field"><label for="dictionary-encoding">{b('outputEncoding')}</label><select id="dictionary-encoding" bind:value={encoding}><option value="utf8">UTF-8</option><option value="utf16">UTF-16</option></select></div>{/if}
                  {:else if view === 'extract'}
                    <div class="field"><label for="extract-operation">{t('operation')}</label><select id="extract-operation" value={extraction} onchange={e=>changeExtraction(e.currentTarget.value as ExtractOperation)}><option value="txt">{t('exportTxt')}</option><option value="jsonl">{t('exportJsonl')}</option><option value="mdd">{t('extractMdd')}</option></select></div>
                  {:else}
                    <div class="field"><label for="converter-name">{t('converter')}</label><select id="converter-name" bind:value={converter}>{#each converterOptions as [value,name]}<option {value}>{name}</option>{/each}</select></div>
                    {#if converter !== 'cc_cedict'}<div class="field"><label for="converter-worksheet">{t('worksheet')}</label><input id="converter-worksheet" bind:value={worksheet} maxlength="1024" /></div>{/if}
                    <div class="field"><span class="field-label">{u('format')}</span><span class="field-value">TXT · UTF-8</span></div>
                  {/if}
                  {#if view === 'build' && pack === 'mdd' && mddInput==='manifest'}<div class="field path-field"><label for="resource-root">{t('resourceRoot')}</label><input id="resource-root" bind:value={resourceRoot} required dir="auto"/><button type="button" class="smallbutton iconbutton" aria-label={t('resourceRoot')} onclick={() => action(() => pickInput('root'))}><Icon name="folder"/></button></div>{/if}
                  {#if view==='extract' && extraction==='mdd'}
                    <div class="field path-field"><label for="extract-parent">{x('parent')}</label><input id="extract-parent" value={extractParent} readonly dir="auto"/><button class="smallbutton" type="button" onclick={()=>action(chooseExtractParent)}>{t('choose')}</button></div>
                    <div class="field"><label for="extract-folder">{x('folderName')}</label><input id="extract-folder" bind:value={extractFolder} required maxlength="255" dir="auto"/></div>
                  {/if}
                  <div class="field path-field"><label for="output-path">{u('saveTo')}</label><input id="output-path" bind:value={destination} readonly={view==='extract' && extraction==='mdd'} required dir="auto" placeholder={u('chooseDestination')}/><button type="button" class="smallbutton iconbutton" aria-label={t('destination')} onclick={() => action(() => pickOutput())}>…</button></div>
                </div>
                {#if view==='extract'}<p class="note">{x(extraction==='mdd'?'folderHint':extraction==='txt'?'txtHint':'jsonlHint')}</p>{#if extraction!=='mdd'}<p class="note">{x('metadata')}</p>{/if}{/if}
                <details class="advanced">
                  <summary>{u('more')}{#if view === 'build' && pack !== 'mdd'}<span class="profile-caption"> · {u(pack === 'block' ? 'block' : 'bounded')}</span>{/if}</summary>
                  <div class="advanced-content">
                    <label for="source-path">{folderBuild()?m('folder'):u('inputDetails')}</label>{#if folderBuild()}<input id="source-path" bind:value={resourceRoot} dir="auto" />{:else}<input id="source-path" bind:value={source} dir="auto" />{/if}
                    {#if view === 'build'}
                      {#if pack==='mdd'}<label for="mdd-input">{m('mode')}</label><select id="mdd-input" bind:value={mddInput}><option value="folder">{m('folderMode')}</option><option value="manifest">{m('manifestMode')}</option></select><p class="note">{mddInput==='folder'?m('limits'):m('manifest')}</p>{/if}
                      {#if pack !== 'mdd'}
                        <label for="source-format">{b('format')}</label><select id="source-format" bind:value={sourceFormat}><option value="txt">{b('txtOption')}</option><option value="jsonl">{b('jsonlOption')}</option></select>
                        {#if sourceFormat==='txt'}<label for="txt-profile">{b('profile')}</label><select id="txt-profile" bind:value={txtProfile}><option value="canonical_v1">{b('canonical')}</option><option value="legacy_body_span_v1">{b('legacy')}</option></select><p class="note">{b('profileHint')}</p>{/if}
                      {/if}
                      {#if pack !== 'mdd'}<label for="pack-profile">{u('profile')}</label><select id="pack-profile" bind:value={pack}><option value="generic">{t('buildGeneric')}</option><option value="block">{t('buildBlock')}</option></select>{/if}
                      <label for="dictionary-description">{t('description')}</label><textarea id="dictionary-description" bind:value={description} rows="3"></textarea>
                      {#if pack !== 'mdd'}<label for="dictionary-stylesheet">{t('stylesheet')}</label><textarea id="dictionary-stylesheet" bind:value={stylesheet} rows="4" dir="ltr"></textarea>{/if}
                      {#if folderBuild()}<p class="note">{m('close')}</p>{:else if pack!=='mdd' && sourceFormat==='txt'}<p class="note">{b('hint')}</p><pre class="manifest-help">{b('sample')}</pre><p class="note">{b('closeHint')}</p>{:else}<p class="note">{b('jsonlHint')}</p><pre class="manifest-help">{t('manifestHint')}</pre>{/if}
                    {:else if view==='extract'}{#if extraction!=='mdd'}<label for="export-profile">{x('profile')}</label><select id="export-profile" bind:value={exportProfile}><option value="large">{x('large')}</option><option value="bounded">{x('bounded')}</option></select>{#if exportProfile==='large'}<p class="note">{x('close')}</p>{/if}{/if}<p class="note">{x(extraction==='mdd'?'mddHint':extraction==='txt'?'txtHint':'jsonlHint')}</p>{/if}
                  </div>
                </details>
                <p class="note publication-note">{t('noOverwrite')}</p>{#if view==='build' && pack!=='mdd' && sourceFormat==='txt' && (sessionId || mddId)}<p class="note">{b('closeHint')}</p>{/if}
                {#if view==='extract' && extraction!=='mdd' && exportProfile==='large' && (sessionId || mddId)}<p class="note">{x('close')}</p>{/if}
                {#if folderBuild() && (sessionId || mddId)}<p class="note">{m('close')}</p>{/if}
                <div class="actions"><span class="note">{u('local')}</span><button class="primary" type="submit">{view==='extract'?x(extraction==='mdd'?'extract':'export'):u(view==='build'?'buildTitle':'convertTitle')}</button></div>
              </fieldset>
            </form>
            <aside class="summary">
              <h2>{u('output')}</h2><div class="outputtile"><Icon name={view === 'extract' ? 'extract' : 'book'}/><b><bdi>{fileName(destination) || u('noOutput')}</bdi></b><small>{outputKind()}</small></div>
              <div class="stat"><span>{u('format')}</span><bdi>{outputFormat()}</bdi></div><div class="stat"><span>{t('encoding')}</span><bdi>{outputEncoding()}</bdi></div><div class="stat"><span>{u('location')}</span><span>{u('localFolder')}</span></div>
              {#if view==='extract' && extraction!=='mdd'}<div class="stat"><span>{x('profile')}</span><span>{x(exportProfile)}</span></div>{/if}
              {#if view === 'build' && pack !== 'mdd'}<div class="stat"><span>{u('profile')}</span><span>{u(pack === 'block' ? 'block' : 'bounded')}</span></div>{/if}
              <div class="checklist">{#if view === 'build'}<p><Icon name="check"/><span>{u('duplicate')}</span></p>{/if}<p><Icon name="check"/><span>{u('noClobber')}</span></p><p><Icon name="check"/><span>{u('background')}</span></p></div><p class="note" style="margin-top:25px">{u('outputHint')}</p>
            </aside>
          </div>
        {:else if view === 'converters'}
          <section class="page"><h2>{u('selectConverter')}</h2><p>{u('convertersLead')}</p><div class="convertergrid">{#each converterOptions as [value,name]}<button class="converter" onclick={() => {converter=value;converterSetup=true;}}><Icon name="convert"/><strong>{name}</strong><small>{u('configureConverter')} → TXT</small></button>{/each}<button class="converter" onclick={()=>selectView('plugins')}><Icon name="convert"/><strong>{y('heading')}</strong><small>{y('tile')}</small></button></div></section>
        {:else if view === 'plugins'}
          <section class="page plugin-page">
            <button class="backbutton" onclick={()=>selectView('converters')}><Icon name="back"/>{u('selectConverter')}</button>
            <form onsubmit={event=>{event.preventDefault();void action(runPlugin);}}>
              <fieldset disabled={!connected || pending>0 || shuttingDown}>
                <div class="fields">
                  <div class="field path-field"><label for="plugin-python">{y('python')}</label><input id="plugin-python" bind:value={pluginPython} dir="ltr"/><button type="button" class="smallbutton" onclick={()=>action(()=>pickPluginFile('python'))}>{t('choose')}</button></div>
                  <div class="field path-field"><label for="plugin-file">{y('plugin')}</label><input id="plugin-file" bind:value={pluginFile} oninput={()=>pluginTrusted=false} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(()=>pickPluginFile('plugin'))}>{t('choose')}</button></div>
                  <div class="field"><label for="plugin-class">{y('class')}</label><input id="plugin-class" bind:value={pluginClass} maxlength="128" dir="ltr"/></div>
                  <div class="field path-field"><label for="plugin-source">{u('source')}</label><input id="plugin-source" bind:value={pluginSource} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(()=>pickPluginFile('source'))}>{t('choose')}</button></div>
                  <div class="field path-field"><label for="plugin-parent">{x('parent')}</label><input id="plugin-parent" bind:value={pluginParent} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(()=>pickPluginFile('parent'))}>{t('choose')}</button></div>
                  <div class="field"><label for="plugin-folder">{x('folderName')}</label><input id="plugin-folder" bind:value={pluginFolder} dir="auto"/></div>
                </div>
                <p class="note">{y('bundle')}</p><p class="note">{y('limits')}</p>
                <label class="plugin-trust"><input type="checkbox" bind:checked={pluginTrusted}/>{y('trust')}</label>
                <div class="job-buttons"><button class="primary" type="submit" disabled={!pluginTrusted || !pluginPython || !pluginFile || !pluginSource || !resourceDestination(pluginParent,pluginFolder) || !!sessionId || !!mddId}>{y('run')}</button></div>
                {#if sessionId || mddId}<p class="note">{y('close')}</p>{/if}
              </fieldset>
            </form>
          </section>
        {:else if view === 'database'}
          <section class="page database-page">
            <form onsubmit={event=>{event.preventDefault();void action(runDatabase);}}>
              <fieldset disabled={!connected || pending>0 || shuttingDown}>
                <div class="fields">
                  <div class="field"><label for="database-operation">{t('operation')}</label><select id="database-operation" bind:value={databaseOperation} onchange={changeDatabaseOperation}><option value="txt_to_db">{d('toDb')}</option><option value="db_to_txt">{d('toTxt')}</option><option value="jsonl_to_db">{d('fromJsonl')}</option><option value="db_to_jsonl">{d('toJsonl')}</option><option value="mdx_to_db">{d('mdxToDb')}</option><option value="db_to_mdx">{d('dbToMdx')}</option></select></div>
                  <div class="field path-field"><label for="database-source">{d('source')}</label><input id="database-source" bind:value={databaseSource} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(pickDatabaseSource)}>{t('choose')}</button></div>
                  <div class="field path-field"><label for="database-destination">{d('destination')}</label><input id="database-destination" bind:value={databaseDestination} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(pickDatabaseDestination)}>{t('choose')}</button></div>
                  {#if databaseOperation === 'txt_to_db'}<div class="field"><label for="database-profile">{d('profile')}</label><select id="database-profile" bind:value={databaseProfile}><option value="canonical_v1">{d('canonical')}</option><option value="legacy_body_span_v1">{d('legacy')}</option></select></div>{/if}
                </div>
                {#if databaseOperation==='db_to_mdx'}<p class="note">{d('rebuildHint')}</p>{/if}
                {#if databaseOperation==='mdx_to_db'}<p class="note">{d('mdxHint')}</p>{/if}
                {#if databaseOperation==='jsonl_to_db'}<p class="note">{d('jsonlImportHint')}</p>{/if}
                {#if databaseOperation==='db_to_jsonl'}<p class="note">{d('jsonlHint')}</p>{/if}
                <p class="note">{d('preserve')}</p><p class="note">{(databaseOperation==='db_to_jsonl'||databaseOperation==='jsonl_to_db')?d('jsonlFormat'):d('format')}</p><p class="note">{d('limits')}</p>
                {#if sessionId || mddId}<p class="note">{d('closed')}</p>{/if}
                <div class="job-buttons"><button class="primary" type="submit" disabled={!databaseSource || !databaseDestination || !!sessionId || !!mddId}>{d('run')}</button></div>
              </fieldset>
            </form>
            <h2 style="margin-top:32px">{d('browse')}</h2>
            <form onsubmit={event=>{event.preventDefault();void action(()=>loadDatabasePage());}}>
              <fieldset disabled={!connected || pending>0 || shuttingDown || databaseReadBusy}>
                <div class="fields">
                  <div class="field path-field"><label for="database-read-source">{d('source')}</label><input id="database-read-source" bind:value={databaseReadSource} oninput={()=>resetDatabaseRead(true)} dir="auto"/><button type="button" class="smallbutton" onclick={()=>action(pickDatabaseReadSource)}>{t('choose')}</button></div>
                  <div class="field"><label for="database-read-mode">{t('operation')}</label><select id="database-read-mode" bind:value={databaseReadMode} onchange={()=>resetDatabaseRead()}><option value="all">{d('all')}</option><option value="exact">{d('exact')}</option><option value="prefix">{d('prefix')}</option><option value="pattern">{d('pattern')}</option><option value="definition">{d('definitionSearch')}</option></select></div>
                  {#if databaseReadMode !== 'all'}<div class="field"><label for="database-read-query">{databaseReadMode==='definition'?d('searchText'):d('headword')}</label><input id="database-read-query" bind:value={databaseReadQuery} oninput={()=>resetDatabaseRead()} dir="auto"/></div>{/if}
                  {#if databaseReadMode!=='all'}<div class="field"><label for="database-matching">{d('matching')}</label><select id="database-matching" bind:value={databaseMatching} onchange={()=>resetDatabaseRead()}><option value="literal">{d('caseLiteral')}</option><option value="unicode16_lower">{d('caseLower')}</option></select></div>{/if}
                  <div class="field"><label for="database-read-limit">{d('pageSize')}</label><select id="database-read-limit" bind:value={databaseReadLimit} onchange={()=>resetDatabaseRead()}><option value={2}>2</option><option value={16}>16</option><option value={32}>32</option></select></div>
                </div>
                <p class="note">{d('readHint')}</p>{#if databaseReadMode==='definition'}<p class="note">{d('definitionHint')}</p>{/if}{#if databaseReadMode==='pattern'}<p class="note">{d('patternHint')}</p>{/if}{#if databaseReadMode!=='all' && databaseMatching==='unicode16_lower'}<p class="note">{d('caseHint')}</p>{/if}
                <div class="job-buttons"><button class="primary" type="submit" disabled={!databaseReadSource || !!sessionId || !!mddId || databaseReadMode!=='all' && !databaseReadQuery}>{d('load')}</button></div>
              </fieldset>
            </form>
            {#if databaseReadBusy}<p role="status" class="note">{t('running')}</p><button class="smallbutton" disabled={!connected || shuttingDown} onclick={()=>action(async()=>{await databaseBrowser.cancel();})}>{t('cancel')}</button>{/if}
            {#if databaseSnapshotOpen}<div class="job-buttons"><span class="note">{d('snapshotOpen')}</span><button class="smallbutton" disabled={pending>0 || databaseReadBusy} onclick={()=>action(closeDatabaseRead)}>{d('closeSnapshot')}</button></div>{/if}
            {#if databaseReadPage}
              {#if databaseReadPage.dictionary_metadata}<details><summary>{d('dictionaryMetadata')}</summary><pre>{JSON.stringify(databaseReadPage.dictionary_metadata,null,2)}</pre></details>
                <details class="metadata-editor database-metadata-editor"><summary>{d('saveMetadataCopy')}</summary>
                  <fieldset disabled={!connected || pending>0 || shuttingDown || databaseReadBusy || !!sessionId || !!mddId}>
                    <p class="note">{d('metadataCopyHint')}</p>
                    <div class="fields">
                      <div class="field"><label for="database-edit-title">{e('title')}</label><input id="database-edit-title" bind:value={databaseEditTitle} disabled={!databaseReplaceTitle} dir="auto"/><label><input type="checkbox" bind:checked={databaseReplaceTitle}/>{e('replace')}</label></div>
                      <div class="field"><label for="database-edit-description">{e('description')}</label><textarea id="database-edit-description" rows="3" bind:value={databaseEditDescription} disabled={!databaseReplaceDescription} dir="auto"></textarea><label><input type="checkbox" bind:checked={databaseReplaceDescription}/>{e('replace')}</label></div>
                    </div>
                    <div class="field"><label for="database-edit-style">{e('stylesheet')}</label><textarea id="database-edit-style" rows="8" bind:value={databaseEditStyle} disabled={!databaseReplaceStyle} dir="ltr"></textarea><label><input type="checkbox" bind:checked={databaseReplaceStyle}/>{e('replace')}</label></div>
                    <p class="note">{d('stylesheetCopyHint')}</p>
                    <button class="smallbutton" disabled={!databaseReplaceTitle && !databaseReplaceDescription && !databaseReplaceStyle} onclick={()=>action(saveDatabaseMetadataCopy)}>{d('saveMetadataCopy')}</button>
                  </fieldset>
                </details>{/if}
              <p class="note" role="status">{d('records')}: {databaseReadPage.total} · {d('offset')}: {databaseReadPage.offset}</p>
              <div class="job-buttons"><button class="smallbutton" disabled={pending>0 || databaseReadBusy || databaseReadPage.offset===0} onclick={()=>action(()=>loadDatabasePage(Math.max(0,(databaseReadPage?.offset || 0)-databaseReadLimit)))}>{d('previous')}</button><button class="smallbutton" disabled={pending>0 || databaseReadBusy || databaseReadPage.next_offset===null} onclick={()=>action(()=>loadDatabasePage(databaseReadPage?.next_offset || 0))}>{t('next')}</button></div>
              <div class="database-results">
                <div class="database-rows" aria-label={d('records')}>{#each databaseReadPage.rows as row (row.rowid)}<button class="database-row" class:active={databaseSelected?.rowid===row.rowid} onclick={()=>selectDatabaseRow(row)}><bdi>{row.key}</bdi><small>#{row.rowid}</small></button>{:else}<p>{t('noEntries')}</p>{/each}</div>
                <div class="database-definition">
                  <div class="database-definition-head">{#if databaseSelected}<h3 dir="auto">{databaseSelected.key}</h3><p class="note">{d('row')}: {databaseSelected.rowid}</p>{:else}<p class="note">{t('selectEntry')}</p>{/if}</div>
                  <div class="database-preview-note"><button class="smallbutton" disabled={pending>0 || databaseReadBusy || shuttingDown} onclick={addDatabaseEntry}>{d('addEntry')}</button> {#if databaseSelected}<button class="smallbutton" disabled={pending>0 || databaseReadBusy || shuttingDown} onclick={editDatabaseEntry}>{d('editDefinition')}</button> <button class="smallbutton" disabled={pending>0 || databaseReadBusy || shuttingDown} onclick={deleteDatabaseEntry}>{d('deleteEntry')}</button>{/if}</div>
                  {#if databaseEntryEditing && (databaseEntryAdding || databaseSelected?.rowid===databaseEntryEditing.rowid)}
                    <div class="metadata-editor database-preview-note"><fieldset disabled={!connected || pending>0 || shuttingDown || databaseReadBusy || !!sessionId || !!mddId}>
                      {#if databaseEntryDeleting}<p>{d('deleteEntry')}: <bdi>{databaseEntryEditing.key}</bdi> · #{databaseEntryEditing.rowid}</p><p class="note">{d('deleteEntryHint')}</p>{:else}
                      <p class="note">{d(databaseEntryAdding?'addEntryHint':'entryCopyHint')}</p>
                      <div class="field"><label for="database-entry-key">{d('headword')}</label><input id="database-entry-key" bind:value={databaseEntryKey} disabled={!databaseEntryAdding && !databaseRenameKey} dir="auto"/>{#if !databaseEntryAdding}<label><input type="checkbox" bind:checked={databaseRenameKey}/>{d('renameHeadword')}</label>{/if}</div>
                      {#if !databaseEntryAdding}<p class="note">{d('renameHint')}</p>{/if}
                      <label for="database-entry-text">{d('sourceView')} · {#if databaseEntryAdding}{d('addEntry')}{:else}#{databaseEntryEditing.rowid}{/if}</label>
                      <textarea id="database-entry-text" class="database-entry-editor" rows="10" bind:value={databaseEntryText} dir="auto"></textarea>
                      {/if}
                      <div class="job-buttons"><button class="smallbutton" onclick={()=>action(saveDatabaseEntryCopy)}>{d(databaseEntryAdding?'saveAdditionCopy':databaseEntryDeleting?'saveDeletionCopy':'saveEntryCopy')}</button><button class="smallbutton" onclick={()=>databaseEntryEditing=null}>{t('cancel')}</button></div>
                    </fieldset></div>
                  {/if}
                  <div class="readingbar"><div class="segment" aria-label={d('definitionView')}>
                    {#each ['rendered','split','html'] as mode}<button class:active={databasePreviewMode===mode} aria-pressed={databasePreviewMode===mode} onclick={()=>databasePreviewMode=mode as typeof databasePreviewMode}>{p(mode as 'rendered'|'split'|'html')}</button>{/each}
                  </div><div class="preview-controls"><select bind:value={databasePreviewAppearance} aria-label={p('appearance')} disabled={databasePreviewMode==='html'}><option value="original">{p('original')}</option><option value="paper">{p('paper')}</option><option value="dark">{p('dark')}</option></select></div></div>
                  <div class="entry-views database-entry-views" class:split={databasePreviewMode==='split'}>
                    {#if databasePreviewMode!=='html'}<div class="preview-pane">
                      {#if databasePreview}<iframe class="dictionary-preview" title={d('definitionView')} sandbox="" referrerpolicy="no-referrer" srcdoc={databasePreview.document}></iframe>
                      {:else}<div class="preview-placeholder">{!databaseSelected?p('empty'):databasePreviewBusy?p('loading'):p('unavailable')}{#if databasePreviewError}<p role="alert" class="note">{databasePreviewError}</p>{/if}</div>{/if}
                    </div>{/if}
                    {#if databasePreviewMode!=='rendered'}<pre dir="auto" class="definition-source">{databaseSelected?.text ?? t('selectEntry')}</pre>{/if}
                  </div>
                  <div class="readingfoot">{p('staticHint')}</div>
                  <p class="note database-preview-note">{d('previewHint')}</p>
                  {#if databasePreview?.warnings.length}<details class="database-preview-note"><summary>{p('warnings')}</summary>{#each databasePreview.warnings as warning}<p class="note">{warning}</p>{/each}</details>{/if}
                </div>
              </div>
            {/if}
            <p class="note">{d('deferred')}</p>
          </section>
        {:else if view === 'morphology'}
          <section class="page"><span class="tag">{u('later')}</span><h2 style="margin-top:18px">{viewLabel(view)}</h2><p>{u('laterText')}</p><p>{t('deferred')}</p></section>
        {:else if view === 'jobs'}
          <section class="page jobs-page">
            {#if poll?.jobs.some(job=>terminal(job.state))}<div class="job-buttons"><button class="smallbutton" disabled={pending>0} onclick={()=>action(dismissFinished)}>{m('dismiss')}</button></div>{/if}
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
            <details class="reader-setup metadata-editor">
              <summary>{e('heading')}</summary>
              <fieldset disabled={!connected || pending > 0 || shuttingDown}>
                <div class="fields">
                  <div class="field path-field"><label for="metadata-source">{e('source')}</label><input id="metadata-source" bind:value={metadataSource} dir="auto"/><button class="smallbutton" onclick={()=>action(pickMetadata)}>{t('choose')}</button></div>
                  <div class="field"><label for="metadata-kind">{e('kind')}</label><select id="metadata-kind" bind:value={metadataKind}><option value="mdx">MDX v2</option><option value="mdd">MDD v2</option></select></div>
                  <div class="field"><label for="metadata-title">{e('title')}</label><input id="metadata-title" bind:value={metadataTitle} disabled={!replaceTitle} dir="auto"/><label><input type="checkbox" bind:checked={replaceTitle}/>{e('replace')}</label></div>
                  <div class="field"><label for="metadata-description">{e('description')}</label><textarea id="metadata-description" rows="3" bind:value={metadataDescription} disabled={!replaceDescription} dir="auto"></textarea><label><input type="checkbox" bind:checked={replaceDescription}/>{e('replace')}</label></div>
                  {#if metadataKind==='mdx'}<div class="field"><label for="metadata-style">{e('stylesheet')}</label><textarea id="metadata-style" rows="5" bind:value={metadataStyle} disabled={!replaceStyle} dir="ltr"></textarea><label><input type="checkbox" bind:checked={replaceStyle}/>{e('replace')}</label></div>{/if}
                </div>
                <div class="job-buttons"><button class="smallbutton" disabled={!info} onclick={loadMetadata}>{e('load')}</button><button class="smallbutton" disabled={!!sessionId || !!mddId || !metadataSource || !(replaceTitle || replaceDescription || (metadataKind==='mdx' && replaceStyle))} onclick={()=>action(saveMetadata)}>{e('save')}</button></div>
              </fieldset><p class="note">{e('hint')}</p><p class="note">{e('limits')}</p>{#if metadataKind==='mdx'}<p class="note">{e('styleHint')}</p>{/if}
            </details>
            <form class="lookup-form" onsubmit={e => {e.preventDefault();void action(() => lookup());}}><label class="search"><Icon name="search"/><input bind:value={query} maxlength="4096" placeholder={t('query')} aria-label={t('query')}/></label><button type="submit" class="smallbutton" disabled={sessionState !== 'ready' || queryPending || pending > 0}>{t('search')}</button></form>
            <div class="tools">
              <aside class="wordpanel"><div class="wordslabel">{u('records')}<bdi>{pageResult?.total ?? 0}</bdi></div><div class="wordlist">{#each pageResult?.rows || [] as row}<button class="word" class:active={selected?.ordinal === row.ordinal} onclick={() => selectEntry(row)} disabled={pending>0 || queryPending}><b><bdi>{row.key}</bdi></b><small>#{row.ordinal}</small></button>{:else}<p class="note">{t('noEntries')}</p>{/each}</div>{#if pageResult?.next_offset !== null && pageResult?.next_offset !== undefined}<button class="smallbutton" disabled={queryPending || pending > 0} onclick={() => action(() => lookup(pageResult!.next_offset!))}>{t('next')}</button>{/if}</aside>
              <section class="reading">
                <div class="readingbar"><div class="segment" aria-label={t('tools')}>
                  {#each ['rendered','split','html'] as mode}<button class:active={previewMode===mode} aria-pressed={previewMode===mode} onclick={()=>previewMode=mode as typeof previewMode}>{p(mode as 'rendered'|'split'|'html')}</button>{/each}
                </div><div class="preview-controls"><select bind:value={previewAppearance} aria-label={p('appearance')}><option value="original">{p('original')}</option><option value="paper">{p('paper')}</option><option value="dark">{p('dark')}</option></select><button class="smallbutton" class:active={detailsOpen} aria-expanded={detailsOpen} onclick={()=>detailsOpen=!detailsOpen}>{p('details')}</button></div></div>
                {#if selected?.text?.startsWith('@@@LINK=') || resolved || redirectError || resolveJob}
                  <div class="redirect-panel">
                    <div class="job-buttons"><button class="smallbutton" disabled={sessionState!=='ready' || !!resolveJob || pending>0 || queryPending} onclick={()=>action(followRedirect)}>{r('follow')}</button>
                      {#if resolveJob}<button class="smallbutton" onclick={()=>action(async()=>{await call({action:'session_cancel',session_id:sessionId,job_id:resolveJob});})}>{t('cancel')}</button>{/if}
                      {#if resolved}<button class="smallbutton" class:active={!showResolved} onclick={()=>showResolved=false}>{r('source')}</button><button class="smallbutton" class:active={showResolved} onclick={()=>showResolved=true}>{r('definition')}</button>{/if}
                    </div>
                    {#if resolved}<label class="redirect-result">{r('targets')}<select bind:value={resolvedIndex} onchange={()=>showResolved=true}>{#each resolved.results as result,i}<option value={i}>{result.row.key} · #{result.row.ordinal} ({i+1}/{resolved.results.length})</option>{/each}</select></label>
                      <ol class="redirect-chain" aria-label={r('chain')}>{#each resolved.results[resolvedIndex]?.chain || [] as hop}<li><bdi>{hop.key}</bdi> <span>#{hop.ordinal} → </span><bdi>{hop.target}</bdi></li>{/each}</ol>
                    {/if}
                    {#if resolveJob}<p class="note" role="status">{r('following')}</p>{/if}{#if redirectError}<p class="note" role="alert">{redirectError}</p>{/if}<p class="note">{r('hint')}</p>
                  </div>
                {/if}
                <div class="reading-content" class:has-details={detailsOpen}>
                  <div class="entry-views" class:split={previewMode==='split'}>
                    {#if previewMode!=='html'}<div class="preview-pane">
                      {#if preview}<iframe class="dictionary-preview" title="" aria-label={p('rendered')} sandbox="" referrerpolicy="no-referrer" srcdoc={preview.document}></iframe>
                      {:else}<div class="preview-placeholder">{!selected?p('empty'):previewBusy?p('loading'):p('unavailable')}{#if previewError || infoError}<p class="note">{previewError || infoError}</p>{/if}</div>{/if}
                    </div>{/if}
                    {#if previewMode!=='rendered'}<pre class="definition-source">{displayed ? displayed.text?.slice(0,65536) ?? `${displayed.bytes?.length || 0} bytes` : t('selectEntry')}</pre>{/if}
                  </div>
                  {#if detailsOpen}<aside class="entry-inspector" aria-label={p('details')}>
                    <h3>{p('record')}</h3><dl><dt>{t('query')}</dt><dd dir="auto">{displayed?.key || '—'}</dd><dt>{p('ordinal')}</dt><dd>{displayed?.ordinal ?? '—'}</dd><dt>{p('characters')}</dt><dd>{displayed?.text?.length ?? 0}</dd><dt>{p('records')}</dt><dd>{String(info?.manifest.records ?? '—')}</dd><dt>{p('sourceHash')}</dt><dd class="hash">{info?.source_sha256 || '—'}</dd><dt>{p('count')}</dt><dd>{preview?.resources || 0}</dd><dt>{p('bytes')}</dt><dd>{preview?.bytes || 0}</dd></dl>
                    <h3>{p('metadata')}</h3>
                    <button class="smallbutton" disabled={!numericStylesheet || sessionState!=='ready' || !!mddId || pending>0} onclick={()=>action(exportStylesheet)}>{z('export')}</button>
                    <p class="note">{!numericStylesheet?z('missing'):mddId?z('detach'):z('hint')}</p>
                    {#if info}<dl>{#each Object.entries(info.attributes) as [key,value]}<dt>{key}</dt><dd dir="auto"><pre>{value.slice(0,4096)}</pre>{#if value.length>4096}…{/if}</dd>{/each}</dl>{:else}<p class="note">{infoError || p('noMetadata')}</p>{/if}
                    <h3>{p('warnings')}</h3>{#each preview?.warnings || [] as warning}<p class="note">{warning}</p>{:else}<p class="note">{previewError || infoError || p('noWarnings')}</p>{/each}<p class="note">{p('profile')}</p>
                  </aside>{/if}
                </div>
                <div class="readingfoot"><span>{previewBusy?p('loading'):p('staticHint')}</span>{#if displayed?.text && displayed.text.length>65536 && previewMode!=='rendered'}<span>{t('clipping')}</span>{/if}</div>
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
