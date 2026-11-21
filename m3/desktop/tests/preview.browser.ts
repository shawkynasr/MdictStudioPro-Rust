// Run against the actual browser engine, separately from the pure Node tests.
// While `npm run tauri dev` is running, open /preview-check.html at port 1420.
import { renderPreview, CHILD_CSP } from '../src/preview';
const results=document.querySelector('#results')!;
const lines:string[]=[];
function check(ok:boolean,name:string) {lines.push((ok?'PASS ':'FAIL ')+name);results.textContent=lines.join('\n');if(!ok)throw new Error(name);}
try {
  const requested:string[]=[];
  const files:Record<string,Uint8Array>={
    'css/main.css':new TextEncoder().encode('.blue{color:rgb(0,0,255)}.tile{background:url(../images/a.png)}'),
    'images/a.png':Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg=='),c=>c.charCodeAt(0)),
  };
  const raw='<link rel="stylesheet" href="css/main.css"><div class="blue tile">CSS_OK</div><img src="images/a.png"><script>parent.postMessage("SCRIPT_RAN","*")</script><svg onload="alert(1)"></svg><iframe src="https://example.invalid/frame"></iframe><form action="https://example.invalid/send"><input></form><a href="javascript:alert(1)">link</a><img onerror="alert(1)" src="https://example.invalid/tracker"><p>`2`MARKER_OK</p>';
  const preview=await renderPreview(raw,'2\n<span style="color:blue">\n</span>\n','original',async key=>{requested.push(key);return files[key]||null;},new AbortController().signal);
  check(!/<script|<iframe|<form|onerror=|javascript:/i.test(preview.document),'active HTML removed');
  check(preview.document.includes(CHILD_CSP),'child CSP embedded');
  check(preview.document.includes('data:image/png;base64,'),'MDD asset embedded');
  check(preview.document.includes('color:blue'),'numeric stylesheet expanded');
  check(requested.filter(key=>key==='images/a.png').length===1,'CSS and IMG share bounded per-preview cache');
  check(!requested.some(key=>key.includes('example.invalid')),'remote URL never reaches resource loader');
  check(preview.warnings.length>0,'blocked content surfaced in warnings');
  let messages=0;window.addEventListener('message',e=>{if(e.data==='SCRIPT_RAN')messages++;});
  const frame=document.createElement('iframe');frame.setAttribute('sandbox','');frame.referrerPolicy='no-referrer';frame.srcdoc=preview.document;
  document.querySelector('#frames')!.append(frame);
  await new Promise(resolve=>{frame.onload=resolve;});
  let blocked=false;try{blocked=frame.contentWindow!.document===null;}catch{blocked=true;}
  check(blocked,'sandbox origin blocks parent DOM inspection');
  // Deliberately bypass sanitizing here to test the boundary itself.
  const attack=document.createElement('iframe');attack.setAttribute('sandbox','');attack.srcdoc='<meta http-equiv="Content-Security-Policy" content="'+CHILD_CSP+'"><script>parent.postMessage("SCRIPT_RAN","*")</script><h3>Static sandbox content</h3>';
  document.querySelector('#frames')!.append(attack);
  await new Promise(resolve=>{attack.onload=resolve;});
  await new Promise(resolve=>setTimeout(resolve,250));
  check(messages===0,'sandbox/CSP block raw scripts independently of sanitizing');
  const abort=new AbortController();abort.abort();
  let cancelled=false;try{await renderPreview('x','','original',null,abort.signal);}catch(e){cancelled=e instanceof DOMException&&e.name==='AbortError';}
  check(cancelled,'aborted preview cannot publish content');
  lines.push('All browser checks passed. Confirm CSS_OK and MARKER_OK appear blue in the first frame.');results.textContent=lines.join('\n');
}catch(e){lines.push('ERROR '+String(e));results.textContent=lines.join('\n');}
