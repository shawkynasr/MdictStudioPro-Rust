/** Explicit scalar-map-v1 options; no plugin import or schema execution in the UI. */
export function parsePluginOptions(text:string):Record<string,string|number|boolean> {
  function invalid():never { throw {code:'invalid_input',message:'Plugin options: expected an object with <=64 scalar fields and <=8 KiB JSON.'}; }
  const bytes=(s:string)=>new TextEncoder().encode(s).length;
  const wellFormed=(s:string)=>Array.from(s).every(c=>{const n=c.codePointAt(0)!;return n<0xd800||n>0xdfff;});
  if(bytes(text)>8192)invalid();
  let value:unknown;
  try { value=JSON.parse(text.trim()||'{}'); } catch { invalid(); }
  if(!value || typeof value!=='object' || Array.isArray(value))invalid();
  const entries=Object.entries(value);
  if(entries.length>64)invalid();
  for(const [key,v] of entries) {
    if(!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(key))invalid();
    if(typeof v==='string') { if(!wellFormed(v)||bytes(v)>2048)invalid(); }
    else if(typeof v==='number') { if(!Number.isFinite(v)||Math.abs(v)>Number.MAX_SAFE_INTEGER)invalid(); }
    else if(typeof v!=='boolean')invalid();
  }
  if(bytes(JSON.stringify(value))>8192)invalid();
  return value as Record<string,string|number|boolean>;
}

export type PluginPreset={name:string;python:string;plugin:string;class_name:string;options:string};
export const PLUGIN_PRESETS_KEY='studio-plugin-presets-v1';
const bytes=(value:string)=>new TextEncoder().encode(value).length;
const validText=(value:unknown,max:number):value is string=>typeof value==='string'&&value.length>0&&bytes(value)<=max&&!/[\u0000\r\n]/.test(value)&&Array.from(value).every(c=>{const n=c.codePointAt(0)!;return n<0xd800||n>0xdfff;});
function presetError(message:string):never {throw {code:'invalid_input',message};}
function checkedPreset(value:unknown):PluginPreset {
  if(!value||typeof value!=='object'||Array.isArray(value))presetError('Invalid plugin preset.');
  const p=value as Record<string,unknown>;
  if(Object.keys(p).sort().join(',')!=='class_name,name,options,plugin,python')presetError('Unexpected plugin preset fields.');
  if(!validText(p.name,256)||p.name.trim()!==p.name||Array.from(p.name).length>64||!validText(p.python,4096)||!validText(p.plugin,4096)||typeof p.class_name!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(p.class_name)||typeof p.options!=='string')presetError('Enter a preset name, Python path, plugin path and class.');
  const options=JSON.stringify(parsePluginOptions(p.options));
  return {name:p.name,python:p.python,plugin:p.plugin,class_name:p.class_name,options};
}
export function encodePluginPresets(items:PluginPreset[]):string {
  if(!Array.isArray(items)||items.length>8)presetError('At most eight plugin presets can be saved.');
  const checked=items.map(checkedPreset);
  if(new Set(checked.map(p=>p.name)).size!==checked.length)presetError('Plugin preset names must be unique.');
  const text=JSON.stringify({version:1,items:checked});
  if(bytes(text)>65536)presetError('Saved plugin presets exceed 64 KiB.');
  return text;
}
export function decodePluginPresets(raw:string|null):PluginPreset[] {
  if(raw===null)return [];
  if(bytes(raw)>65536)presetError('Saved plugin presets exceed 64 KiB.');
  let value:unknown;try{value=JSON.parse(raw);}catch{presetError('Saved plugin presets contain invalid JSON.');}
  if(!value||typeof value!=='object'||Array.isArray(value))presetError('Invalid plugin preset storage.');
  const p=value as Record<string,unknown>;
  if(Object.keys(p).sort().join(',')!=='items,version'||p.version!==1||!Array.isArray(p.items))presetError('Unsupported plugin preset storage.');
  const items=p.items.map(checkedPreset);encodePluginPresets(items);return items;
}
export function savePluginPreset(items:PluginPreset[],draft:PluginPreset,replaceName?:string):PluginPreset[] {
  const next=decodePluginPresets(encodePluginPresets(items));const checked=checkedPreset(draft);
  const index=replaceName===undefined?-1:next.findIndex(p=>p.name===replaceName);
  if(replaceName!==undefined&&index<0)presetError('Select a preset to update.');
  if(next.some((p,i)=>p.name===checked.name&&i!==index))presetError('This preset name already exists. Use Update selected or another name.');
  if(index<0)next.push(checked);else next[index]=checked;
  encodePluginPresets(next);return next;
}
export function loadPluginPreset(items:PluginPreset[],name:string):PluginPreset & {trusted:false} {
  const p=decodePluginPresets(encodePluginPresets(items)).find(p=>p.name===name);
  if(!p)presetError('Select a saved plugin preset.');
  return {...p,trusted:false};
}
export function deletePluginPreset(items:PluginPreset[],name:string):PluginPreset[] {
  loadPluginPreset(items,name);return items.filter(p=>p.name!==name).map(p=>({...p}));
}
