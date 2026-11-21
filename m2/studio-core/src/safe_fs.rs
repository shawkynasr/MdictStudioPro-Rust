//! Descriptor-relative staged writes and platform no-replace publication.
//! No path-following fallback is used on unsupported platforms/filesystems.
use crate::{Error, ErrorCode, JobContext, Phase, Resource, Result};
use crate::resource_paths::PlannedPath;
use std::path::Path;

pub(crate) fn supported() -> Result<()> {
    if cfg!(any(target_os="macos", target_os="linux")) { Ok(()) }
    else { Err(Error::new(ErrorCode::UnsupportedPlatform,"Safe directory publication is implemented for macOS/Linux only")) }
}

#[cfg(unix)]
mod unix {
    use super::*;
    use std::{collections::BTreeSet, ffi::CString, fs::{File,OpenOptions}, io::{self,Write},
        os::{fd::{AsRawFd,FromRawFd},unix::{ffi::OsStrExt,fs::OpenOptionsExt}},path::PathBuf};

    fn component(value: &[u8]) -> Result<CString> {
        CString::new(value).map_err(|_|Error::new(ErrorCode::UnsafePath,"NUL in filesystem path"))
    }
    fn filesystem_error(error: io::Error) -> Error {
        if error.kind()==io::ErrorKind::AlreadyExists {
            Error::new(ErrorCode::PathCollision,"Target filesystem aliases distinct resource paths")
        } else { Error::from(error) }
    }

    pub(super) fn write(root: &Path, paths: &[PlannedPath], resources: &[Resource], job: &mut JobContext<'_>) -> Result<()> {
        let root = OpenOptions::new().read(true).custom_flags(libc::O_DIRECTORY|libc::O_NOFOLLOW|libc::O_CLOEXEC).open(root)?;
        let mut created: BTreeSet<PathBuf> = BTreeSet::new();
        for (index, (path, resource)) in paths.iter().zip(resources).enumerate() {
            job.checkpoint(Phase::Extracting,index,resources.len())?;
            let mut directory = root.try_clone()?;
            let mut prefix = PathBuf::new();
            for part in &path.parts[..path.parts.len()-1] {
                prefix.push(part); let name = component(part.as_bytes())?;
                if created.insert(prefix.clone()) {
                    // SAFETY: valid owned fd, NUL-terminated single component.
                    // A distinct logical prefix must be newly created; even an
                    // existing directory here is a filesystem alias or intrusion.
                    if unsafe { libc::mkdirat(directory.as_raw_fd(),name.as_ptr(),0o700) } != 0 {
                        return Err(filesystem_error(io::Error::last_os_error()));
                    }
                }
                // SAFETY: open relative to the owned directory handle, refuse
                // symlink components; returned fd is immediately owned by File.
                let fd = unsafe { libc::openat(directory.as_raw_fd(),name.as_ptr(),libc::O_RDONLY|libc::O_DIRECTORY|libc::O_NOFOLLOW|libc::O_CLOEXEC) };
                if fd < 0 { return Err(Error::from(io::Error::last_os_error())); }
                directory = unsafe { File::from_raw_fd(fd) };
            }
            let name = component(path.parts.last().ok_or_else(||Error::new(ErrorCode::UnsafePath,"Missing file component"))?.as_bytes())?;
            // SAFETY: anchored parent fd and validated single leaf; never
            // follow a symlink or replace any existing file on the filesystem.
            let fd = unsafe { libc::openat(directory.as_raw_fd(),name.as_ptr(),
                libc::O_WRONLY|libc::O_CREAT|libc::O_EXCL|libc::O_NOFOLLOW|libc::O_CLOEXEC,0o600 as libc::c_int) };
            if fd < 0 { return Err(filesystem_error(io::Error::last_os_error())); }
            let mut file = unsafe { File::from_raw_fd(fd) };
            file.write_all(&resource.bytes)?; file.sync_all()?;
        }
        job.checkpoint(Phase::Extracting,resources.len(),resources.len())
    }

    pub(super) fn publish(source: &Path, destination: &Path) -> Result<()> {
        let source = component(source.as_os_str().as_bytes())?;
        let destination = component(destination.as_os_str().as_bytes())?;
        #[cfg(target_os="macos")]
        // SAFETY: both CStrings live through the call. RENAME_EXCL is required;
        // unsupported filesystems return an error rather than a replacing rename.
        let result = unsafe { libc::renamex_np(source.as_ptr(),destination.as_ptr(),libc::RENAME_EXCL) } as libc::c_long;
        #[cfg(target_os="linux")]
        // SAFETY: correct renameat2 syscall signature, live CStrings, AT_FDCWD.
        let result = unsafe { libc::syscall(libc::SYS_renameat2,libc::AT_FDCWD,source.as_ptr(),
            libc::AT_FDCWD,destination.as_ptr(),libc::RENAME_NOREPLACE) };
        #[cfg(not(any(target_os="macos",target_os="linux")))]
        return Err(Error::new(ErrorCode::UnsupportedPlatform,"Exclusive directory publication unavailable"));
        #[cfg(any(target_os="macos",target_os="linux"))]
        if result == 0 { Ok(()) } else { Err(Error::from(io::Error::last_os_error())) }
    }
}

pub(crate) fn write(root: &Path, paths: &[PlannedPath], resources: &[Resource], job: &mut JobContext<'_>) -> Result<()> {
    supported()?;
    #[cfg(unix)] { unix::write(root,paths,resources,job) }
    #[cfg(not(unix))] { let _=(root,paths,resources,job); Err(Error::new(ErrorCode::UnsupportedPlatform,"Descriptor-relative extraction unavailable")) }
}
pub(crate) fn publish(source: &Path, destination: &Path) -> Result<()> {
    supported()?;
    #[cfg(unix)] { unix::publish(source,destination) }
    #[cfg(not(unix))] { let _=(source,destination); Err(Error::new(ErrorCode::UnsupportedPlatform,"Exclusive directory publication unavailable")) }
}

#[cfg(all(test,unix))]
mod tests {
    use super::*;
    use crate::{CancellationToken,Limits,resource_paths::plan};
    #[test]
    fn staged_symlink_directory_is_never_followed() {
        let root=tempfile::tempdir().unwrap(); let outside=tempfile::tempdir().unwrap();
        std::os::unix::fs::symlink(outside.path(),root.path().join("assets")).unwrap();
        let resources=vec![Resource {key:"assets/escape.bin".into(),bytes:vec![1,2,3]}];
        let paths=plan(&resources,&Limits::default()).unwrap();
        let token=CancellationToken::default(); let mut sink=|_|{};
        assert!(write(root.path(),&paths,&resources,&mut JobContext::new(&token,&mut sink)).is_err());
        assert_eq!(std::fs::read_dir(outside.path()).unwrap().count(),0);
    }
}
