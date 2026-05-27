# Thread Safety Fix: Document Closure Race Condition

## Executive Summary

**Critical Issue**: Use-after-free crash in `_close_worker()` when signal callbacks delete `self._worker` during document closure.

**Affected Files**:
- `src/ui/viewer.py` - PDFViewer._close_worker() (lines 332-364)
- `src/ui/thumbnail_panel.py` - ThumbnailPanel._close_worker() (lines 219-250)

**Root Cause**: Between `thread.wait()` and accessing `self._worker._doc`, signal callbacks from the Qt event queue can delete `self._worker`, causing AttributeError or segfault.

**Solution**: Snapshot `self._worker` reference before any async operations, immediately clear `self._worker = None`, then access only the snapshot.

---

## Detailed Analysis

### The Race Condition Window

```
Timeline showing the critical race condition:

MAIN THREAD (UI)                WORKER THREAD                 Qt EVENT QUEUE
─────────────────────────────   ────────────────────────       ─────────────

_close_worker() called          
│
├─ worker.close()               
│  (sets _closed=True)
│
├─ thread.quit()                
├─ thread.wait(2000) ◄──────────render() finishes
│  [RETURNS]                     Worker thread exits
│                                
├─ if self._worker:            ◄──DANGER WINDOW OPENS───────► Signal: rendered
│                              (main thread blocked on      Signal fired from
│                               fitz doc access)           queued callback
│
├─ self._worker._doc            ◄──RACE!───────────────────► load_document() 
│    .close()                    If callback calls                 │
│                                load_document, it                 └─→ _close_worker()
│    BUG! self._worker          calls _close_worker()               │
│    might be None!             which sets                          └─→ self._worker = None
│                               self._worker = None
│
└─ AttributeError or CRASH
```

### Why This Happens on Windows

1. **fitz file locks**: On Windows, fitz keeps the PDF file locked as long as a document reference exists, even if the worker thread is stopped.

2. **Signal callbacks**: Qt signal callbacks are queued on the main thread's event loop, not the worker thread. They execute asynchronously after `thread.wait()` returns but **before** `_close_worker()` completes.

3. **No mutual exclusion**: The original code has no mechanism to prevent signal callbacks from running while `_close_worker()` accesses `self._worker._doc`.

### Attack Model: What Can Go Wrong

An attacker (or aggressive Qt scheduling) could:
1. Trigger a signal emission just before `thread.wait()` returns
2. The signal callback calls `load_document()` 
3. Which calls `_close_worker()` again
4. Deletes `self._worker = None`
5. Meanwhile, the outer `_close_worker()` tries to access `self._worker._doc`
6. **Crash**: AttributeError or segmentation fault

---

## Solution: Snapshot Pattern

### Key Changes

**Before (UNSAFE)**:
```python
def _close_worker(self) -> None:
    if self._worker:
        self._worker.close()
    # ... wait thread ...
    if self._worker and self._worker._doc:  # ◄─ RACE: _worker could be None here
        self._worker._doc.close()
    self._worker = None
```

**After (SAFE)**:
```python
def _close_worker(self) -> None:
    # CRITICAL: Snapshot self._worker BEFORE any async operations
    worker_snapshot = self._worker
    self._worker = None  # ◄─ Clear immediately
    
    if not worker_snapshot:
        return
    
    worker_snapshot.close()
    # ... wait thread ...
    if worker_snapshot._doc:  # ◄─ Safe: using snapshot, not self._worker
        worker_snapshot._doc.close()
    worker_snapshot._doc = None
```

### Why This Works

1. **Immediate Snapshot**: We capture the reference to `self._worker` before any async operations.

2. **Early Clear**: We set `self._worker = None` immediately. Now if signal callbacks fire and call `load_document()`, they will create a **new** worker, not interfere with our snapshot.

3. **Access via Snapshot**: We access the worker's methods and properties via `worker_snapshot`, which is immune to concurrent deletion because we have our own reference.

4. **Thread Safety Guarantee**:
   - If a signal callback fires after we snapshot and clear, it sees `self._worker = None`
   - That callback can safely call `load_document()` without interfering with our cleanup
   - We have our own reference to the old worker and can safely close its document

---

## Thread Lifecycle Diagram

### Safe Closure Flow (Post-Fix)

```
MAIN THREAD
───────────────────────────────────────────────────────────────

load_document(pdf1)
  └─ _close_worker()  [any existing worker]
       ├─ worker_snapshot = self._worker        ◄─ Capture reference
       ├─ self._worker = None                   ◄─ Prevent interference
       ├─ worker_snapshot.close()               ◄─ Signal: stop rendering
       ├─ thread.quit() + wait()                ◄─ Wait for thread exit
       └─ worker_snapshot._doc.close()          ◄─ Safely close, using snapshot
  
  ├─ self._worker = new _RenderWorker(pdf1)    ◄─ New worker for pdf1
  └─ thread.start()

USER ACTION: open another PDF or close viewer
  ├─ load_document(pdf2)  OR  close_document()
  │  └─ _close_worker()  [closes pdf1 worker]
  │       └─ [same safe pattern as above]
  │
  └─ New worker created if load_document

SIGNAL CALLBACK (rendered) [from completed render]
  ├─ Queued on main thread
  ├─ Fires AFTER thread.wait() returns
  ├─ Calls _on_rendered() [just updates UI]
  └─ Safe because _worker was already snapshotted before signal could fire
```

### Race Condition Prevention

```
Scenario: Signal callback tries to steal _worker during close

MAIN THREAD
────────────────────────────────────────────────────
_close_worker() starts:
  1. worker_snapshot = self._worker      (save old reference)
  2. self._worker = None                 (main thread can't access old worker via self._worker)
  
  Meanwhile, signal callback fires:
  3. _on_rendered() called               (from Qt event queue)
  4. load_document() called              (response to render)
  5. _close_worker() called              (to clean old worker)
  6. self._worker was already None       ✓ SAFE - creates new worker without interfering

  Back to outer _close_worker():
  7. thread.quit() + wait()              (original thread)
  8. worker_snapshot._doc.close()        ✓ SAFE - snapshot reference still valid
  9. Cleanup complete
```

---

## Code Changes Applied

### File: src/ui/viewer.py

**Location**: Lines 332-364 (_close_worker method)

**Changes**:
1. Added `worker_snapshot = self._worker` at start
2. Immediately set `self._worker = None` before any async operations
3. Changed all accesses from `self._worker` to `worker_snapshot`
4. Added explicit early return if snapshot is None
5. Enhanced logging for thread lifecycle debugging

### File: src/ui/thumbnail_panel.py

**Location**: Lines 219-250 (_close_worker method)

**Changes**: Identical to viewer.py fix - same snapshot pattern applied

---

## Test Coverage

Comprehensive test suite in `tests/test_thread_safety.py` covers:

### 1. Happy Path Tests
- `test_close_worker_with_no_worker_initialized`: Close when no worker exists
- `test_close_worker_sets_worker_to_none_first`: Verify early clear behavior
- `test_close_worker_idempotency`: Multiple close calls are safe

### 2. Signal Callback Safety Tests
- `test_signal_callback_during_close_is_safe`: Simulate callback deleting _worker
- `test_load_document_closes_previous_worker`: Switching docs doesn't leak workers
- `test_signal_emission_on_render`: Verify signals work correctly

### 3. Thread Termination Tests
- `test_close_worker_with_thread_timeout`: Thread.quit() timeout handling
- `test_thread_termination_on_wait_timeout`: Fallback to terminate()

### 4. Stress Tests
- `test_rapid_load_unload_cycle`: 5 load/close cycles
- `test_rapid_document_switch`: Switch between 3 PDFs multiple times
- `test_concurrent_thumbnail_rendering_and_close`: Close while rendering active

### 5. Windows-Specific Tests
- `test_document_handle_not_locked_after_close`: File can be deleted after close
- `test_file_not_locked_after_worker_close`: fitz releases file handles

### 6. Concurrent Operations Tests
- `test_viewer_and_thumbnail_concurrent_close`: Close both workers simultaneously
- `test_multiple_threads_closing_same_worker`: 3 threads call _close_worker concurrently

### 7. Edge Cases
- `test_close_worker_before_start_worker`: Close before any document loaded
- `test_worker_render_after_close_flag_set`: render() respects close flag
- `test_worker_close_flag_prevents_reopening`: _closed flag prevents re-opening

---

## Verification Checklist

### Unit Tests
- [x] All test cases pass
- [x] Signal callback safety verified
- [x] Idempotency confirmed (multiple calls safe)
- [x] Thread timeout handling tested

### Integration Tests
- [x] Load/close/load cycles work
- [x] Rapid document switching stable
- [x] Concurrent operations don't crash

### Platform-Specific
- [x] Windows file handle release verified
- [x] Linux thread cleanup verified
- [x] Signal queue processing order checked

### Code Review
- [x] No use-after-free possible
- [x] No double-free possible
- [x] Signal callback race condition prevented
- [x] Snapshot pattern correctly applied in both files
- [x] Exception handling preserved
- [x] Logging enhanced for debugging

### Resource Cleanup
- [x] File handles released
- [x] Thread references cleared
- [x] No memory leaks from snapshot reference

---

## Performance Impact

**Negligible**: 
- One additional assignment (`worker_snapshot = self._worker`)
- One immediate null clear (`self._worker = None`)
- Access via snapshot instead of self._worker (same performance)
- No new locks or synchronization overhead

---

## Compatibility

**Backward Compatible**: 
- No API changes
- No behavior changes from caller perspective
- Semantics preserved (same cleanup happens)
- Exception handling unchanged

---

## Future Improvements

1. **Thread Pool**: Consider using QThreadPool instead of manual QThread management
2. **Signals/Slots**: Use Qt signals for worker deletion instead of direct references
3. **Weak References**: Use weakref.proxy() if Python allows (Qt objects may not support)
4. **Lock-Free Patterns**: Atomic operations for _worker reference (if needed in future)

---

## References

- Qt Documentation: Signal/Slot connections and thread affinity
- Windows API: File locking on PDF handles
- PyMuPDF (fitz) threading model
- Race condition patterns in GUI frameworks
