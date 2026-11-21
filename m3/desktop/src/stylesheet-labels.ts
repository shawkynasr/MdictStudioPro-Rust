import type {Locale} from './i18n';
const en={export:'Export numeric stylesheet…',missing:'No numeric stylesheet in this header. External CSS files are separate MDD resources.',detach:'Detach the MDD reader before exporting the stylesheet.',hint:'Saves the decoded MDX StyleSheet exactly as UTF-8 text, without adding a BOM or changing line endings.'};
const zh:Record<keyof typeof en,string>={export:'导出数字样式表…',missing:'此头信息中没有数字样式表。外部 CSS 文件属于独立的 MDD 资源。',detach:'导出样式表前请分离 MDD 阅读器。',hint:'将解码后的 MDX StyleSheet 原样保存为 UTF-8 文本，不添加 BOM，也不更改换行符。'};
const ar:Record<keyof typeof en,string>={export:'تصدير جدول الأنماط الرقمية…',missing:'لا يوجد جدول أنماط رقمي في الترويسة. ملفات CSS الخارجية موارد منفصلة في MDD.',detach:'افصل قارئ MDD قبل تصدير جدول الأنماط.',hint:'يحفظ قيمة StyleSheet المفكوكة من MDX كنص UTF-8 كما هي، دون إضافة BOM أو تغيير فواصل الأسطر.'};
export const stylesheetLabel=(locale:Locale,key:keyof typeof en)=>(locale==='ar'?ar:locale==='zh'?zh:en)[key];
