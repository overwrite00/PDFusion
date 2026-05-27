# Password Flow Diagram: Batch Operations with Per-File Passwords

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                        │
│                     (BatchPanel - PyQt6)                        │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────────┐
         │                         │                             │
    DROP FILES              ADD FILE HANDLER          _add_files()
         │                         │                             │
         └─────────────────────────┼─────────────────────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │ _check_protected_file(path)  │
                    │                              │
                    │ 1. Try pikepdf.open()        │
                    │ 2. No password needed?       │
                    │    Return None               │
                    │ 3. PasswordError caught?     │
                    │    Show ask_password()       │
                    │    Store pwd if provided     │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │ _file_passwords dict:        │
                    │ {                            │
                    │   file1.pdf: "pwd1",         │
                    │   file2.pdf: "pwd2",         │
                    │   file3.pdf: None,           │
                    │ }                            │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │ FILE LIST WIDGET:            │
                    │ • file1.pdf 🔒               │
                    │ • file2.pdf 🔒               │
                    │ • file3.pdf                  │
                    └──────────────┬───────────────┘
                                   │
                           ┌───────▼────────┐
                           │ USER CLICKS    │
                           │ APPLY BUTTON   │
                           └───────┬────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │ _on_apply()                  │
                    │                              │
                    │ Create BatchJob with:        │
                    │ password_map = dict(        │
                    │   _file_passwords           │
                    │ )                            │
                    └──────────────┬───────────────┘
                                   │
         ┌─────────────────────────▼─────────────────────────────┐
         │                   CORE LAYER                          │
         │              (batch.py - run_batch)                   │
         └──────────────────────────┬──────────────────────────┘
                                    │
                 ┌──────────────────▼──────────────────┐
                 │ BatchJob created with:              │
                 │ • operation: COMPRESS               │
                 │ • output_dir: /path/to/output       │
                 │ • password_map: {                   │
                 │     file1: "pwd1",                  │
                 │     file2: "pwd2",                  │
                 │     file3: None                     │
                 │   }                                 │
                 └──────────────┬───────────────────┘
                                │
                ┌───────────────▼────────────────┐
                │ FOR EACH FILE IN PARALLEL:     │
                │ ThreadPoolExecutor(max=4)      │
                │                                │
                │ process_one(path) {            │
                │   _dispatch(path, job)         │
                │ }                              │
                └───────────────┬────────────────┘
                                │
        ┌───────────────────────▼───────────────────────┐
        │         PASSWORD LOOKUP IN _dispatch()        │
        │                                               │
        │ if job.password_map and path in password_map: │
        │     pwd = job.password_map[path]              │
        │ else:                                         │
        │     pwd = job.password  # fallback            │
        │                                               │
        │ Returns: str | None                           │
        └───────────────┬───────────────────────────────┘
                        │
        ┌───────────────▼──────────────────────┐
        │ ROUTE TO CORRECT OPERATION:          │
        │                                      │
        │ if COMPRESS:                         │
        │   compress(path, out, config, pwd)   │
        │ elif PROTECT:                        │
        │   protect(path, out, config, pwd)    │
        │ elif WATERMARK:                      │
        │   apply_watermark(path, out, cfg,pwd)│
        │ elif ROTATE:                         │
        │   rotate_all(path, angle, out, pwd)  │
        │ elif MERGE_TO_ONE:                   │
        │   _run_merge([paths], out, job)      │
        │ ... etc                              │
        │                                      │
        └───────────────┬──────────────────────┘
                        │
        ┌───────────────▼──────────────────────┐
        │ SPECIAL: MERGE OPERATION             │
        │                                      │
        │ _run_merge(input_paths, out, job):   │
        │                                      │
        │ if job.password_map:                 │
        │   passwords = [                      │
        │     job.password_map.get(p,          │
        │                         job.password)│
        │     for p in input_paths             │
        │   ]                                  │
        │ else:                                │
        │   passwords = [job.password] * len   │
        │                                      │
        │ merge(paths, output, passwords)      │
        └───────────────┬──────────────────────┘
                        │
        ┌───────────────▼──────────────────────┐
        │ CORE OPERATION EXECUTES:             │
        │                                      │
        │ If pwd provided:                     │
        │   pikepdf.open(path, password=pwd)   │
        │ else:                                │
        │   pikepdf.open(path)                 │
        │                                      │
        │ Operation succeeds OR raises error   │
        └───────────────┬──────────────────────┘
                        │
        ┌───────────────▼──────────────────────┐
        │ EXCEPTION HANDLING:                  │
        │                                      │
        │ try:                                 │
        │   _dispatch(...)                     │
        │ except Exception as e:               │
        │   return BatchResult(                │
        │     path, None, False, str(e)        │
        │   )                                  │
        │                                      │
        │ Error is EXPLICIT not silent!        │
        └───────────────┬──────────────────────┘
                        │
        ┌───────────────▼──────────────────────┐
        │ BATCH RESULT:                        │
        │                                      │
        │ BatchResult(                         │
        │   input_path=file1,                  │
        │   output_path=output_file,           │
        │   success=True,                      │
        │   error=None                         │
        │ )                                    │
        │                                      │
        │ OR on failure:                       │
        │                                      │
        │ BatchResult(                         │
        │   input_path=file2,                  │
        │   output_path=None,                  │
        │   success=False,                     │
        │   error="PDF password invalid..."    │
        │ )                                    │
        └───────────────┬──────────────────────┘
                        │
         ┌──────────────▼──────────────────┐
         │  PROGRESS CALLBACK (periodic)   │
         │                                 │
         │ progress_callback(              │
         │   completed=1,                  │
         │   total=3,                      │
         │   name="file1.pdf"              │
         │ )                               │
         └──────────────┬──────────────────┘
                        │
         ┌──────────────▼──────────────────┐
         │ COLLECT ALL RESULTS:            │
         │                                 │
         │ [                               │
         │   BatchResult(..., success=T),  │
         │   BatchResult(..., success=T),  │
         │   BatchResult(..., success=F),  │
         │ ]                               │
         └──────────────┬──────────────────┘
                        │
         ┌──────────────▼──────────────────────┐
         │      RETURN TO UI LAYER             │
         └──────────────┬──────────────────────┘
                        │
         ┌──────────────▼──────────────────────┐
         │ _on_batch_done(results):            │
         │                                     │
         │ - Show completion dialog            │
         │ - Display success/failure stats     │
         │ - Show error details for failed     │
         │ - Update status message             │
         │                                     │
         │ Result shown to user:               │
         │ "Completato: 2/3 con successo"      │
         │ "1 file con errori:                 │
         │  • file2.pdf: PDF password invalid" │
         └──────────────────────────────────────┘
```

## Password Resolution Algorithm (Priority Order)

```
FUNCTION resolve_password(path: Path, job: BatchJob) -> str | None:
    
    # STEP 1: Check password_map for explicit per-file password
    IF job.password_map EXISTS AND path IN job.password_map:
        password = job.password_map[path]
        RETURN password  # Use mapped password (highest priority)
    
    # STEP 2: Fall back to uniform password (backwards compat)
    ELSE:
        password = job.password
        RETURN password  # Could be None if no fallback
    
    # Note: If password is None and file is protected,
    # core function will raise PasswordError (explicit, not silent)
END
```

## Decision Tree for Protected File Handling

```
┌─────────────────────────────────┐
│ File added to batch panel       │
└────────────────────┬────────────┘
                     │
        ┌────────────▼───────────┐
        │ _check_protected_file()│
        └────────────┬───────────┘
                     │
        ┌────────────▼───────────────────────┐
        │ Try: pikepdf.open(path)             │
        │ (without password)                  │
        └────────────┬───────────────────────┘
                     │
        ┌────────────▼─────────────────────────────┐
        │ SUCCESS: No password needed             │
        └────────────┬─────────────────────────────┘
                     │
        ┌────────────▼──────────────────────┐
        │ _file_passwords[path] = None       │
        │ Display: "file.pdf"                │
        │ NO 🔒 indicator                    │
        └────────────────────────────────────┘


        ┌────────────▼─────────────────────────────┐
        │ EXCEPTION: pikepdf.PasswordError         │
        │ (File is password-protected)             │
        └────────────┬─────────────────────────────┘
                     │
        ┌────────────▼──────────────────────────┐
        │ ask_password(filename=path.name)      │
        │ Show password dialog to user          │
        └────────────┬──────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │ User enters password?     │
        └────┬───────────────┬──────┘
             │ YES           │ NO (Cancel)
             │               │
        ┌────▼──────┐   ┌────▼──────────────┐
        │ pwd = "x" │   │ Show warning:     │
        │           │   │ "Protected but    │
        │           │   │  no password"     │
        │           │   │                   │
        │           │   │ _file_passwords   │
        │           │   │ [path] = None     │
        └────┬──────┘   └────┬──────────────┘
             │               │
        ┌────▼──────────────▼──────────────┐
        │ Store in _file_passwords dict    │
        │ Display with 🔒 indicator        │
        └──────────────────────────────────┘
```

## Error Handling Flow

```
BATCH OPERATION EXECUTION
├─ FILE 1 (protected, pwd in map)
│  ├─ _dispatch(file1, job)
│  │  ├─ pwd = job.password_map[file1]  ← "pwd1"
│  │  ├─ compress(file1, out1, cfg, "pwd1")
│  │  └─ SUCCESS
│  └─ BatchResult(file1, out1, True, None)
│
├─ FILE 2 (protected, WRONG pwd in map)
│  ├─ _dispatch(file2, job)
│  │  ├─ pwd = job.password_map[file2]  ← "WRONGPWD"
│  │  ├─ compress(file2, out2, cfg, "WRONGPWD")
│  │  └─ EXCEPTION: "PDF password invalid"
│  └─ BatchResult(file2, None, False, "PDF password...")
│
├─ FILE 3 (protected, NO pwd in map)
│  ├─ _dispatch(file3, job)
│  │  ├─ pwd = job.password  ← None (fallback)
│  │  ├─ compress(file3, out3, cfg, None)
│  │  └─ EXCEPTION: "PDF password invalid"
│  └─ BatchResult(file3, None, False, "PDF password...")
│
└─ RESULTS COLLECTED:
   ✅ File 1: Success
   ❌ File 2: Error (wrong password)
   ❌ File 3: Error (missing password)
   
   USER SEES:
   "Completato: 1/3 con successo
    2 file con errori:
    • file2.pdf: PDF password invalid
    • file3.pdf: PDF password invalid"
```

## Backwards Compatibility Matrix

```
SCENARIO 1: Old Code (No password_map)
├─ job = BatchJob(operation=..., password="pwd")
├─ password_map = None
└─ All files use "pwd" as fallback
   Result: WORKS (same as before)

SCENARIO 2: New Code (With password_map)
├─ job = BatchJob(
│   operation=...,
│   password_map={file1: "pwd1", file2: "pwd2"}
│ )
├─ password_map is populated
└─ Each file uses mapped password
   Result: WORKS (new feature)

SCENARIO 3: Hybrid (password_map partial)
├─ job = BatchJob(
│   operation=...,
│   password="fallback_pwd",
│   password_map={file1: "pwd1"}
│ )
├─ file1 uses "pwd1" (from map)
├─ file2 uses "fallback_pwd" (fallback)
└─ file3 uses "fallback_pwd" (fallback)
   Result: WORKS (fallback mechanism)

SCENARIO 4: Empty password_map
├─ job = BatchJob(
│   operation=...,
│   password="pwd",
│   password_map={}
│ )
├─ password_map exists but is empty
├─ All files check map: not found
├─ All files fallback to "pwd"
└─ Behavior: WORKS (same as SCENARIO 1)
```

## UI State Management

```
BATCH PANEL STATE:
┌─────────────────────────────────────────────┐
│ self._files: list[Path]                     │
│ [Path("a.pdf"), Path("b.pdf"), ...]         │
│                                             │
│ self._file_passwords: dict[Path, str|None]  │
│ {                                           │
│   Path("a.pdf"): None,       # unprotected  │
│   Path("b.pdf"): "pwd2",     # protected    │
│   Path("c.pdf"): None,       # protected    │
│ }                                           │
│                                             │
│ Display List:                               │
│ • a.pdf          (no 🔒)                    │
│ • b.pdf 🔒       (has 🔒)                   │
│ • c.pdf          (no 🔒, but needs pwd!)    │
└─────────────────────────────────────────────┘

OPERATION: Remove file
├─ Pop from self._files
├─ Pop from self._file_passwords (important!)
└─ Update display

OPERATION: Clear all
├─ Clear self._files
├─ Clear self._file_passwords (important!)
└─ Clear display

OPERATION: Apply Batch
├─ password_map = dict(self._file_passwords)
├─ Create BatchJob(password_map=password_map)
├─ Pass to run_batch()
└─ Show progress and results
```

## Testing Coverage Map

```
PASSWORD LOOKUP LOGIC:
├─ ✅ password_map exists, file in map
├─ ✅ password_map exists, file NOT in map (fallback)
├─ ✅ password_map is None (full fallback)
├─ ✅ password_map is empty (full fallback)
└─ ✅ password_map is None AND job.password is None

ERROR SCENARIOS:
├─ ✅ Protected file, no password (explicit error)
├─ ✅ Protected file, wrong password (explicit error)
├─ ✅ Unprotected file, password provided (ignored)
└─ ✅ Mixed protected/unprotected (each handled correctly)

OPERATIONS:
├─ ✅ COMPRESS with password_map
├─ ✅ PROTECT with password_map
├─ ✅ WATERMARK with password_map
├─ ✅ ROTATE with password_map
├─ ✅ MERGE_TO_ONE with password_map (per-file)
├─ ✅ ADD_HEADERS_FOOTERS with password_map
├─ ✅ ADD_LICENSE_PAGE with password_map
└─ ✅ SPLIT with password_map

BACKWARDS COMPATIBILITY:
├─ ✅ password_map=None, use job.password
├─ ✅ password_map={}, fallback to job.password
├─ ✅ Old tests still pass
└─ ✅ Existing code unchanged

STRESS:
└─ ✅ 10 files, 10 different passwords
```

## Silent Failure Prevention: Before vs After

```
BEFORE (BROKEN):
┌──────────────────────────────────┐
│ File 1: protected, pwd="secret"  │
│ File 2: protected, pwd="other"   │
│ File 3: unprotected              │
│                                  │
│ BatchJob(password="secret")       │
│                                  │
│ Result:                          │
│ File 1: ✅ Works (right pwd)     │
│ File 2: 💥 SILENT FAILURE        │ ← BUG!
│         (user doesn't know!)     │
│ File 3: ✅ Works (no pwd needed) │
│                                  │
│ User sees: "Operation complete"  │
│ But File 2 was never processed!  │
└──────────────────────────────────┘

AFTER (FIXED):
┌──────────────────────────────────────┐
│ File 1: protected, pwd="secret"      │
│ File 2: protected, pwd="other"       │
│ File 3: unprotected                  │
│                                      │
│ password_map = {                     │
│   file1: "secret",                   │
│   file2: "other",                    │
│   file3: None                        │
│ }                                    │
│                                      │
│ Result:                              │
│ File 1: ✅ Works (mapped pwd)        │
│ File 2: ✅ Works (mapped pwd)        │
│ File 3: ✅ Works (no pwd needed)     │
│                                      │
│ User sees:                           │
│ "Completato: 3/3 con successo"       │
│ All files processed correctly!       │
└──────────────────────────────────────┘

WORST CASE (User forgets password):
┌──────────────────────────────────────┐
│ password_map empty or missing file:  │
│                                      │
│ File 2: protected, no pwd in map     │
│                                      │
│ Result: ❌ EXPLICIT ERROR            │
│ "file2.pdf: PDF password invalid"    │
│                                      │
│ User sees clear error message        │
│ Can retry with correct password      │
└──────────────────────────────────────┘
```

## Summary: Key Design Points

1. **Per-file password mapping** → No more uniform passwords for mixed batches
2. **Explicit error handling** → Silent failures eliminated completely
3. **UI password detection** → Protected files detected at add time
4. **Backwards compatibility** → Old code works unchanged
5. **Fallback mechanism** → password_map + job.password work together
6. **All operations supported** → COMPRESS, PROTECT, WATERMARK, ROTATE, MERGE, etc.
7. **Progress reporting** → Works with password_map
8. **Comprehensive tests** → 20+ test cases covering all scenarios
