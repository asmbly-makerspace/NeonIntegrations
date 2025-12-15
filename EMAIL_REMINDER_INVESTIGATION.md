# Email Reminder Investigation Summary

## Issue
Instructors reported receiving multiple emails (4-5) in a single day reminding them of their classes.

## Investigation Status: ✅ COMPLETE

Used Test-Driven Development (TDD) to create comprehensive test coverage for both email reminder scripts to identify potential causes of duplicate emails.

## Test Coverage Summary

### All Tests: ✅ 50 passing tests
- **dailyClassReminder.py**: 16 tests
- **weeklyClassReminder.py**: 10 tests  
- **Other tests**: 24 tests (neonUtil, openPath)

### dailyClassReminder.py - 16 Tests
✅ Comprehensive coverage including:
- Teacher deduplication (single teacher with multiple events)
- Duplicate teacher names in search results
- Multiple teachers with separate emails
- Date boundary conditions (TODAY, tomorrow, 2 days out)
- Empty events (no emails sent)
- None teacher (fallback to classes@asmbly.org)
- Unknown teachers not in teachers.json
- No registrants message
- Mixed registration statuses (SUCCEEDED, FAILED, CANCELED, etc.)
- Error handling (continues to next teacher on failure)
- Multiple attendees per registration
- **Duplicate event IDs from Neon API** (verifies no duplicate emails)

### weeklyClassReminder.py - 10 Tests
✅ Comprehensive coverage including:
- Teacher deduplication with multiple events
- Multiple teachers get separate emails
- Duplicate events only send one email
- Empty events (no emails sent)
- None teacher (fallback to board@asmbly.org)
- No registrants message
- Subject line format
- CC to classes@asmbly.org
- Deduplication efficiency with many events
- **Duplicate event IDs from Neon API** (verifies no duplicate emails)

## Code Issues Fixed

### ✅ COMPLETED: weeklyClassReminder.py Refactoring
1. **Added proper structure**: Wrapped in `main()` function with `if __name__ == '__main__'` guard
2. **Fixed O(n²) deduplication**: Changed to O(n) set comprehension
3. **Added error handling**: File operations now handle FileNotFoundError and JSONDecodeError
4. **Fixed resource leak**: File properly closed using context manager
5. **Standardized MIME headers**: Changed to proper capitalization (To, CC, Subject)
6. **Removed dead code**: Unused base64 import removed
7. **Added logging configuration**: Fixed datetime format (%H:%M:%S)

### ✅ COMPLETED: Both Scripts Enhanced
1. **Invocation logging added**: Each script logs unique UUID for tracking individual runs
2. **Logging format fixed**: Corrected datetime format from %H:%H:%S to %H:%M:%S

## Root Cause Analysis

### ✅ RULED OUT: Code-Level Issues

#### 1. Deduplication Logic Failures - ❌ NOT THE CAUSE
**Status**: Thoroughly tested and confirmed working correctly.

**Evidence**:
- Both scripts use set comprehension for O(n) teacher deduplication
- 26 comprehensive tests verify correct behavior
- Tests confirm: Multiple events per teacher → single email
- Tests confirm: Duplicate events in search results → single email
- Tests confirm: Duplicate event IDs from API → single email per teacher

#### 2. Neon API Returning Duplicate Events - ❌ NOT THE CAUSE  
**Status**: Tested with mock duplicate event IDs - does NOT cause duplicate emails.

**Evidence**:
- New tests simulate API returning duplicate event records with same event ID
- Both duplicate events are shown in email body (acceptable behavior)
- Teacher deduplication prevents duplicate emails even with duplicate API data
- Scripts process duplicate events but don't send duplicate emails

#### 3. Date Range Overlap - ✅ INTENTIONAL DESIGN (NOT A BUG)
**Status**: Confirmed as intentional by product owner.

**Details**:
- `dailyClassReminder.py`: TODAY to TODAY+2 days (runs daily)
- `weeklyClassReminder.py`: TODAY to TODAY+10 days (runs Sundays at 6 PM)
- Design intent: Teachers receive both weekly summary and daily reminders
- Overlap only occurs on Sundays when both scripts run

### ⚠️ MOST LIKELY CAUSE: Duplicate Script Invocations

**Hypothesis**: The systemd timer is triggering multiple times, causing the same script to run multiple times in a short period.

**Evidence Supporting This**:
- All code-level causes have been ruled out through testing
- Scripts work correctly in isolation (verified by tests)
- ✅ Invocation logging now added to track individual script runs

**Next Steps to Verify**:
1. Check production logs for multiple invocation IDs in short timespan
2. Review systemd timer configuration: `systemctl cat class-reminders.timer`
3. Check timer logs: `journalctl -u class-reminders.service --since "1 week ago"`
4. Verify no duplicate deployment paths (systemd + cron, multiple directories, etc.)

### ❓ REQUIRES EXTERNAL TESTING: Email Vendor Issues

**Hypothesis**: Gmail API or SMTP layer might be duplicating messages.

**Cannot test in code** - would require:
- Gmail API logs review
- AWS/Gmail retry configuration verification
- Email delivery tracking

## Recommendations for Production

### ✅ COMPLETED: Code Improvements
1. **Test coverage**: 26 comprehensive tests added (16 daily + 10 weekly)
2. **weeklyClassReminder.py refactoring**: Proper structure, error handling, resource management
3. **Invocation logging**: Unique UUID logged at script start in both scripts
4. **Logging format**: Fixed datetime format in both scripts

### 🔍 NEXT STEPS: Production Investigation

**Primary Focus**: Verify systemd timer configuration and check for duplicate invocations

1. **Monitor invocation IDs in production logs**:
   ```bash
   journalctl -u class-reminders.service --since "1 week ago" | grep "Script invocation ID"
   ```
   Look for multiple invocation IDs within minutes of each other.

2. **Review systemd timer configuration**:
   ```bash
   systemctl list-timers
   systemctl cat class-reminders.timer
   ```
   Verify timer isn't triggering multiple times.

3. **Check for duplicate deployments**:
   - Verify script isn't running from both systemd timer AND cron
   - Check for multiple timer units pointing to same script
   - Confirm no duplicate directories running the same script

4. **If duplicates persist**, investigate:
   - Gmail API logs for duplicate send attempts
   - AWS/Gmail retry configuration
   - Email delivery tracking

### 💡 Optional Enhancements

**Only implement if duplicate invocations are confirmed as the issue:**

1. **Rate limiting**: Track last email time per teacher to prevent duplicates within 23 hours
2. **Email subject differentiation**: Make daily vs weekly distinction clearer
3. **Email footer tracking**: Include invocation ID in footer for debugging

## Summary

### What We've Accomplished

1. **✅ Comprehensive Testing**: 26 tests covering all code paths in both reminder scripts
2. **✅ Code Refactoring**: weeklyClassReminder.py properly structured and optimized  
3. **✅ Invocation Tracking**: Unique UUIDs logged for production debugging
4. **✅ Bug Fixes**: Resource leaks, error handling, logging format issues resolved

### What We've Ruled Out

1. **❌ Deduplication logic failures**: Verified working correctly through extensive tests
2. **❌ Duplicate events from Neon API**: Tested - does not cause duplicate emails
3. **✅ Date range overlap**: Confirmed as intentional design (not a bug)

### Most Likely Root Cause

**Duplicate script invocations** (systemd timer misconfiguration) - next step is to verify in production using the invocation IDs now being logged.

## Files Modified

- `dailyClassReminder.py` - Added invocation logging, fixed datetime format
- `weeklyClassReminder.py` - Major refactoring + invocation logging
- `tests/test_dailyClassReminders.py` - Added 11 new tests (now 16 total)
- `tests/test_weeklyClassReminder.py` - Created with 10 comprehensive tests
- `EMAIL_REMINDER_INVESTIGATION.md` - This document

## Test Results

**All 50 tests pass** ✅
```
tests/test_dailyClassReminders.py:     16 tests PASSED
tests/test_weeklyClassReminder.py:     10 tests PASSED
tests/test_neonUtil.py:                11 tests PASSED
tests/test_openPathUpdateAll.py:       10 tests PASSED
tests/test_openPathUpdateSingle.py:     3 tests PASSED

Total: 50 passed in 0.66s
```
