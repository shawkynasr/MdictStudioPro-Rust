//! Deterministic, offline-only large-file and fault fixtures.
use mdictlib::{LegacySort,MdxBuilder,MddBuilder,MdxFile,MddFile,WriteOptions};
use studio_engine_probe::{Result,stage_directory};
use serde_json::{json,Value};
use std::{fs::{self,File},io::{self,Write},path::Path,time::Duration};

fn parameters(path:&Path)->Result<(usize,usize,usize,usize)> {
    let v:Value=serde_json::from_slice(&fs::read(path)?)?;
    let get=|name:&str|->Result<usize>{Ok(usize::try_from(v[name].as_u64().ok_or("Invalid stress parameter")?)?)};
    let (entries,width,resources,size)=(get("entries")?,get("body_bytes")?,get("resources")?,get("resource_bytes")?);
    if entries==0 || resources==0 || entries>100_000 || width<64 || width>4096 || resources>512 || size<64 || size>1024*1024 {
        return Err("Stress preset parameter range exceeded".into());
    }
    let text_volume=entries.checked_mul(width).ok_or("Stress size overflow")?;
    let resource_volume=resources.checked_mul(size).ok_or("Stress size overflow")?;
    if text_volume>128*1024*1024 || resource_volume>32*1024*1024 {
        return Err("Stress decoded-volume budget exceeded".into());
    }
    Ok((entries,width,resources,size))
}

fn data(index:usize,size:usize,text:bool)->Vec<u8> {
    let mut state=(index as u32 ^ 0xa341316c).wrapping_add(1);
    let alphabet=b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    (0..size).map(|_|{
        state^=state<<13;state^=state>>17;state^=state<<5;
        if text {alphabet[(state&63) as usize]} else {(state&255) as u8}
    }).collect()
}

fn options()->WriteOptions {
    WriteOptions::new().with_legacy_sort(LegacySort::PreserveInput)
        .with_key_block_target_bytes(256).with_record_block_target_bytes(4096)
}

pub fn build(spec:&Path,out:&Path)->Result<Value> {
    let (entries,width,resources,size)=parameters(spec)?;
    stage_directory(out,|stage|{
        let mut mdx=MdxBuilder::with_options(options());
        mdx.header_attribute("Title","Offline stress fixture - do not import")?;
        mdx.header_attribute("Format","Html")?;
        mdx.header_attribute("Compact","No")?;
        for i in 0..entries {
            let bytes=data(i,width,true);let body=std::str::from_utf8(&bytes)?;
            mdx.add_entry(&format!("word-{i:08}"),body)?;
        }
        let mdx=mdx.finish(File::create(stage.join("stress.mdx"))?)?;
        let mut mdd=MddBuilder::with_options(options());
        mdd.header_attribute("Title","Offline stress binary resources")?;
        for i in 0..resources {mdd.add_resource(&format!("\\data\\resource-{i:08}.bin"),&data(i,size,false))?;}
        let mdd=mdd.finish(File::create(stage.join("stress.mdd"))?)?;
        Ok(json!({"status":"stress_files_built_not_native_qualified","entries":entries,"resources":resources,
            "mdx_key_blocks":mdx.key_blocks,"mdx_record_blocks":mdx.record_blocks,
            "mdd_key_blocks":mdd.key_blocks,"mdd_record_blocks":mdd.record_blocks}))
    })
}

pub fn verify(spec:&Path,out:&Path)->Result<Value> {
    let (entries,width,resources,size)=parameters(spec)?;
    let file=MdxFile::open(out.join("stress.mdx"))?;let mut count=0;
    for key in file.keys() {
        let key=key?;let entry=file.entry_at(key.ordinal())?.ok_or("Missing stress record")?;
        if key.key()!=format!("word-{count:08}") || entry.text().as_bytes()!=data(count,width,true) {
            return Err("Stress text/order differs from generated specification".into());
        }
        count+=1;
    }
    if count!=entries {return Err("Stress entry count differs".into());}
    for i in [0,entries/2,entries-1] {
        let found=file.locate(&format!("word-{i:08}"))?.ok_or("Stress lookup missing")?;
        let mut count=0;
        for ordinal in found.iter() {
            if file.entry_at(ordinal)?.ok_or("Missing lookup ordinal")?.text().as_bytes()!=data(i,width,true) {return Err("Stress lookup payload differs".into());}
            count+=1;
        }
        if count!=1 {return Err("Stress lookup multiplicity differs".into());}
    }
    drop(file);
    let file=MddFile::open(out.join("stress.mdd"))?;let mut count=0;
    for key in file.keys() {
        let key=key?;let value=file.resource_at(key.ordinal())?.ok_or("Missing stress resource")?;
        if key.key()!=format!("\\data\\resource-{count:08}.bin") || value.bytes()!=data(count,size,false) {
            return Err("Stress resource/order differs".into());
        }
        count+=1;
    }
    if count!=resources {return Err("Stress resource count differs".into());}
    for i in [0,resources/2,resources-1] {
        let found=file.locate(&format!("\\data\\resource-{i:08}.bin"))?.ok_or("Stress resource lookup missing")?;
        let mut count=0;
        for ordinal in found.iter() {
            if file.resource_at(ordinal)?.ok_or("Missing resource lookup ordinal")?.bytes()!=data(i,size,false) {return Err("Stress resource lookup bytes differ".into());}
            count+=1;
        }
        if count!=1 {return Err("Stress resource lookup multiplicity differs".into());}
    }
    Ok(json!({"status":"stress_all_generated_payloads_verified","entries":entries,"resources":resources,"sampled_exact_lookups":6}))
}

pub fn inspect(path:&Path)->Result<Value> {
    let file=MdxFile::open(path)?;let mut count=0;
    for key in file.keys() {let key=key?;file.entry_at(key.ordinal())?.ok_or("Missing input record")?;count+=1;}
    Ok(json!({"records":count}))
}

struct FailWriter { inner:File, remaining:usize }
impl Write for FailWriter {
    fn write(&mut self,buf:&[u8])->io::Result<usize> {
        if self.remaining==0 {return Err(io::Error::new(io::ErrorKind::Other,"injected write failure"));}
        let amount=buf.len().min(self.remaining);let n=self.inner.write(&buf[..amount])?;self.remaining-=n;Ok(n)
    }
    fn flush(&mut self)->io::Result<()> {self.inner.flush()}
}

pub fn fail_write(out:&Path)->Result<Value> {
    stage_directory(out,|stage|{
        let mut builder=MdxBuilder::with_options(options());
        for i in 0..16 {builder.add_entry(&format!("word-{i:08}"),std::str::from_utf8(&data(i,512,true))?)?;}
        builder.finish(FailWriter{inner:File::create(stage.join("partial.mdx"))?,remaining:1024})?;
        Err("Injected writer unexpectedly succeeded".into())
    })
}

pub fn hold(out:&Path,ready:&Path)->Result<Value> {
    stage_directory(out,|stage|{
        fs::write(stage.join("partial-output"),b"unpublished staging data")?;
        fs::write(ready,b"ready")?;
        loop { std::thread::sleep(Duration::from_millis(100)); }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn small_stress_roundtrip_and_write_failure_leave_no_published_failure() {
        let temp=tempfile::tempdir().unwrap();let spec=temp.path().join("spec.json");
        fs::write(&spec,br#"{"entries":128,"body_bytes":128,"resources":8,"resource_bytes":256}"#).unwrap();
        let out=temp.path().join("files");build(&spec,&out).unwrap();verify(&spec,&out).unwrap();
        let failed=temp.path().join("failed");assert!(fail_write(&failed).is_err());assert!(!failed.exists());
        let recovered=temp.path().join("recovered");build(&spec,&recovered).unwrap();verify(&spec,&recovered).unwrap();
    }
}
