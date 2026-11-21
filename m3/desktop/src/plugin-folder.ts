import {parsePluginCatalog} from './plugin-catalog.ts';
import type {PluginCatalog,PluginClass} from './plugin-catalog.ts';
export type FolderEntry={filename:string;source:string;plugin_sha256:string|null;catalog:PluginCatalog|null;error:{code:string;message:string}|null};
export type PluginFolder={profile:'trusted-python-folder-v1';folder:string;destination:string;ignored_entries:number;entries:FolderEntry[]};
export type FolderChoice={id:string;entry:FolderEntry;converter:PluginClass};
function invalid():never{throw {code:'invalid_input',message:'Invalid or oversized plugin folder catalog.'};}
const bytes=(s:string)=>new TextEncoder().encode(s).length;
function obj(v:unknown):Record<string,unknown>{if(!v||typeof v!=='object'||Array.isArray(v))invalid();return v as Record<string,unknown>;}
function text(v:unknown,max:number):v is string{return typeof v==='string'&&bytes(v)<=max&&!v.includes('\0')&&Array.from(v).every(c=>{const n=c.codePointAt(0)!;return n<0xd800||n>0xdfff;});}
export function parsePluginFolder(raw:unknown):PluginFolder {
  if(bytes(JSON.stringify(raw)??'')>131072)invalid();
  const v=obj(raw);
  if(Object.keys(v).sort().join(',')!=='destination,entries,folder,ignored_entries,profile'||v.profile!=='trusted-python-folder-v1'||!text(v.folder,16384)||!v.folder.startsWith('/')||!text(v.destination,16384)||typeof v.ignored_entries!=='number'||!Number.isInteger(v.ignored_entries)||Number(v.ignored_entries)<0||Number(v.ignored_entries)>256||!Array.isArray(v.entries)||v.entries.length>16||v.entries.length+Number(v.ignored_entries)>256)invalid();
  const names=new Set<string>();
  for(const value of v.entries){
    const e=obj(value);
    if(Object.keys(e).sort().join(',')!=='catalog,error,filename,plugin_sha256,source'||!text(e.filename,256)||!e.filename.endsWith('.py')||e.filename.startsWith('__')||/[\\/]/.test(e.filename)||names.has(e.filename)||!text(e.source,16641)||e.source!==(v.folder.endsWith('/')?v.folder:v.folder+'/')+e.filename||!(e.plugin_sha256===null||typeof e.plugin_sha256==='string'&&/^[a-f0-9]{64}$/.test(e.plugin_sha256)))invalid();
    names.add(e.filename);
    if(e.error!==null){
      const error=obj(e.error);
      if(Object.keys(error).sort().join(',')!=='code,message'||!text(error.code,64)||!text(error.message,2048)||e.catalog!==null)invalid();
    }else{
      if(e.plugin_sha256===null||e.catalog===null)invalid();
      parsePluginCatalog(e.catalog);
    }
  }
  return JSON.parse(JSON.stringify(raw)) as PluginFolder;
}
export function folderChoices(folder:PluginFolder):FolderChoice[]{
  return folder.entries.flatMap(entry=>entry.catalog?.classes.map(converter=>({id:JSON.stringify([entry.filename,converter.class_name]),entry,converter}))??[]);
}
/** Namespace by filename + class; repeated display names never overwrite. */
export function selectFolderChoice(folder:PluginFolder,id:string):FolderChoice {
  const choice=folderChoices(folder).find(c=>c.id===id);if(!choice)invalid();return choice;
}
