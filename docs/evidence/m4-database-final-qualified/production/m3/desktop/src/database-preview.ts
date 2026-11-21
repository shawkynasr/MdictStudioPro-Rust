// Prepare presentation input only. Rendering stays in the shared sandboxed
// preview; this helper never inserts dictionary text into the app document.
export function databasePreviewInput(text: string, metadata?: Record<string,string>|null): {text:string;sheet:string} {
  const attribute=(name:string)=>Object.entries(metadata || {}).find(([key])=>key.toLowerCase()===name)?.[1] || '';
  if(attribute('format').toLowerCase()==='text') {
    return {text:'<pre>'+text.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')+'</pre>',sheet:''};
  }
  return {text,sheet:attribute('stylesheet')};
}
