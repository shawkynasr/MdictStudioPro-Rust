// Static dictionary preview. Dictionary markup never enters the app document.
// The iframe sandbox and child CSP are the security boundary; sanitizing also
// makes resource behavior predictable. This module has no native-command access.
export type Appearance = 'original' | 'paper' | 'dark';
export type ResourceLoader = (key: string, signal: AbortSignal) => Promise<Uint8Array | null>;
export interface Preview { document: string; warnings: string[]; resources: number; bytes: number }
export const CHILD_CSP = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
const MAX_HTML = 131072, MAX_EXPANDED = 262144, MAX_ASSET = 524288, MAX_BUNDLE = 4194304, MAX_RESOURCES = 32;
export function aborted(signal: AbortSignal) { if (signal.aborted) throw new DOMException('Preview cancelled', 'AbortError'); }
export function resourcePath(value: string, base = ''): string | null {
  let path: string;
  try { path = decodeURIComponent(value.trim().split(/[?#]/,1)[0]).replaceAll('\\','/'); } catch { return null; }
  if (!path || path.length > 2048 || /[\x00-\x1f\x7f:]/.test(path) || path.startsWith('//')) return null;
  const parts = path.startsWith('/') ? [] : base.split('/').slice(0,-1);
  for (const part of path.split('/')) {
    if (!part || part === '.') continue;
    if (part === '..') { if (!parts.length) return null; parts.pop(); }
    else parts.push(part);
  }
  return parts.length ? parts.join('/') : null;
}
export function resourceCandidates(path: string): string[] {
  return [...new Set(['\\'+path.replaceAll('/','\\'), path, '/'+path, path.replaceAll('/','\\')])];
}
export function expandStylesheet(text: string, sheet: string): string {
  if (new TextEncoder().encode(text).length > MAX_HTML || new TextEncoder().encode(sheet).length > 65536) throw new Error('Preview text exceeds the static preview profile');
  if (!sheet) return text;
  const lines=sheet.replaceAll('\r\n','\n').split('\n');
  if (lines.at(-1)==='') lines.pop();
  if (lines.length % 3) throw new Error('Malformed numeric stylesheet: expected ID, prefix and suffix');
  const styles=new Map<string,[string,string]>();
  for (let i=0;i<lines.length;i+=3) {
    const id=lines[i];
    if (!/^\d{1,32}$/.test(id) || styles.has(id)) throw new Error('Malformed or duplicate numeric stylesheet ID');
    styles.set(id,[lines[i+1],lines[i+2]]);
  }
  const chunks=text.split(/`(\d+)`/);let result=chunks[0],size=new TextEncoder().encode(chunks[0]).length;
  for (let i=1;i<chunks.length;i+=2) {
    const pair=styles.get(chunks[i]);
    // Unknown markers stay visible instead of silently losing source content.
    const next=pair ? pair[0]+chunks[i+1]+pair[1] : '`'+chunks[i]+'`'+chunks[i+1];
    size+=new TextEncoder().encode(next).length;
    if (size>MAX_EXPANDED) throw new Error('Expanded stylesheet exceeds preview profile');
    result+=next;
  }
  return result;
}
function mime(path: string): string | null {
  const ext=path.toLowerCase().split('.').at(-1);
  return ({png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',gif:'image/gif',webp:'image/webp',avif:'image/avif',ico:'image/x-icon',ttf:'font/ttf',otf:'font/otf',woff:'font/woff',woff2:'font/woff2'} as Record<string,string>)[ext || ''] || null;
}
function dataURL(bytes: Uint8Array, type: string) {
  let raw='';for (let i=0;i<bytes.length;i+=8192) raw+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return 'data:'+type+';base64,'+btoa(raw);
}
// A deliberately small CSS resource grammar. Imports are disabled; dictionaries
// can attach ordinary <link rel=stylesheet> files from the selected MDD.
export async function rewriteCSS(css: string, base: string, asset: (url: string, base: string) => Promise<string>, warn: (message:string)=>void): Promise<string> {
  if (css.length>MAX_HTML) throw new Error('Stylesheet exceeds preview profile');
  css=css.replace(/\/\*[\s\S]*?\*\//g,'');
  css=css.replace(/@import\b[^;]*(;|$)/gi,()=>{warn('CSS @import is disabled in the static preview');return '';});
  const pattern=/url\(\s*(?:"([^"]*)"|'([^']*)'|([^\s)]*))\s*\)/gi;
  let out='',end=0;
  for (const match of css.matchAll(pattern)) {
    out+=css.slice(end,match.index)+`url("${await asset(match[1] ?? match[2] ?? match[3],base)}")`;
    end=match.index!+match[0].length;
    if (out.length>8*MAX_BUNDLE) throw new Error('Expanded CSS exceeds preview profile');
  }
  return out+css.slice(end);
}
export async function renderPreview(text: string, sheet: string, appearance: Appearance, load: ResourceLoader | null, signal: AbortSignal): Promise<Preview> {
  aborted(signal);
  const warnings:string[]=[];const warn=(s:string)=>{if(warnings.length<20&&!warnings.includes(s))warnings.push(s);};
  let resources=0,loaded=0,bytes=0,encoded=0;
  const cache=new Map<string,Promise<Uint8Array|null>>();
  async function read(path:string) {
    aborted(signal);
    if (!load) {warn('Attach a matching MDD to load images, fonts and CSS');return null;}
    if (cache.has(path)) return cache.get(path)!;
    if (++resources>MAX_RESOURCES) {warn('Resource count limit reached (32)');return null;}
    const promise=(async()=>{
      let data:Uint8Array|null;
      try {data=await load(path,signal);aborted(signal);} catch(e) {
        aborted(signal);warn('Resource unavailable: '+path+' ('+String(e instanceof Error?e.message:e).slice(0,180)+')');return null;
      }
      if (!data) {warn('Missing resource: '+path);return null;}
      if (data.length>MAX_ASSET || bytes+data.length>MAX_BUNDLE) {warn('Resource size limit: '+path);return null;}
      bytes+=data.length;loaded+=1;return data;
    })();cache.set(path,promise);return promise;
  }
  async function asset(url:string,base:string) {
    const path=resourcePath(url,base);const type=path&&mime(path);
    if (!path || !type) {warn('Blocked or unsupported resource: '+url.slice(0,100));return '';}
    const data=await read(path);if(!data)return '';
    encoded+=Math.ceil(data.length/3)*4;
    if(encoded>8*1024*1024) {warn('Embedded resource expansion limit reached');return '';}
    return dataURL(data,type);
  }
  async function css(raw:string,base:string) {return rewriteCSS(raw,base,asset,warn);}
  // template contents remain inert during parsing, including image/link URLs.
  // No untrusted node is attached to the live application document.
  const doc=document.implementation.createHTMLDocument('');
  const template=doc.createElement('template');template.innerHTML=expandStylesheet(text,sheet);
  const nodes=Array.from(template.content.querySelectorAll('*'));
  if (nodes.length>4000) throw new Error('Entry exceeds the 4,000 element preview profile');
  const forbidden=new Set(['script','iframe','frame','frameset','object','embed','base','meta','form','input','button','select','textarea','template','audio','video','source','track']);
  for (const el of nodes) {
    aborted(signal);
    if (!template.content.contains(el)) continue;
    const tag=el.localName;
    if (el.namespaceURI!=='http://www.w3.org/1999/xhtml' || forbidden.has(tag)) {el.remove();warn('Active content removed');continue;}
    if (tag==='link') {
      if ((el.getAttribute('rel')||'').toLowerCase()==='stylesheet') {
        const path=resourcePath(el.getAttribute('href')||'');
        if (path?.toLowerCase().endsWith('.css')) {
          const data=await read(path);
          if(data) {
            try {
              const style=doc.createElement('style');style.textContent=await css(new TextDecoder('utf-8',{fatal:true}).decode(data),path);el.replaceWith(style);continue;
            } catch(e) {aborted(signal);warn('Stylesheet unavailable: '+path);}

          }
        } else warn('Blocked stylesheet URL');
      }
      el.remove();continue;
    }
    // Allow only passive presentation attributes. Strip all navigation except
    // local anchors; entry:// links and redirects remain readable in HTML mode.
    for (const attr of Array.from(el.attributes)) {
      const name=attr.name.toLowerCase();
      if (name==='style') el.setAttribute('style',await css(attr.value,''));
      else if (tag==='img' && name==='src') el.setAttribute('src',await asset(attr.value,''));
      else if (tag==='a' && name==='href' && /^#[\w-]+$/.test(attr.value)) continue;
      else if (!/^(id|class|title|lang|dir|alt|width|height|colspan|rowspan|align|valign|bgcolor|color|face|size|border|cellpadding|cellspacing|role|aria-label)$/.test(name)) el.removeAttribute(attr.name);
    }
    if(tag==='style')el.textContent=await css(el.textContent||'','');
  }
  // A serialized CSS value cannot terminate its containing style element.
  const safeBody=template.innerHTML.replace(/<style\b([^>]*)>([\s\S]*?)<\/style>/gi,(_all,attrs,body)=>'<style'+attrs+'>'+body.replaceAll('<','\\3c ')+'</style>');
  const override=appearance==='original'?'':appearance==='paper'?'html,body{background:#f7f2e7!important;color:#342f29!important;color-scheme:light!important}':'html,body{background:#18212c!important;color:#e5ebf5!important}a{color:#9bc0ff!important}';
  const output='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+CHILD_CSP+'"><meta name="referrer" content="no-referrer"><style>html{color-scheme:light}body{margin:24px;font:16px/1.65 system-ui,sans-serif;overflow-wrap:anywhere}img{max-width:100%;height:auto}</style></head><body>'+safeBody+'<style>'+override+'</style></body></html>';
  if(output.length>12*MAX_BUNDLE) throw new Error('Preview document exceeds profile');
  aborted(signal);return {document:output,warnings,resources:loaded,bytes};
}
