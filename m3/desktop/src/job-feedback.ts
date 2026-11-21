import type {Locale} from './i18n';
import type {Failure,Snapshot} from './bridge';
const en={queued:'Queued',running:'Running',succeeded:'Succeeded',failed:'Failed',cancelled:'Cancelled',cancelling:'Cancellation requested',unknown:'Unknown state',details:'Error details',pythonSelection:'Python executable and Plugin .py file point to the same file. Select your Python interpreter (for example .venv/bin/python) in Python executable.',pythonPermission:'Check that Python executable points to an executable Python interpreter. Also check access to the plugin, input and output parent folder.',permission:'Check read access to the input and write access to the output parent folder.',destination:'Choose a new output name or folder; the existing destination was kept.',limit:'An operation limit was reached. Check error details; reduce the input or workload, or choose another supported profile.',uncertain:'Publication outcome is uncertain. Inspect the destination before retrying.'};
const zh:Record<keyof typeof en,string>={queued:'排队中',running:'运行中',succeeded:'已成功',failed:'已失败',cancelled:'已取消',cancelling:'已请求取消',unknown:'未知状态',details:'错误详情',pythonSelection:'Python 可执行文件与插件文件指向同一个文件。请在 Python 可执行文件中选择解释器（例如 .venv/bin/python）。',pythonPermission:'请确认 Python 路径指向可执行的解释器，并检查插件、输入及输出父目录的访问权限。',permission:'请检查输入的读取权限及输出父目录的写入权限。',destination:'请选择新的输出名称或文件夹；已有输出已保留。',limit:'操作达到限制。请查看错误详情，减少输入或工作量，或选择其他支持的配置。',uncertain:'发布结果不确定。重试前请检查输出位置。'};
const ar:Record<keyof typeof en,string>={queued:'في الانتظار',running:'قيد التشغيل',succeeded:'نجحت',failed:'فشلت',cancelled:'أُلغيت',cancelling:'طُلب الإلغاء',unknown:'حالة غير معروفة',details:'تفاصيل الخطأ',pythonSelection:'يشير حقل Python وملف الإضافة إلى الملف نفسه. اختر مفسّر Python (مثل .venv/bin/python) في حقل الملف التنفيذي.',pythonPermission:'تحقق من أن مسار Python يشير إلى مفسّر قابل للتنفيذ، ومن صلاحيات الوصول إلى الإضافة والمدخلات ومجلد الإخراج.',permission:'تحقق من صلاحية قراءة المدخلات والكتابة في المجلد الأب للإخراج.',destination:'اختر اسماً أو مجلداً جديداً للإخراج؛ حُفظت الوجهة الموجودة.',limit:'بلغت العملية أحد الحدود. راجع تفاصيل الخطأ وقلل المدخلات أو حجم العمل، أو اختر إعداداً آخر مدعوماً.',uncertain:'نتيجة النشر غير مؤكدة. افحص الوجهة قبل إعادة المحاولة.'};
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
  if(!message)message=error.message||error.code;
  return !error.code||(state==='cancelled'&&error.code==='cancelled')?message:error.code+': '+message;
}
export function jobFailureHint(error:Failure,operation?:string):JobFeedbackLabel|null {
  if(error.publication_uncertain)return 'uncertain';
  if(error.code==='destination_exists')return 'destination';
  if(error.code==='limit_exceeded')return 'limit';
  if(error.code==='io'&&(/permission denied|os error 13/i.test(error.message)))return operation==='python_converter'?'pythonPermission':'permission';
  return null;
}
export function pythonSelectionIssue(python:string,plugin:string):JobFeedbackLabel|null {
  return python&&plugin&&python===plugin?'pythonSelection':null;
}
