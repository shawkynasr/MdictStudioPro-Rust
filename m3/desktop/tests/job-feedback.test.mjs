import test from 'node:test';
import assert from 'node:assert/strict';
import {jobFeedback,jobFeedbackLabel,jobFailureMessage,jobFailureHint,pythonSelectionIssue} from '../src/job-feedback.ts';
const job=(state,extra={})=>({state,cancel_requested:false,error:null,...extra});
test('job states have distinct presentation and late cancellation preserves success',()=>{
  assert.deepEqual(jobFeedback(job('queued')),{label:'queued',tone:'active'});
  assert.deepEqual(jobFeedback(job('running')),{label:'running',tone:'active'});
  assert.deepEqual(jobFeedback(job('failed')),{label:'failed',tone:'danger'});
  assert.deepEqual(jobFeedback(job('cancelled')),{label:'cancelled',tone:'muted'});
  assert.deepEqual(jobFeedback(job('running',{cancel_requested:true})),{label:'cancelling',tone:'warning'});
  assert.deepEqual(jobFeedback(job('succeeded',{cancel_requested:true})),{label:'succeeded',tone:'success'});
  assert.deepEqual(jobFeedback(job('future_state')),{label:'unknown',tone:'muted'});
});
test('uncertain publication stays visible regardless of state and suppresses retry hints',()=>{
  for(const state of ['failed','cancelled','succeeded']) {
    const error={code:'destination_exists',message:'uncertain',publication_uncertain:true};
    assert.equal(jobFeedback(job(state,{error})).tone,'warning');
    assert.equal(jobFailureHint(error,'python_converter'),'uncertain');
  }
});
test('display removes only repeated leading codes while the original failure is unchanged',()=>{
  const error={code:'cancelled',message:'cancelled: cancelled: Stopped before publication',detail:'database',publication_uncertain:false};
  const before=JSON.stringify(error);
  assert.equal(jobFailureMessage(error,'cancelled'),'Stopped before publication');
  assert.equal(jobFailureMessage({...error,code:'io',message:'io: Permission denied (os error 13)'},'failed'),'io: Permission denied (os error 13)');
  assert.equal(jobFailureMessage({code:'io',message:'native detail: io: later'},'failed'),'io: native detail: io: later');
  assert.equal(JSON.stringify(error),before);
});
test('typed hints distinguish permissions, existing outputs and limits without parsing arbitrary errors',()=>{
  assert.equal(jobFailureHint({code:'io',message:'Permission denied (os error 13)'},'python_converter'),'pythonPermission');
  assert.equal(jobFailureHint({code:'io',message:'Permission denied'},'pack_txt_mdx'),'permission');
  assert.equal(jobFailureHint({code:'engine',message:'Permission denied'},'python_converter'),null);
  assert.equal(jobFailureHint({code:'io',message:'File not found'},'python_converter'),null);
  assert.equal(jobFailureHint({code:'destination_exists',message:'exists'}),'destination');
  assert.equal(jobFailureHint({code:'limit_exceeded',message:'output bytes'}),'limit');
});
test('identical interpreter/plugin selection is caught, while normal interpreter and custom launchers stay valid',()=>{
  assert.equal(pythonSelectionIssue('/a/plugin.py','/a/plugin.py'),'pythonSelection');
  assert.equal(pythonSelectionIssue('/a/.venv/bin/python','/a/plugin.py'),null);
  assert.equal(pythonSelectionIssue('/a/launcher.py','/a/plugin.py'),null);
  assert.equal(pythonSelectionIssue('',''),null);
});
test('all feedback labels and hints have English, Chinese and Arabic strings',()=>{
  const keys=['queued','running','succeeded','failed','cancelled','cancelling','unknown','details','pythonSelection','pythonPermission','permission','destination','limit','uncertain'];
  for(const locale of ['en','zh','ar'])for(const key of keys)assert.ok(jobFeedbackLabel(locale,key)?.length>0);
});

test('decoded export limits give an actionable profile hint without widening other operations',()=>{
  const error={code:'limit_exceeded',message:'decoded limit',limit:{name:'decoded_text_bytes',value:100663297,max:100663296}};
  assert.equal(jobFailureHint(error,'export_large_txt'),'exportLimit');
  assert.equal(jobFailureHint({...error,limit:{...error.limit,max:268435456}},'export_large_txt'),'limit');
  assert.equal(jobFailureHint(error,'mdx_to_db'),'limit');
  assert.equal(jobFailureHint({code:'limit_exceeded',message:'Aggregate decoded key/payload cap exceeded'},'export_txt'),'exportLimit');
  assert.equal(jobFailureHint({...error,publication_uncertain:true},'export_large_txt'),'uncertain');
  for(const locale of ['en','zh','ar'])assert.ok(jobFeedbackLabel(locale,'exportLimit'));
});
test('destination display omits fictitious line zero without changing diagnostics',()=>{
  const error={code:'destination_exists',message:'Line 0: Destination exists'};
  assert.equal(jobFailureMessage(error,'failed'),'destination_exists: Destination exists');
  assert.equal(error.message,'Line 0: Destination exists');
  assert.equal(jobFailureHint(error,'pack_txt_mdx'),'rebuildDestination');
  assert.equal(jobFailureHint(error,'python_converter'),'destination');
  for(const locale of ['en','zh','ar'])assert.ok(jobFeedbackLabel(locale,'rebuildDestination'));
});
