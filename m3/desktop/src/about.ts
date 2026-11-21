import type { Locale } from './i18n';

export const project = {
  name: 'Mdict Studio Pro',
  author: 'Shawky Nasr',
  email: 'shawkynasr@126.com',
  repository: 'https://github.com/shawkynasr/MdictStudioPro-Rust',
  releases: 'https://github.com/shawkynasr/MdictStudioPro-Rust/releases',
} as const;

const en = {about:'About',author:'Author',version:'Version',repository:'Official repository',releases:'View releases',updates:'Updates',manual:'Updates are installed manually. Open Releases to see available downloads.',refactor:'A Rust/Tauri refactor of MdictStudioPro.',unavailable:'Unavailable',openFailed:'Could not open the link. Copy the address shown below into your browser.'};
type Labels = {[K in keyof typeof en]:string};
const zh:Labels = {about:'关于',author:'作者',version:'版本',repository:'官方仓库',releases:'查看发布版本',updates:'更新',manual:'更新需要手动安装。打开发布页面查看可用下载。',refactor:'MdictStudioPro 的 Rust/Tauri 重构版本。',unavailable:'无法获取',openFailed:'无法打开链接。请将下方地址复制到浏览器中。'};
const ar:Labels = {about:'حول التطبيق',author:'المؤلف',version:'الإصدار',repository:'المستودع الرسمي',releases:'عرض الإصدارات',updates:'التحديثات',manual:'تُثبَّت التحديثات يدويًا. افتح صفحة الإصدارات لعرض التنزيلات المتاحة.',refactor:'إعادة بناء MdictStudioPro باستخدام Rust وTauri.',unavailable:'غير متاح',openFailed:'تعذر فتح الرابط. انسخ العنوان أدناه إلى المتصفح.'};
const labels={en,zh,ar};
export const aboutLabel=(locale:Locale,key:keyof Labels):string=>labels[locale][key];
