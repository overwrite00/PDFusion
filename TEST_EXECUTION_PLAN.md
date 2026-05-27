# Test Execution Plan: Batch Password Fix #11

## Test Suite Location
`tests/test_batch_passwords.py` - 20+ test cases

## How to Run Tests

### Run All Batch Password Tests
```bash
cd /path/to/PDFusion
python -m pytest tests/test_batch_passwords.py -v
```

### Run Specific Test Class
```bash
# Happy path tests only
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsHappyPath -v

# Error cases
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsErrorCases -v

# Backwards compatibility
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsBackwardsCompat -v

# Operations-specific
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsOperations -v

# Stress test
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsStress -v
```

### Run Single Test
```bash
python -m pytest tests/test_batch_passwords.py::TestBatchPasswordsHappyPath::test_unprotected_files_no_password -xvs
```

### Run with Coverage
```bash
python -m pytest tests/test_batch_passwords.py --cov=src/core/batch --cov=src/ui/panels/batch_panel
```

---

## Test Class Breakdown

### 1. TestBatchPasswordsHappyPath (4 tests)
✅ Happy path scenarios - all should PASS

| Test | Scenario | Expected |
|------|----------|----------|
| `test_unprotected_files_no_password` | 3 unprotected PDFs | All succeed |
| `test_protected_files_same_password` | 3 PDFs, same password | All succeed |
| `test_protected_files_different_passwords` | 3 PDFs, different passwords | All succeed |
| `test_mixed_protected_unprotected` | 2 protected + 1 unprotected | All succeed |

### 2. TestBatchPasswordsErrorCases (2 tests)
❌ Error scenarios - should handle gracefully

| Test | Scenario | Expected |
|------|----------|----------|
| `test_protected_file_no_password_fails_explicitly` | Protected file, no pwd | Explicit error (not silent) |
| `test_wrong_password_fails_explicitly` | Protected file, wrong pwd | Explicit error with message |

### 3. TestBatchPasswordsStress (1 test)
🔥 Performance test

| Test | Scenario | Expected |
|------|----------|----------|
| `test_ten_files_different_passwords` | 10 files, 10 different passwords | All succeed, good performance |

### 4. TestBatchPasswordsBackwardsCompat (2 tests)
⚙️ Backwards compatibility tests

| Test | Scenario | Expected |
|------|----------|----------|
| `test_password_map_none_fallback_to_job_password` | password_map=None, use job.password | Works (old behavior) |
| `test_password_map_empty_fallback_to_job_password` | password_map={}, fallback to job.password | Works (hybrid) |

### 5. TestBatchPasswordsOperations (5 tests)
🔧 Each operation supports password_map

| Test | Operation | Expected |
|------|-----------|----------|
| `test_protect_operation_with_password_map` | PROTECT | All files re-protected |
| `test_watermark_operation_with_password_map` | WATERMARK | Watermarks applied |
| `test_rotate_operation_with_password_map` | ROTATE | Files rotated |
| `test_merge_operation_with_password_map` | MERGE_TO_ONE (diff pwd) | Files merged successfully |
| `test_merge_operation_same_password` | MERGE_TO_ONE (same pwd) | Files merged successfully |

### 6. TestBatchPasswordsProgressCallback (1 test)
📊 Progress reporting works

| Test | Scenario | Expected |
|------|----------|----------|
| `test_progress_callback_with_password_map` | Progress callback with password_map | Correct callbacks emitted |

---

## Test Fixtures

### Input Fixtures (reusable across tests)

**three_unprotected_pdfs**
- Creates 3 unprotected PDF files in temp directory
- Path list returned for batch operations
- No passwords involved

**three_protected_same_pwd**
- Creates 3 PDF files protected with password "same123"
- Uses `core.protect` to encrypt files
- Returns list of protected PDF paths

**three_protected_diff_pwd**
- Creates 3 PDF files with different passwords
- Passwords: "pwd_alpha", "pwd_beta", "pwd_gamma"
- Returns (paths, passwords) tuple

**mixed_protected_unprotected**
- Creates 3 PDFs: protected, unprotected, protected
- Different passwords for each protected file
- Returns (paths, password_dict) tuple

**tmp_dir** (pytest built-in)
- Temporary directory for output files
- Auto-cleaned after test

**tmp_path** (pytest built-in)
- Temporary path for test files
- Auto-cleaned after test

**sample_pdf** (project fixture)
- Base PDF file for creating test copies
- Located in test fixtures

---

## Expected Outcomes

### All Tests Pass (Total: 20+)
```
✅ TestBatchPasswordsHappyPath              4/4 passed
✅ TestBatchPasswordsErrorCases             2/2 passed
✅ TestBatchPasswordsStress                 1/1 passed
✅ TestBatchPasswordsBackwardsCompat        2/2 passed
✅ TestBatchPasswordsOperations             5/5 passed
✅ TestBatchPasswordsProgressCallback       1/1 passed
```

### Coverage Targets
- `src/core/batch.py`: >95% coverage
- `src/ui/panels/batch_panel.py`: >85% coverage (UI code)
- `_dispatch()` function: 100% coverage
- `_run_merge()` function: 100% coverage
- `_check_protected_file()`: 100% coverage

---

## Manual Testing Checklist

### UI Testing (Manual)
After running automated tests, verify UI manually:

**1. Add Protected Files**
- [ ] Drop protected PDF onto batch panel
- [ ] Password dialog appears
- [ ] File added to list with 🔒 indicator
- [ ] Password stored

**2. Add Multiple Protected Files (Different Passwords)**
- [ ] Drop file 1 (protected with "pwd1")
- [ ] Enter password in dialog
- [ ] Drop file 2 (protected with "pwd2")
- [ ] Enter different password
- [ ] Both files shown with 🔒 indicators
- [ ] Each shows different passwords in memory

**3. Run Batch with Mixed Files**
- [ ] Select operation (e.g., COMPRESS)
- [ ] Choose output directory
- [ ] Click Apply
- [ ] All files process successfully
- [ ] Each file uses correct password
- [ ] Output files in output directory

**4. Cancel Password Dialog**
- [ ] Drop protected file
- [ ] Click Cancel on password dialog
- [ ] Warning message appears
- [ ] File still added but marked as needing password
- [ ] Batch operation shows explicit error for that file

**5. Remove Protected File from List**
- [ ] Add protected file (password stored)
- [ ] Select file in list
- [ ] Click "Rimuovi"
- [ ] File removed
- [ ] No password remains in memory

---

## Error Scenarios to Test

### Silent Failure Prevention

**Scenario 1: Missing Password**
```
File: protected.pdf (password: "secret123")
Batch: password_map is empty

Expected: Explicit error
❌ NOT: File silently fails with no indication
✅ YES: Error shows "PDF password invalid or missing"
```

**Scenario 2: Wrong Password**
```
File: protected.pdf (actual password: "secret123")
Batch: password_map={file: "wrongpwd"}

Expected: Explicit error
❌ NOT: Silent failure
✅ YES: Error shows password issue
```

**Scenario 3: Mixed Protected/Unprotected**
```
Files: [protected1.pdf, unprotected.pdf, protected2.pdf]
Passwords: {file1: "pwd1", file3: "pwd2"}

Expected: All succeed
✅ file1 uses "pwd1"
✅ file2 needs no password
✅ file3 uses "pwd2"
```

---

## Performance Expectations

| Test | Files | Passwords | Expected Time |
|------|-------|-----------|----------------|
| Unprotected batch | 3 | 0 | <1s |
| Same password | 3 | 1 | <1s |
| Different passwords | 3 | 3 | <1.5s |
| Merge (different pwd) | 3 | 3 | <2s |
| Stress test (10 files) | 10 | 10 | <5s |

---

## Debugging Failed Tests

### If a test fails:

1. **Check error message**
   ```
   pytest tests/test_batch_passwords.py::TestX::test_Y -xvs
   # Look for assertion error or exception details
   ```

2. **Check temp files**
   ```
   # pytest leaves temp dirs in /tmp or Windows temp
   # Check that test fixtures are creating files correctly
   ```

3. **Check password detection**
   ```python
   # In _check_protected_file()
   # Ensure pikepdf.PasswordError is caught correctly
   ```

4. **Check password_map passing**
   ```python
   # Verify password_map flows from UI → BatchJob → _dispatch
   ```

5. **Run with verbose output**
   ```bash
   python -m pytest tests/test_batch_passwords.py -xvs --tb=long
   ```

---

## Regression Tests

Run existing batch tests to ensure no regression:
```bash
python -m pytest tests/core/test_batch.py -v
```

Expected: All existing tests still pass
- ✅ test_compress_batch
- ✅ test_rotate_batch
- ✅ test_progress_callback
- ✅ test_empty_input_returns_empty
- ✅ test_partial_failure

---

## Integration Test (End-to-End)

### Manual E2E Test
1. Launch application
2. Open Batch panel
3. Drop 3 PDFs (1 protected, 2 unprotected)
4. When protected file added:
   - [ ] Password dialog appears
   - [ ] Type password
   - [ ] File added with 🔒 indicator
5. Select COMPRESS operation
6. Choose output directory
7. Click Apply
8. Monitor progress dialog
9. Check completion:
   - [ ] All files successful
   - [ ] Output files exist
   - [ ] Files compressed correctly

---

## Success Criteria

### Test Suite ✅
- All 20+ tests pass
- No silent failures
- Explicit errors for missing/wrong passwords
- 10-file stress test completes in <5s

### Code Coverage ✅
- batch.py: >95%
- batch_panel.py: >85%
- _dispatch: 100%
- _run_merge: 100%

### Backwards Compatibility ✅
- Old code (password_map=None) works unchanged
- Falls back to job.password when needed
- Existing tests pass

### User Experience ✅
- Protected files detected automatically
- Passwords prompted when file added
- Visual indicator (🔒) for protected files
- Clear error messages if passwords wrong
- No silent failures

---

## Final Verification Checklist

- [ ] All 20+ tests pass locally
- [ ] Code coverage >90%
- [ ] No type errors or linting issues
- [ ] Manual UI testing completed
- [ ] Regression tests pass
- [ ] E2E test successful
- [ ] Documentation updated
- [ ] Ready for CI/CD pipeline
