import {parsePluginCatalog,pluginDefaults} from './plugin-catalog.ts';
import type {PluginCatalog} from './plugin-catalog.ts';
import {resourceDestination,sourceParent} from './extract-path.ts';
export const PLUGIN_PYTHON_KEY='studio-plugin-python-v1';
const bytes=(s:string)=>new TextEncoder().encode(s).length;
function invalid(message:string):never{throw {code:'invalid_input',message};}
export function checkedPythonPath(value:unknown):string {
  if(typeof value!=='string'||!value||bytes(value)>4096||/[\u0000\r\n]/.test(value)||Array.from(value).some(c=>{const n=c.codePointAt(0)!;return n>=0xd800&&n<=0xdfff;}))invalid('Choose a Python executable.');
  return value;
}
export function pluginDrop(paths:string[]):{kind:'plugin'|'source';path:string} {
  if(paths.length!==1||typeof paths[0]!=='string'||!paths[0]||bytes(paths[0])>16384||paths[0].includes('\0'))invalid('Drop one plugin .py file or one input file.');
  return {kind:/\.py$/i.test(paths[0])?'plugin':'source',path:paths[0]};
}
export function pluginOutputSelection(path:string):{parent:string;folder:string} {
  const parent=sourceParent(path),folder=path.split(/[\\/]/).at(-1)??'';
  if(!parent||resourceDestination(parent,folder)!==path)invalid('Choose a new result folder name.');
  return {parent,folder};
}
export type ImportContext={python:string;plugin:string;revision:number};
export function samePluginImport(a:ImportContext,b:ImportContext):boolean{return a.python===b.python&&a.plugin===b.plugin&&a.revision===b.revision;}
export function importedPlugin(value:unknown):{catalog:PluginCatalog;hash:string;className:string;options:string} {
  const v=value as {kind?:unknown;receipt?:{profile?:unknown;plugin_sha256?:unknown;catalog?:unknown}}|null;
  if(!v||v.kind!=='python_probe'||v.receipt?.profile!=='trusted-python-probe-v1'||typeof v.receipt.plugin_sha256!=='string'||!/^[a-f0-9]{64}$/.test(v.receipt.plugin_sha256))invalid('Invalid plugin import response.');
  const catalog=parsePluginCatalog(v.receipt.catalog);
  const only=catalog.classes.length===1?catalog.classes[0]:null;
  return {catalog,hash:v.receipt.plugin_sha256,className:only?.class_name??'',options:only?pluginDefaults(only):'{}'};
}
