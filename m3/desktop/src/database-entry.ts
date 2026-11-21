import type {DatabaseRow,NativeRequest} from './bridge';
/** Row IDs remain decimal strings, including values outside JS safe integers. */
export function entryCopyRequest(source:string,destination:string,hash:string,row:DatabaseRow,text:string,key?:string):NativeRequest {
  const bad=(message:string):never=>{throw {code:'invalid_input',message};};
  if(!source||!destination||source===destination||!/^[a-f0-9]{64}$/i.test(hash))bad('Load a database snapshot and choose a different output file.');
  let id:bigint;try{id=BigInt(row.rowid);}catch{return bad('Invalid selected row ID.');}
  if(id.toString()!==row.rowid||id<-(2n**63n)||id>2n**63n-1n)bad('Invalid selected row ID.');
  if(key!==undefined&&(!key||key==='</>'||/[\u0000\r\n\ud800-\udfff]/u.test(key)||new TextEncoder().encode(key).length>4096))bad('Headword must fit 4 KiB UTF-8, be nonempty, and contain no NUL, CR, LF or TXT delimiter.');
  if(new TextEncoder().encode(text).length>8192||/[\ud800-\udfff]/u.test(text))bad('Definition edit must fit 8 KiB of valid UTF-8 text.');
  const request:NativeRequest={kind:'database',request:{operation:'db_edit_entry',source,destination,expected_source_sha256:hash,rowid:row.rowid,text,...(key===undefined?{}:{key})}};
  if(new TextEncoder().encode(JSON.stringify({action:'submit',request})).length>65536)bad('Encoded edit command exceeds 64 KiB.');
  return request;
}

/** Deletion carries identity only; even a large stored body is never sent back. */
export function entryDeleteRequest(source:string,destination:string,hash:string,row:DatabaseRow):NativeRequest {
  // Reuse the same identity/transport checks without submitting a definition edit.
  const checked=entryCopyRequest(source,destination,hash,row,'');
  if(checked.kind!=='database'||checked.request.operation!=='db_edit_entry')throw {code:'internal',message:'Unexpected entry preflight.'};
  const {text:_,...identity}=checked.request;
  return {kind:'database',request:{...identity,operation:'db_delete_entry'}};
}

/** Additions carry no source row ID and keep duplicate headwords as new records. */
export function entryAddRequest(source:string,destination:string,hash:string,key:string,text:string):NativeRequest {
  entryCopyRequest(source,destination,hash,{rowid:'0',key:'',text:''},text,key);
  return {kind:'database',request:{operation:'db_add_entry',source,destination,expected_source_sha256:hash,key,text}};
}
