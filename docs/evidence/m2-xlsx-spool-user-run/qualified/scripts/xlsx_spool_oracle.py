"""Streaming independent row oracle using the captured openpyxl normalizer."""
import hashlib
import importlib.util
import struct
from pathlib import Path
from openpyxl import load_workbook
from m2_sizing import ROOT

class RowDigest:
    def __init__(self):self.h=hashlib.sha256();self.rows=self.pairs=self.keys=self.values=0
    def add(self,row):
        self.h.update(struct.pack('<QQ',self.rows,len(row)))
        for key,value in sorted(row.items()):
            key=key.encode('utf-8');value=value.encode('utf-8')
            self.h.update(struct.pack('<Q',len(key)));self.h.update(key);self.h.update(struct.pack('<Q',len(value)));self.h.update(value)
            self.keys+=len(key);self.values+=len(value)
        self.rows+=1;self.pairs+=len(row)
    def finish(self):return {'rows':self.rows,'pairs':self.pairs,'key_bytes':self.keys,'value_bytes':self.values,'framed_rows_sha256':self.h.hexdigest()}
def inspect(source,worksheet=None):
    spec=importlib.util.spec_from_file_location('captured_row_normalizer',ROOT/'baseline/legacy/excel_utils.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    workbook=load_workbook(source,read_only=True,data_only=True)
    try:
        sheet=workbook[worksheet] if worksheet else workbook.active
        iterator=sheet.iter_rows(values_only=True)
        first=next(iterator,None)
        if first is None:return {'worksheet':sheet.title,'headers':[],'scanned_data_rows':0,'skipped_blank_rows':0,'normalized_charge_bytes':0,'row_digest':RowDigest().finish()}
        headers=[str(h).strip() if h is not None else f'col_{i}' for i,h in enumerate(first)]
        digest=RowDigest();scanned=skipped=0;charge=sum(len(h.encode()) for h in headers)
        for raw in iterator:
            scanned+=1
            if raw is None or all(value is None for value in raw):skipped+=1;continue
            row={}
            for i,header in enumerate(headers):
                value=module._cell_to_str(raw[i] if i<len(raw) else None);charge+=len(header.encode())+len(value.encode());row[header]=value
            digest.add(row)
        return {'worksheet':sheet.title,'headers':headers,'scanned_data_rows':scanned,'skipped_blank_rows':skipped,'normalized_charge_bytes':charge,'row_digest':digest.finish()}
    finally:workbook.close()
