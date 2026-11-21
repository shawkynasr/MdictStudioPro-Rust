import {parsePluginOptions} from './plugin-options.ts';
export type Scalar=string|number|boolean;
export type OptionField={key:string;type:'string'|'boolean'|'number'|'choice';label:string;default:Scalar;choices:string[]};
export type PluginClass={class_name:string;name:string;description:string;fields:OptionField[];schema_error:string|null};
export type PluginCatalog={version:1;classes:PluginClass[]};
const bytes=(s:string)=>new TextEncoder().encode(s).length;
function invalid():never {throw {code:'invalid_input',message:'Unsupported or invalid plugin inspection catalog.'};}
function object(v:unknown):Record<string,unknown>{if(!v||typeof v!=='object'||Array.isArray(v))invalid();return v as Record<string,unknown>;}
function text(v:unknown,max:number):v is string{return typeof v==='string'&&bytes(v)<=max&&Array.from(v).every(c=>{const n=c.codePointAt(0)!;return n<0xd800||n>0xdfff;});}
export function parsePluginCatalog(value:unknown):PluginCatalog {
  if(bytes(JSON.stringify(value)??'')>32768)invalid();
  const v=object(value);
  if(Object.keys(v).sort().join(',')!=='classes,version'||v.version!==1||!Array.isArray(v.classes)||v.classes.length>16)invalid();
  const names=new Set<string>();
  for(const raw of v.classes){
    const c=object(raw);
    if(Object.keys(c).sort().join(',')!=='class_name,description,fields,name,schema_error'||!text(c.class_name,128)||!/^[A-Za-z_][A-Za-z0-9_]*$/.test(c.class_name)||names.has(c.class_name)||!text(c.name,256)||!text(c.description,512)||!(c.schema_error===null||text(c.schema_error,1024))||!Array.isArray(c.fields)||c.fields.length>16||(c.schema_error!==null&&c.fields.length))invalid();
    names.add(c.class_name);
    const defaults:Record<string,Scalar>=Object.create(null);
    for(const rawField of c.fields){
      const f=object(rawField);
      if(Object.keys(f).sort().join(',')!=='choices,default,key,label,type'||!text(f.key,64)||!/^[A-Za-z_][A-Za-z0-9_]*$/.test(f.key)||Object.hasOwn(defaults,f.key)||!text(f.label,256)||!Array.isArray(f.choices)||f.choices.length>16||!f.choices.every(s=>text(s,256)))invalid();
      if(!((f.type==='string'||f.type==='choice')&&typeof f.default==='string'||f.type==='boolean'&&typeof f.default==='boolean'||f.type==='number'&&typeof f.default==='number'))invalid();
      if(f.type==='choice'){if(typeof f.default!=='string'||!f.choices.includes(f.default)||new Set(f.choices).size!==f.choices.length)invalid();}
      else if(f.choices.length)invalid();
      defaults[f.key]=f.default as Scalar;
    }
    parsePluginOptions(JSON.stringify(defaults));
  }
  return JSON.parse(JSON.stringify(value)) as PluginCatalog;
}
export function pluginDefaults(c:PluginClass):string {
  return JSON.stringify(parsePluginOptions(JSON.stringify(Object.fromEntries(c.fields.map(f=>[f.key,f.default])))));
}
export function setPluginField(options:string,field:OptionField,value:Scalar):string {
  const next=parsePluginOptions(options);
  const valid=field.type==='string'?typeof value==='string':field.type==='choice'?typeof value==='string'&&field.choices.includes(value):field.type==='boolean'?typeof value==='boolean':typeof value==='number'&&Number.isFinite(value);
  if(!valid)invalid();
  Object.defineProperty(next,field.key,{value,enumerable:true,configurable:true,writable:true});
  return JSON.stringify(parsePluginOptions(JSON.stringify(next)));
}
export function pluginFormValues(options:string,c:PluginClass):Record<string,Scalar>|null {
  try{
    const v=parsePluginOptions(options);
    for(const f of c.fields){const x=v[f.key];if(!Object.hasOwn(v,f.key)||!((f.type==='string'||f.type==='choice')&&typeof x==='string'||f.type==='boolean'&&typeof x==='boolean'||f.type==='number'&&typeof x==='number')||(f.type==='choice'&&!f.choices.includes(x as string)))return null;}
    return v;
  }catch{return null;}
}
