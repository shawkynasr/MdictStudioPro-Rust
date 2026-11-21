import type {Command,DatabasePage,DatabaseQuery,DatabaseReaderSnapshot,Failure} from './bridge';

/** Serializes ownership changes and drains every accepted job, including stale opens. */
export class DatabaseBrowser {
  private send:(command:Command)=>Promise<unknown>;
  private pause:()=>Promise<void>;
  private tail:Promise<unknown>=Promise.resolve();
  private epoch=0;
  private cancelledEpoch=-1;
  private reader='';
  private source='';
  private job='';
  constructor(send:(command:Command)=>Promise<unknown>,pause=()=>new Promise<void>(r=>setTimeout(r,80))) {
    this.send=send;this.pause=pause;
  }
  private serial<T>(task:()=>Promise<T>):Promise<T> {
    const next=this.tail.then(task);this.tail=next.catch(()=>{});return next;
  }
  invalidate(close=false):Promise<void> {
    this.epoch++;
    if(this.job)void this.send({action:'database_cancel',job_id:this.job}).catch(()=>{});
    return close?this.serial(()=>this.closeOwned()):Promise.resolve();
  }
  async cancel():Promise<void> {
    this.cancelledEpoch=this.epoch;
    if(this.job)await this.send({action:'database_cancel',job_id:this.job});
  }
  close():Promise<void> {return this.invalidate(true);}
  private async closeOwned():Promise<void> {
    if(!this.reader)return;
    const id=this.reader;
    try {await this.send({action:'database_close',reader_id:id});}
    catch(e) {if((e as Failure)?.code!=='not_found')throw e;}
    for(;;) {
      const state=await this.send({action:'database_poll'}) as DatabaseReaderSnapshot;
      if(state.reader_id!==id || state.state==='closed')break;
      await this.pause();
    }
    this.reader='';this.source='';
  }
  private async run(command:Command,epoch:number,opening=false):Promise<{operation:string;value:unknown}|null> {
    const submitted=await this.send(command) as {reader_id?:string;job_id:string};
    if(opening)this.reader=submitted.reader_id!;
    this.job=submitted.job_id;
    try {
      if(epoch!==this.epoch || this.cancelledEpoch===epoch)await this.send({action:'database_cancel',job_id:this.job});
      for(;;) {
        const state=await this.send({action:'database_poll'}) as DatabaseReaderSnapshot;
        if(state.job_id!==this.job)throw {code:'closed',message:'Database reader closed during the request'};
        if(state.job_state==='queued'||state.job_state==='running'){await this.pause();continue;}
        const result=state.result_available?await this.send({action:'database_take',job_id:this.job}) as {operation:string;value:unknown}:null;
        await this.send({action:'database_forget',job_id:this.job});
        if(!state.reader_id){this.reader='';this.source='';}
        if(state.error)throw state.error;
        return result;
      }
    } finally {this.job='';}
  }
  load(source:string,query:DatabaseQuery):Promise<DatabasePage|null> {
    const epoch=++this.epoch;
    if(this.job)void this.send({action:'database_cancel',job_id:this.job}).catch(()=>{});
    return this.serial(async()=>{
      if(epoch!==this.epoch)return null;
      try {
        if(this.reader && this.source!==source)await this.closeOwned();
        if(epoch!==this.epoch)return null;
        if(!this.reader){
          await this.run({action:'database_open',source},epoch,true);
          if(epoch!==this.epoch){await this.closeOwned();return null;}
          this.source=source;
        }
        const reply=await this.run({action:'database_query',reader_id:this.reader,request:query},epoch);
        return epoch===this.epoch && reply?.operation==='page'?reply.value as DatabasePage:null;
      } catch(e) {if(epoch!==this.epoch)return null;throw e;}
    });
  }
}
