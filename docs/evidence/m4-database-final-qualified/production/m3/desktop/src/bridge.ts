import { invoke } from '@tauri-apps/api/core';

export type Encoding = 'utf8' | 'utf16';
export type Policy = 'raw_exact' | 'header_ascii_v1';
export type Converter = 'cc_cedict' | 'moe_mini' | 'moe_idioms' | 'moe_concise' | 'moe_revised' | 'moe_revised_wfg';
export interface Metadata { title: string; description: string; stylesheet: string; extra: Record<string, string> }
type DictionaryRequest =
  | { operation: 'pack_mdx'; source: string; destination: string; encoding: Encoding; metadata: Metadata }
  | { operation: 'pack_mdd'; source: string; resource_root: string; destination: string; metadata: Metadata }
  | { operation: 'export_txt' | 'export_jsonl'; source: string; destination: string };
export type TxtProfile = 'canonical_v1' | 'legacy_body_span_v1';
export interface DatabaseRow {rowid:string;key:string;text:string}
export interface DatabasePage {source_sha256:string;total:number;offset:number;next_offset:number|null;rows:DatabaseRow[];dictionary_metadata?:Record<string,string>|null}
export interface DatabaseQuery {query:string|null;prefix:boolean;wildcard?:boolean;definition?:boolean;matching?:'literal'|'unicode16_lower';offset:number;limit:number}
export interface DatabaseReaderSnapshot {reader_id:string|null;state:string;job_id:string|null;job_state:string;result_available:boolean;error:Failure|null}
export type NativeRequest =
  | {kind:'database_page';request:{source:string;query:string|null;prefix?:boolean;offset:number;limit:number;expected_source_sha256:string|null}}
  | {kind:'database';request: {operation:'db_add_entry';source:string;destination:string;expected_source_sha256:string;key:string;text:string} | {operation:'db_delete_entry';source:string;destination:string;expected_source_sha256:string;rowid:string} | {operation:'db_edit_entry';source:string;destination:string;expected_source_sha256:string;rowid:string;text:string;key?:string} | {operation:'db_edit_metadata';source:string;destination:string;expected_source_sha256:string;edits:{title?:string;description?:string;stylesheet?:string}} | {operation:'txt_to_db';source:string;destination:string;profile:TxtProfile} | {operation:'db_to_txt'|'jsonl_to_db'|'db_to_jsonl'|'mdx_to_db'|'db_to_mdx';source:string;destination:string}}
  | { kind:'python_plugin'; request:{python:string; plugin:string; class_name:string; source:string; destination:string; trusted:boolean} }
  | { kind: 'metadata'; request: { source: string; destination: string; kind: 'mdx'|'mdd'; edits: {title?:string; description?:string; stylesheet?:string} } }
  | { kind: 'large_export'; request: { source: string; destination: string; format: 'txt'|'jsonl' } }
  | { kind: 'folder_packing'; request: { resource_root: string; destination: string; metadata: Metadata } }
  | { kind: 'txt_packing'; request: { source: string; destination: string; encoding: Encoding; metadata: Metadata; profile: TxtProfile; packing: 'bounded' | 'block' } }
  | { kind: 'dictionary'; request: DictionaryRequest }
  | { kind: 'cc_packing'; request: { source: string; destination: string; encoding: Encoding; metadata: Metadata } }
  | { kind: 'extraction'; request: { source: string; destination: string } }
  | { kind: 'index'; request: { source: string; destination: string; kind: 'mdx' | 'mdd'; policy: Policy } }
  | { kind: 'conversion'; request: { profile: 'cc' | 'concise' | 'small_moe' | 'grouped_moe'; request: { input: string; destination: string; converter: Converter; worksheet: string | null } } };
export type Command =
  | {action:'database_open';source:string}
  | {action:'database_query';reader_id:string;request:DatabaseQuery}
  | {action:'database_poll'}
  | {action:'database_cancel'|'database_take'|'database_forget';job_id:string}
  | {action:'database_close';reader_id:string}
  | { action: 'capabilities' | 'poll' }
  | { action: 'submit'; request: NativeRequest }
  | { action: 'cancel' | 'take' | 'forget'; job_id: string }
  | { action: 'open_reader'; request: { source: string; artifact: string; kind: 'mdx' | 'mdd'; policy: Policy } }
  | { action:'export_stylesheet'; session_id:string; destination:string }
  | { action: 'resolve'; session_id: string; request: {query:string; ordinal:number} }
  | { action: 'page'; session_id: string; request: { query: string; offset: number; limit: number } }
  | { action: 'session_take' | 'session_cancel' | 'session_forget'; session_id: string; job_id: string }
  | { action: 'close_reader' | 'release_reader' | 'reader_details'; session_id: string };
export interface Failure { code: string; message: string; detail?: string; publication_uncertain?: boolean; limit?: { name: string; value: number; max: number } }
export interface Snapshot {
  job_id: string; revision: number; state: string; operation?: string; cancel_requested: boolean;
  result_available: boolean; error: Failure | null;
  latest_progress: { stage: string; phase: string; completed: number; total: number } | null;
}
export interface Poll {
  jobs: Snapshot[];
  sessions: { session: { session_id: string; state: string; error: Failure | null }; jobs: Snapshot[] }[];
  admission: { active_operations: number; max_operations: number; reserved_memory_bytes: number; memory_cap: number };
}
export interface Row { ordinal: number; key: string; text?: string; bytes?: number[] }
export interface Page { rows: Row[]; total: number; offset: number; next_offset: number | null; basis: string }
export interface ReaderDetails { attributes: Record<string,string>; source_sha256: string; source_bytes: number; manifest: Record<string,unknown> }
export interface RedirectHop {ordinal:number; key:string; target:string}
export interface Resolution {row:Row; chain:RedirectHop[]}
export interface Resolved {source_ordinal:number; source_key:string; results:Resolution[]; visits:number}
export interface SessionReply { operation: 'opened' | 'page' | 'resolved'; value: Page | Resolved | Record<string, unknown> }
export async function call<T>(command: Command): Promise<T> {
  const request = JSON.stringify(command);
  if (new TextEncoder().encode(request).length > 65536) throw { code: 'invalid_input', message: 'Command exceeds 64 KiB' };
  return invoke<T>('studio_call', { request });
}
export function failure(error: unknown): Failure {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const e = error as Failure;
    return { code: typeof e.code === 'string' ? e.code : 'internal', message: String(e.message) };
  }
  return { code: 'internal', message: String(error) };
}
