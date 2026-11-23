/** Keep the selected archive format and its filename extension in agreement. */
export function dictionaryOutputPath(path: string, format: 'mdx' | 'mdd'): string {
  const name=path.split(/[\\/]/).at(-1);
  if(!name || name==='.' || name==='..')return path;
  if(path.toLowerCase().endsWith('.'+format))return path;
  // Changing the format after choosing a destination should replace the archive
  // suffix, while meaningful names such as dictionary.v2 keep their stem.
  if(/\.(mdx|mdd)$/i.test(path))return path.replace(/\.(mdx|mdd)$/i,'.'+format);
  return path+'.'+format;
}

/** A rebuild is a new file. Do not offer the original MDX name by default. */
export function suggestedDictionaryPath(source:string,format:'mdx'|'mdd'):string {
  if(!source)return 'dictionary.'+format;
  const stem=source.replace(/\.(mdx|mdd|txt|jsonl)$/i,'');
  return stem+'-rebuilt.'+format;
}
