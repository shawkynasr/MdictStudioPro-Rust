import type {NativeRequest} from './bridge';
export interface DatabaseMetadataEdits {title?:string;description?:string;stylesheet?:string}
/** Canonicalize editor delimiters without trimming HTML or empty suffixes. */
export function editorStylesheet(value:string):string {
  if(value==='')return '';
  let style=value.replace(/\r\n?/g,'\n');
  if(!style.endsWith('\n'))style+='\n';
  const lines=style.slice(0,-1).split('\n'),ids=new Set<string>();
  const bad=():never=>{throw {code:'invalid_input',message:'Use complete ID/opening HTML/closing HTML triplets with unique numeric IDs and no tabs.'};};
  if(lines.length%3)bad();
  for(let i=0;i<lines.length;i+=3) {
    if(!/^[0-9]{1,32}$/.test(lines[i])||ids.has(lines[i])||lines[i+1].includes('\t')||lines[i+2].includes('\t'))bad();
    ids.add(lines[i]);
  }
  return style;
}
/** Check the bounded command before closing the pinned reader. */
export function metadataCopyRequest(source:string,destination:string,hash:string,metadata:Record<string,string>|null|undefined,edits:DatabaseMetadataEdits):NativeRequest {
  const bad=(message:string):never=>{throw {code:'invalid_input',message};};
  if(!source||!destination||source===destination||!metadata||!/^[a-f0-9]{64}$/i.test(hash))bad('Load an MDX database snapshot and choose a different output file.');
  edits=edits.stylesheet===undefined?edits:{...edits,stylesheet:editorStylesheet(edits.stylesheet)};
  if(edits.title===undefined&&edits.description===undefined&&edits.stylesheet===undefined)bad('Choose title, description or stylesheet to replace.');
  for(const [name,cap] of [['title',4096],['description',8192],['stylesheet',16384]] as const) {
    const value=edits[name];if(value===undefined)continue;
    if(new TextEncoder().encode(value).length>cap||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ud800-\udfff\ufffe\uffff]/u.test(value))bad('Title/description/stylesheet must fit 4/8/16 KiB, using valid XML text.');
  }
  const request:NativeRequest={kind:'database',request:{operation:'db_edit_metadata',source,destination,expected_source_sha256:hash,edits}};
  if(new TextEncoder().encode(JSON.stringify({action:'submit',request})).length>65536)bad('Encoded metadata command exceeds 64 KiB.');
  return request;
}
