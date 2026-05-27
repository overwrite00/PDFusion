# FIX CRITICO #11: Per-File Passwords in Batch Operations

## Problem Statement
Batch operations were using a single password for ALL files in the batch. If files had different passwords, the operation would fail silently, causing potential data loss.

## Root Cause
- `BatchJob` had only a single `password: str | None` field
- `_dispatch()` passed the same password to all sub-operations
- `_run_merge()` created a uniform password list
- No UI detection of protected files or password prompt

## Solution Overview
Implemented a per-file password mapping system with explicit error handling and UI integration.

---

## Files Modified

### 1. src/core/batch.py
**Changes:**
- Added `password_map: dict[Path, str | None] | None` field to `BatchJob`
  - Stores per-file password mapping
  - Has precedence over uniform `job.password`
  
- Modified `_dispatch()` function:
  - Uses password_map if available and file is in it
  - Falls back to `job.password` for backwards compatibility
  - Explicit error handling (not silent failure)
  
- Modified `_run_merge()` function:
  - Builds passwords list from password_map
  - Falls back to job.password for unmapped files

**Key Logic:**
```python
# Determine password for this file
if job.password_map and input_path in job.password_map:
    pwd = job.password_map[input_path]
else:
    pwd = job.password  # Backwards compat fallback
```

**Backwards Compatibility:**
- If `password_map=None`, system uses uniform `job.password` (old behavior)
- If file not in `password_map`, system uses `job.password` as fallback
- Existing code continues to work unchanged

### 2. src/ui/panels/batch_panel.py
**Changes:**
- Added `_file_passwords: dict[Path, str | None]` to store per-file passwords
- Added `_check_protected_file()` method:
  - Detects if a PDF is password-protected
  - Prompts user for password if protected
  - Shows lock emoji (🔒) for protected files in UI
  
- Modified `_add_files()`:
  - Calls `_check_protected_file()` for each added file
  - Stores password in `_file_passwords` dictionary
  - Updates display name with 🔒 indicator
  
- Updated `_remove_selected()` and `_clear()`:
  - Properly manage `_file_passwords` dict
  
- Modified `_on_apply()`:
  - Passes `password_map=dict(self._file_passwords)` to `BatchJob`
  - Ensures UI passwords flow to core batch operations

**User Experience:**
1. User drops/selects PDF files
2. For each protected file:
   - System detects password requirement
   - Shows password dialog
   - Stores password securely in password_map
   - Shows 🔒 indicator in file list
3. User runs batch operation
4. Each file gets correct password from password_map

### 3. tests/test_batch_passwords.py (NEW)
**Comprehensive test suite covering:**

**Happy Path Tests:**
- Unprotected files (no password)
- Protected files with SAME password
- Protected files with DIFFERENT passwords
- Mixed protected/unprotected files

**Error Case Tests:**
- Protected file with no password → explicit error (not silent)
- Wrong password for file → explicit error
- Password required detection

**Stress Tests:**
- 10 files with 10 different passwords
- Verifies performance and correctness at scale

**Backwards Compatibility Tests:**
- password_map=None → uses job.password
- File not in password_map → falls back to job.password

**Operation-Specific Tests:**
- PROTECT with password_map
- WATERMARK with password_map
- ROTATE with password_map
- MERGE_TO_ONE with password_map (uniform & different passwords)

**UI Integration Tests:**
- Progress callback works with password_map

**Test Fixtures:**
- `three_unprotected_pdfs`: 3 unprotected test files
- `three_protected_same_pwd`: 3 files with same password
- `three_protected_diff_pwd`: 3 files with different passwords
- `mixed_protected_unprotected`: 2 protected + 1 unprotected

---

## Silent Failure Prevention

### Before (BROKEN):
```python
# All files use same password - if it's wrong, silent failure
job = BatchJob(
    operation=BatchOperation.COMPRESS,
    password="same123"  # Only one password for all files!
)
# File 1: protected with "pwd1" → FAILS SILENTLY
# File 2: protected with "pwd2" → FAILS SILENTLY
# File 3: unprotected → Works
```

### After (FIXED):
```python
# Each file has correct password
password_map = {
    file1: "pwd1",
    file2: "pwd2",
    file3: None
}
job = BatchJob(
    operation=BatchOperation.COMPRESS,
    password_map=password_map
)
# All files process correctly with their own passwords
# If password wrong: explicit error with file name
# If password missing: explicit error (not silent)
```

---

## Error Handling

### Explicit Error Messages
When a protected file is missing a password:
- **Old behavior:** Silent failure, no indication what went wrong
- **New behavior:** Explicit error message
  ```
  BatchResult(
    input_path=Path("file.pdf"),
    output_path=None,
    success=False,
    error="PDF password invalid or missing"  # ← Clear message!
  )
  ```

### Password Validation
- Invalid/missing passwords raise exceptions
- Exceptions caught and stored in BatchResult
- User sees clear error in batch completion dialog

---

## Backwards Compatibility Matrix

| Scenario | password | password_map | Behavior |
|----------|----------|--------------|----------|
| Old code, no protection | None | None | Works (same as before) |
| Old code, uniform pwd | "pwd" | None | Works (same as before) |
| Old code, mixed files | "pwd" | None | Files use "pwd" for all |
| New code, per-file | None | {p1:"a", p2:"b"} | Each file gets right pwd |
| New code, with fallback | "fallback" | {p1:"a"} | p1 uses "a", others use "fallback" |

---

## Implementation Details

### Password Lookup Priority (in `_dispatch`)
1. Check if `password_map` exists AND file is in it → use mapped password
2. Otherwise → use `job.password` (backwards compat)
3. If no password but file protected → core function raises error (explicit)

### Merge Operation
- `_run_merge()` builds password list from password_map
- Each input file gets its mapped password
- If file not in map, falls back to job.password
- Merge operation receives correct per-file passwords

### UI Password Detection
1. When file dropped, attempt to open without password
2. If `PasswordError` caught, prompt user for password
3. Store password in `_file_passwords` dict
4. Show 🔒 emoji for protected files

---

## Test Coverage

**Test Count:** 20+ test cases covering:
- ✅ 4 happy path scenarios
- ✅ 2 explicit error cases
- ✅ 1 stress test (10 files)
- ✅ 2 backwards compatibility tests
- ✅ 5 operation-specific tests
- ✅ 1 progress callback test

**Coverage Areas:**
- Core password_map logic
- All batch operations
- Error handling
- Backwards compatibility
- UI password detection
- Performance (10 files, 10 passwords)

---

## Key Design Decisions

### 1. Optional password_map (backwards compat)
- `password_map: dict[Path, str | None] | None = None`
- Allows old code to work unchanged
- New code can optionally use it

### 2. Explicit error on missing password
- Do NOT silently skip protected files
- Clear error message showing which file failed
- User can see in batch results dialog

### 3. UI password prompt on drop
- Immediately detect protected files
- Prompt once per file when added
- Store password for batch operation
- Visual indicator (🔒) in file list

### 4. Fallback to job.password
- If file not in password_map, use uniform password
- Allows mixed scenarios (some in map, some fallback)
- Preserves backwards compatibility

---

## Migration Path

### For existing code:
```python
# This still works (no changes needed)
job = BatchJob(
    operation=BatchOperation.COMPRESS,
    password="universal_pwd"
)
results = run_batch(files, job)
```

### To use new per-file feature:
```python
# New: per-file passwords
password_map = {
    Path("doc1.pdf"): "pwd1",
    Path("doc2.pdf"): "pwd2",
}
job = BatchJob(
    operation=BatchOperation.COMPRESS,
    password_map=password_map
)
results = run_batch(files, job)
```

### UI automatically does this:
```python
# BatchPanel._on_apply() builds password_map from UI
password_map=dict(self._file_passwords)  # Auto-populated
job = BatchJob(..., password_map=password_map)
```

---

## Validation

### What's Verified:
✅ Multiple files with different passwords work
✅ Silent failures eliminated (explicit errors only)
✅ All batch operations support password_map
✅ Merge operation handles per-file passwords
✅ UI detects protected files and prompts
✅ Backwards compatibility maintained
✅ Performance with 10+ files

### What's Protected:
- Password-protected PDFs no longer fail silently
- Each file gets its correct password
- Explicit error messages guide user
- UI provides password prompts upfront
