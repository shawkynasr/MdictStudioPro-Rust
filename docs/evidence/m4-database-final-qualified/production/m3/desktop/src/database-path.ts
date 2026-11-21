export type DatabaseOperation='txt_to_db'|'db_to_txt'|'jsonl_to_db'|'db_to_jsonl'|'mdx_to_db'|'db_to_mdx';
export function databaseOutputPath(path:string,operation:DatabaseOperation):string {
  if(!path || /[\\/]$/.test(path))return '';
  const extension=operation==='db_to_mdx'?'mdx':operation==='db_to_txt'?'txt':operation==='db_to_jsonl'?'jsonl':'db';
  return new RegExp(`\\.${extension}$`,'i').test(path)?path:`${path}.${extension}`;
}
