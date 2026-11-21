import { invoke } from '@tauri-apps/api/core';

export type Encoding = 'utf8' | 'utf16';
export type Policy = 'raw_exact' | 'header_ascii_v1';
export type Converter = 'cc_cedict' | 'moe_mini' | 'moe_idioms' | 'moe_concise' | 'moe_revised' | 'moe_revised_wfg';
export interface Metadata { title: string; description: string; stylesheet: string; extra: Record<string, string> }
type DictionaryRequest =
  | { operation: 'pack_mdx'; source: string; destination: string; encoding: Encoding; metadata: Metadata }
  | { operation: 'pack_mdd'; source: string; resource_root: string; destination: string; metadata: Metadata }
  | { operation: 'export_txt' | 'export_jsonl'; source: string; destination: string };
export type NativeRequest =
  | { kind: 'dictionary'; request: DictionaryRequest }
  | { kind: 'cc_packing'; request: { source: string; destination: string; encoding: Encoding; metadata: Metadata } }
  | { kind: 'extraction'; request: { source: string; destination: string } }
  | { kind: 'index'; request: { source: string; destination: string; kind: 'mdx'; policy: Policy } }
  | { kind: 'conversion'; request: { profile: 'cc' | 'concise' | 'small_moe' | 'grouped_moe'; request: { input: string; destination: string; converter: Converter; worksheet: string | null } } };
export type Command =
  | { action: 'capabilities' | 'poll' }
  | { action: 'submit'; request: NativeRequest }
  | { action: 'cancel' | 'take' | 'forget'; job_id: string }
  | { action: 'open_reader'; request: { source: string; artifact: string; kind: 'mdx'; policy: Policy } }
  | { action: 'page'; session_id: string; request: { query: string; offset: number; limit: number } }
  | { action: 'session_take' | 'session_cancel' | 'session_forget'; session_id: string; job_id: string }
  | { action: 'close_reader' | 'release_reader'; session_id: string };
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
export interface SessionReply { operation: 'opened' | 'page'; value: Page | Record<string, unknown> }
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
