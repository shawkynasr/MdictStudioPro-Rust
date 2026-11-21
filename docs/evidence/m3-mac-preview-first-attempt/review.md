# First preview build attempt

Lock/source checks, installed direct frontend versions, CLI flag check and all
four exact M3 lock normalizations passed. The desktop full dependency metadata
command then requested uncached android_system_properties 0.1.6 while offline.
No native compilation or .app creation occurred. The runner's metadata preflight
was broader than needed: it now uses --no-deps. Exact lock hashes and the actual
build's --locked --offline flags remain mandatory; no dependency download or
upgrade is introduced by the correction. Required Mac build archives, if missing,
will still be reported as a separate failure rather than silently fetched.
