import type { Locale } from './i18n';
const en={
  workspace:'WORKSPACE',data:'DATA & LANGUAGE',inspect:'INSPECT',personal:'Personal workspace',
  buildTitle:'Build dictionary',extractTitle:'Extract dictionary',convertTitle:'Convert source',
  buildLead:'From source files to something worth looking up.',extractLead:'Bring entries and resources back into your workspace.',
  convertersLead:'A dedicated starting point for each source format.',toolsLead:'Inspect the meaning, the markup and the details.',jobsLead:'Your work continues in the background.',
  source:'Source',stepOne:'01 / Choose input',dictionary:'Dictionary',stepTwo:'02 / Configure output',name:'Name',format:'Format',saveTo:'Save to',
  more:'More options',output:'Output',location:'Location',localFolder:'Local folder',chooseSource:'Choose a source file',chooseDestination:'Choose a new destination',
  jsonl:'JSONL dictionary manifest',resourceManifest:'JSONL resource manifest',archive:'MDict v2 archive',converterSource:'Dictionary source',
  sourceHint:'Your source stays on your computer.',noSource:'Choose a file to begin.',outputHint:'Output details update as you configure your dictionary.',
  mdx:'MDict v2 dictionary',mdd:'MDict resource archive',txt:'Dictionary text',jsonlOutput:'JSONL entries',folder:'Extracted resources',
  duplicate:'Keep duplicate entries',noClobber:'Never replace existing outputs',background:'Work in the background',
  local:'Your files. Your computer.',selectConverter:'Choose a converter',configureConverter:'Configure conversion',
  database:'Database',morphology:'Morphology',later:'Planned',laterText:'This workspace will be added in a later integration slice.',
  inputDetails:'Source path',sourceNote:"Build from UTF-8 dictionary TXT or a JSONL manifest. Converters produce TXT.",
  profile:'Packing profile',bounded:'Bounded · 100,000 records',block:'Block spool · 250,000 records',
  connection:'Native runtime connected',notConnected:'Connecting to native runtime',newIndex:'Choose a new index location',
  records:'Entries',sourceMode:'HTML source',entryDetails:'Record details',currentJob:'Current job',
  files:'Files',noOutput:'No output selected',sourceType:'Source type',receipt:'Verified publication receipt',
};
type Labels=typeof en;
const zh:Labels={
  workspace:'工作区',data:'数据与语言',inspect:'检查',personal:'个人工作区',buildTitle:'构建词典',extractTitle:'提取词典',convertTitle:'转换源文件',
  buildLead:'将源文件整理为值得查阅的词典。',extractLead:'将词条和资源导出到工作区。',convertersLead:'为每种源格式提供专用入口。',toolsLead:'检查释义、源码与词条详情。',jobsLead:'任务在后台继续进行。',
  source:'源文件',stepOne:'01 / 选择输入',dictionary:'词典',stepTwo:'02 / 配置输出',name:'名称',format:'格式',saveTo:'保存到',more:'更多选项',output:'输出',location:'位置',localFolder:'本地文件夹',chooseSource:'选择源文件',chooseDestination:'选择新的输出位置',
  jsonl:'JSONL 词典清单',resourceManifest:'JSONL 资源清单',archive:'MDict v2 文件',converterSource:'词典来源',sourceHint:'源文件保留在你的电脑上。',noSource:'请选择文件以开始。',outputHint:'配置词典时，输出详情会随之更新。',
  mdx:'MDict v2 词典',mdd:'MDict 资源文件',txt:'词典文本',jsonlOutput:'JSONL 词条',folder:'提取的资源',duplicate:'保留重复词条',noClobber:'不覆盖已有输出',background:'后台处理',local:'你的文件，你的电脑。',
  selectConverter:'选择转换器',configureConverter:'配置转换',database:'数据库',morphology:'词形处理',later:'计划中',laterText:'此工作区将在后续集成阶段加入。',inputDetails:'源文件路径',sourceNote:"使用 UTF-8 词典 TXT 或 JSONL 清单构建。转换器输出 TXT。",
  profile:'构建配置',bounded:'有界 · 10 万条',block:'分块暂存 · 25 万条',connection:'已连接本地运行时',notConnected:'连接本地运行时',newIndex:'选择新的索引位置',records:'词条',sourceMode:'HTML 源码',entryDetails:'记录详情',currentJob:'当前任务',files:'文件',noOutput:'尚未选择输出',sourceType:'来源类型',receipt:'已验证的发布结果',
};
const ar:Labels={
  workspace:'مساحة العمل',data:'البيانات واللغة',inspect:'الفحص',personal:'مساحة عمل شخصية',buildTitle:'إنشاء قاموس',extractTitle:'استخراج قاموس',convertTitle:'تحويل المصدر',
  buildLead:'من ملفات المصدر إلى قاموس يستحق الرجوع إليه.',extractLead:'أعد المداخل والموارد إلى مساحة عملك.',convertersLead:'نقطة بداية مخصصة لكل صيغة مصدر.',toolsLead:'افحص المعنى والتنسيق والتفاصيل.',jobsLead:'يستمر عملك في الخلفية.',
  source:'المصدر',stepOne:'٠١ / اختيار المدخلات',dictionary:'القاموس',stepTwo:'٠٢ / إعداد المخرجات',name:'الاسم',format:'الصيغة',saveTo:'حفظ في',more:'خيارات إضافية',output:'المخرجات',location:'الموقع',localFolder:'مجلد محلي',chooseSource:'اختر ملف المصدر',chooseDestination:'اختر موقع مخرجات جديدًا',
  jsonl:'قائمة قاموس JSONL',resourceManifest:'قائمة موارد JSONL',archive:'ملف MDict v2',converterSource:'مصدر القاموس',sourceHint:'يبقى ملف المصدر على جهازك.',noSource:'اختر ملفًا للبدء.',outputHint:'تتحدث تفاصيل المخرجات أثناء إعداد القاموس.',
  mdx:'قاموس MDict v2',mdd:'ملف موارد MDict',txt:'نص القاموس',jsonlOutput:'مداخل JSONL',folder:'الموارد المستخرجة',duplicate:'حفظ المداخل المكررة',noClobber:'عدم استبدال المخرجات الموجودة',background:'العمل في الخلفية',local:'ملفاتك، على جهازك.',
  selectConverter:'اختر محوّلًا',configureConverter:'إعداد التحويل',database:'قاعدة البيانات',morphology:'الصرف',later:'مخطط',laterText:'ستُضاف هذه المساحة في مرحلة تكامل لاحقة.',inputDetails:'مسار المصدر',sourceNote:"أنشئ القاموس من TXT بترميز UTF-8 أو قائمة JSONL. تنتج المحوّلات ملفات TXT.",
  profile:'إعداد الإنشاء',bounded:'محدود · ١٠٠ ألف مدخل',block:'تجميع كتلي · ٢٥٠ ألف مدخل',connection:'متصل بالتشغيل المحلي',notConnected:'جارٍ الاتصال بالتشغيل المحلي',newIndex:'اختر موقع فهرس جديدًا',records:'المداخل',sourceMode:'مصدر HTML',entryDetails:'تفاصيل السجل',currentJob:'المهمة الحالية',files:'الملفات',noOutput:'لم تُحدد المخرجات',sourceType:'نوع المصدر',receipt:'نتيجة نشر متحقق منها',
};
export type StudioLabel=keyof Labels;
export const studioLabel=(locale:Locale,key:StudioLabel):string=>({en,zh,ar})[locale][key];
