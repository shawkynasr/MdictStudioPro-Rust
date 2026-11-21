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
