import type {Locale} from './i18n';
export type TextSize = 'standard' | 'large' | 'larger';
export function textSizePreference(value:unknown):TextSize {
  return value==='large'||value==='larger'?value:'standard';
}
const labels={
  en:{textSize:'Interface text size',standard:'Standard',large:'Large',larger:'Extra large'},
  zh:{textSize:'界面文字大小',standard:'标准',large:'大',larger:'更大'},
  ar:{textSize:'حجم نص الواجهة',standard:'قياسي',large:'كبير',larger:'كبير جدًا'}
};
export const readabilityLabel=(locale:Locale,key:keyof typeof labels.en)=>labels[locale][key];
