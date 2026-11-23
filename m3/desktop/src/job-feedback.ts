import type {Locale} from './i18n';
import type {Failure,Snapshot} from './bridge';
const en={queued:'Queued',running:'Running',succeeded:'Succeeded',failed:'Failed',cancelled:'Cancelled',cancelling:'Cancellation requested',unknown:'Unknown state',details:'Error details',pythonSelection:'Python executable and Plugin .py file point to the same file. Select your Python interpreter (for example .venv/bin/python) in Python executable.',pythonPermission:'Check that Python executable points to an executable Python interpreter. Also check access to the plugin, input and output parent folder.',permission:'Check read access to the input and write access to the output parent folder.',destination:'The output already exists. Choose a new file or folder name; the existing destination was kept.',rebuildDestination:'The output already exists. Return to Build and choose a new name, such as dictionary-rebuilt.mdx. The original file was kept.',exportLimit:'This dictionary exceeds the selected decoded-text limit. In Extract, choose Extended (256 MiB) and a new output path. Compressed MDX size is not the decoded text size. Build and SQLite limits are separate.',packingLimit:'This TXT exceeds the selected build profile. In Build, choose Extended TXT (256 MiB decoded text; 512 MiB input) and a new MDX name. Other per-entry and resource limits still apply.',limit:'An operation limit was reached. Check error details; reduce the input or workload, or choose another supported profile.',uncertain:'Publication outcome is uncertain. Inspect the destination before retrying.'};
const zh:Record<keyof typeof en,string>={queued:'排队中',running:'运行中',succeeded:'已成功',failed:'已失败',cancelled:'已取消',cancelling:'已请求取消',unknown:'未知状态',details:'错误详情',pythonSelection:'Python 可执行文件与插件文件指向同一个文件。请在 Python 可执行文件中选择解释器（例如 .venv/bin/python）。',pythonPermission:'请确认 Python 路径指向可执行的解释器，并检查插件、输入及输出父目录的访问权限。',permission:'请检查输入的读取权限及输出父目录的写入权限。',destination:'输出位置已存在。请改用新的文件名或文件夹名；已有输出已保留。',rebuildDestination:'输出位置已存在。请返回「构建」，改用新名称（例如 dictionary-rebuilt.mdx）。原文件已保留。',exportLimit:'此词典解压后的文本超出所选上限。请在「提取」中选择「扩展（256 MiB）」并使用新的输出路径。MDX 压缩大小不等于解码文本大小，构建及 SQLite 限制另计。',packingLimit:'此 TXT 超出所选构建配置。请在「构建」中选择「扩展 TXT」（256 MiB 解码文本、512 MiB 输入）并使用新的 MDX 文件名。单条释义及其他资源限制仍然适用。',limit:'操作达到限制。请查看错误详情，减少输入或工作量，或选择其他支持的配置。',uncertain:'发布结果不确定。重试前请检查输出位置。'};
const ar:Record<keyof typeof en,string>={queued:'في الانتظار',running:'قيد التشغيل',succeeded:'نجحت',failed:'فشلت',cancelled:'أُلغيت',cancelling:'طُلب الإلغاء',unknown:'حالة غير معروفة',details:'تفاصيل الخطأ',pythonSelection:'يشير حقل Python وملف الإضافة إلى الملف نفسه. اختر مفسّر Python (مثل .venv/bin/python) في حقل الملف التنفيذي.',pythonPermission:'تحقق من أن مسار Python يشير إلى مفسّر قابل للتنفيذ، ومن صلاحيات الوصول إلى الإضافة والمدخلات ومجلد الإخراج.',permission:'تحقق من صلاحية قراءة المدخلات والكتابة في المجلد الأب للإخراج.',destination:'الإخراج موجود. اختر اسم ملف أو مجلد جديداً؛ حُفظت الوجهة الموجودة.',rebuildDestination:'الإخراج موجود. ارجع إلى الإنشاء واختر اسماً جديداً مثل dictionary-rebuilt.mdx. حُفظ الملف الأصلي.',exportLimit:'يتجاوز نص القاموس بعد فك الضغط الحد المختار. اختر التصدير الموسّع (256 MiB) ومسار إخراج جديداً في الاستخراج. للإنشاء وSQLite حدود منفصلة.',packingLimit:'يتجاوز TXT إعداد الإنشاء المختار. اختر TXT الموسّع (نص مفكوك 256 MiB ومدخل 512 MiB) واسم MDX جديدًا. تبقى حدود التعريف الواحد والموارد الأخرى سارية.',limit:'بلغت العملية أحد الحدود. راجع تفاصيل الخطأ وقلل المدخلات أو حجم العمل، أو اختر إعداداً آخر مدعوماً.',uncertain:'نتيجة النشر غير مؤكدة. افحص الوجهة قبل إعادة المحاولة.'};
export type JobFeedbackLabel=keyof typeof en;
export const jobFeedbackLabel=(locale:Locale,key:JobFeedbackLabel)=>(locale==='zh'?zh:locale==='ar'?ar:en)[key];
export type JobTone='active'|'success'|'danger'|'muted'|'warning';
export function jobFeedback(job:Pick<Snapshot,'state'|'cancel_requested'|'error'>):{label:JobFeedbackLabel;tone:JobTone} {
  if(job.error?.publication_uncertain)return {label:job.state==='failed'?'failed':'uncertain',tone:'warning'};
  if(job.state==='succeeded')return {label:'succeeded',tone:'success'};
  if(job.state==='failed')return {label:'failed',tone:'danger'};
  if(job.state==='cancelled')return {label:'cancelled',tone:'muted'};
  if(job.state==='queued'||job.state==='running')return {label:job.cancel_requested?'cancelling':job.state,tone:job.cancel_requested?'warning':'active'};
  return {label:'unknown',tone:'muted'};
}
export function jobFailureMessage(error:Failure,state:string):string {
  const prefix=error.code+':';let message=error.message;
  while(error.code&&message.startsWith(prefix))message=message.slice(prefix.length).trimStart();
  if(error.code==='destination_exists')message=message.replace(/^Line 0:\s*/, '');
  if(!message)message=error.message||error.code;
  return !error.code||(state==='cancelled'&&error.code==='cancelled')?message:error.code+': '+message;
}
export function jobFailureHint(error:Failure,operation?:string):JobFeedbackLabel|null {
  if(error.publication_uncertain)return 'uncertain';
  if(error.code==='destination_exists')return operation?.startsWith('pack_')?'rebuildDestination':'destination';
  if(error.code==='limit_exceeded') {
    if(operation==='pack_txt_mdx' && error.limit && ['txt_input_bytes','decoded_text_bytes','prepared_jsonl_bytes'].includes(error.limit.name) && error.limit.max<=128*1024*1024)return 'packingLimit';
    if(operation?.startsWith('export_') && (error.limit?.name==='decoded_text_bytes' && error.limit.max<=96*1024*1024 || error.message==='Aggregate decoded key/payload cap exceeded'))return 'exportLimit';
    return 'limit';
  }
  if(error.code==='io'&&(/permission denied|os error 13/i.test(error.message)))return operation==='python_converter'?'pythonPermission':'permission';
  return null;
}
export function pythonSelectionIssue(python:string,plugin:string):JobFeedbackLabel|null {
  return python&&plugin&&python===plugin?'pythonSelection':null;
}
