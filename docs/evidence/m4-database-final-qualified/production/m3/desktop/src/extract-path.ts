/** Destination helpers only; filesystem validation and no-clobber stay native. */
export type ExtractOperation = 'txt' | 'jsonl' | 'mdd';
export function exportFilePath(path:string,format:'txt'|'jsonl'):string {
  const name=path.split(/[\\/]/).at(-1);
  if(!name || name==='.' || name==='..')return path;
  if(path.toLowerCase().endsWith('.'+format))return path;
  return /\.(mdx|mdd|txt|jsonl)$/i.test(path)?path.replace(/\.(mdx|mdd|txt|jsonl)$/i,'.'+format):path+'.'+format;
}
export function sourceParent(path:string):string {
  const index=Math.max(path.lastIndexOf('/'),path.lastIndexOf('\\'));
  return index<0?'':path.slice(0,index+1);
}
export function resourceFolderName(source:string):string {
  const stem=(source.split(/[\\/]/).at(-1)||'').replace(/\.mdd$/i,'').replace(/[\x00-\x1f\x7f<>:"/\\|?*]/g,'-').trim().replace(/[ .]+$/,'');
  const base=stem || 'dictionary';
  // Leave space for the suffix in a single portable UTF-8 path component.
  let result='';for(const char of base){if(new TextEncoder().encode(result+char).length>220)break;result+=char;}
  return result+'_resources';
}
export function resourceDestination(parent:string,name:string):string|null {
  if(!parent || !name || name==='.' || name==='..' || /[\x00-\x1f\x7f<>:"/\\|?*]/.test(name) || /[ .]$/.test(name) || new TextEncoder().encode(name).length>255)return null;
  const base=name.split('.')[0].toUpperCase();
  if(/^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])$/.test(base))return null;
  const separator=parent.includes('\\')&&!parent.includes('/')?'\\':'/';
  return parent.replace(/[\\/]+$/,'')+separator+name;
}
