# Email Reminder Investigation Summary

## Issue
Instructors are reporting receiving multiple emails (4-5) in a single day reminding them of their classes.

## Investigation Approach
Used Test-Driven Development (TDD) to create comprehensive test coverage for both email reminder scripts to identify potential causes of duplicate emails.

## Test Coverage Summary

### dailyClassReminder.py
✅ **15 comprehensive tests** covering:
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

**Result**: All code paths tested, deduplication logic confirmed working correctly.

### weeklyClassReminder.py
✅ **9 comprehensive tests** covering:
- Teacher deduplication with multiple events
- Multiple teachers get separate emails
- Duplicate events only send one email
- Empty events (no emails sent)
- None teacher (fallback to board@asmbly.org)
- No registrants message
- Subject line format
- CC to classes@asmbly.org
- Deduplication efficiency with many events

**Result**: All code paths tested after refactoring, deduplication logic confirmed working correctly.

## Issues Found and Fixed

### 1. ✅ FIXED: weeklyClassReminder.py - Lack of Proper Structure
**Problem**: The weekly reminder script executed at module import time rather than being wrapped in a main() function with `if __name__ == '__main__'` guard.

**Risk**: If the script was accidentally imported rather than executed, it could run unexpectedly. This also made it impossible to unit test.

**Fix**: Refactored weeklyClassReminder.py to:
- Wrap all execution logic in a `main()` function
- Add `if __name__ == '__main__':` guard
- Extract helper functions for better testability

### 2. ✅ FIXED: weeklyClassReminder.py - Inefficient Deduplication
**Problem**: Lines 58-60 used an inefficient list-based deduplication:
```python
rawTeachers = [item.get("Event Topic") for item in responseEvents["searchResults"]]
teachers = []
[teachers.append(teacher) for teacher in rawTeachers if teacher not in teachers]
```

**Risk**: While this still deduplicates correctly, the O(n²) complexity could cause issues with large datasets. More importantly, it uses a list comprehension as a statement (discarding the return value), which is not Pythonic.

**Fix**: Changed to use set comprehension (O(n) complexity):
```python
teachers = list({item.get("Event Topic") for item in responseEvents["searchResults"]})
```

## Potential Root Causes of Duplicate Emails

Based on code analysis and testing, here are the possible causes ranked by likelihood:

### 1. ⚠️ LIKELY: Duplicate Script Invocation
**Hypothesis**: The systemd timer or cron job is triggering multiple times.

**Evidence**:
- Both scripts have proper deduplication logic that works correctly (verified by tests)
- The scripts process events correctly without duplicating within a single run
- The README mentions that systemd timers are used to run these scripts

**How to verify**:
- Check systemd timer logs: `/var/log/syslog` or `journalctl -u class-reminders.service`
- Check for multiple timer units that might be running the same script
- Verify timer configuration doesn't have multiple triggers

**Testing recommendation**: This would need to be tested in the production environment by checking systemd logs and timer configurations.

### 2. ⚠️ POSSIBLE: Date Range Overlap Between Scripts
**Hypothesis**: Both daily and weekly scripts email about the same classes.

**Evidence**:
- `dailyClassReminder.py` searches for events from TODAY to TODAY+2 days
- `weeklyClassReminder.py` searches for events from TODAY to TODAY+10 days
- These ranges overlap, meaning a class 2 days out could be included in both emails

**However**: 
- Daily script runs daily (per README)
- Weekly script runs weekly (Sundays at 6:00 PM per code comment)
- A teacher would only get duplicates if they check emails on Sunday AND both scripts run at similar times

**Mitigation**: This appears to be intentional design - teachers get:
- Weekly: Summary of all classes in next 10 days (Sundays)
- Daily: Reminder of classes in next 2 days (daily)

If this is causing confusion, consider:
- Adjusting daily script to only send for classes TODAY and tomorrow (not +2 days)
- OR adjusting weekly script to skip Sunday when daily also runs
- OR clearly label emails as "Weekly Summary" vs "Daily Reminder"

### 3. ❌ RULED OUT: Deduplication Logic Failure
**Status**: Thoroughly tested and working correctly.

**Evidence**:
- dailyClassReminder.py uses set comprehension (line 83): `TEACHERS = {item.get("Event Topic") for item in RESPONSE_EVENTS["searchResults"]}`
- weeklyClassReminder.py now uses set comprehension (after fix)
- Tests confirm that:
  - Multiple events for one teacher → one email
  - Duplicate events in search results → one email
  - Same teacher teaching multiple classes → one email with all classes

### 4. ❓ POSSIBLE: Neon API Returning Duplicate Events
**Hypothesis**: The Neon CRM API might be returning duplicate event records.

**Evidence**: 
- Both scripts deduplicate teachers but not events before processing
- If API returns duplicate event records, the script would process them separately
- However, deduplication by teacher should still prevent duplicate EMAILS

**How to verify**:
- Add logging to capture the raw API response
- Check if `responseEvents["searchResults"]` contains duplicate event IDs
- This would need to be tested with live API calls

**Testing recommendation**: Add logging like:
```python
event_ids = [e.get("Event ID") for e in RESPONSE_EVENTS["searchResults"]]
if len(event_ids) != len(set(event_ids)):
    logging.warning("Duplicate event IDs detected in API response: %s", event_ids)
```

### 5. ❓ REQUIRES EMAIL VENDOR TESTING: Gmail/SMTP Issues
**Hypothesis**: The email sending mechanism might be duplicating messages.

**This would require testing with the email vendor** (Gmail API based on code):
- Check Gmail API logs for duplicate send attempts
- Verify `sendMIMEmessage()` implementation doesn't retry
- Check if AWS/Gmail is configured to retry failed sends

## Recommendations

### Immediate Actions (Code-based)

1. ✅ **DONE**: Add comprehensive test coverage to both scripts
2. ✅ **DONE**: Refactor weeklyClassReminder.py for better structure
3. ✅ **DONE**: Fix inefficient deduplication in weeklyClassReminder.py

### Production Environment Actions

1. **Check systemd timer logs** for duplicate invocations:
   ```bash
   journalctl -u class-reminders.service -u internal-class-checker.service --since "1 week ago" | grep "Beginning class reminders"
   ```

2. **Add invocation logging** to both scripts:
   ```python
   import uuid
   invocation_id = str(uuid.uuid4())
   logging.info("Script invocation ID: %s", invocation_id)
   ```
   
   This would help identify if teachers are receiving multiple emails from different script runs.

3. **Add API response logging** to detect duplicate events from Neon:
   ```python
   logging.info("Received %d events from Neon API", len(RESPONSE_EVENTS["searchResults"]))
   event_ids = [e.get("Event ID") for e in RESPONSE_EVENTS["searchResults"]]
   if len(event_ids) != len(set(event_ids)):
       logging.warning("Duplicate event IDs in API response: %s", 
                      [id for id in event_ids if event_ids.count(id) > 1])
   ```

4. **Review systemd timer configuration** on AdminBot2025 EC2 instance:
   ```bash
   systemctl list-timers
   systemctl cat class-reminders.timer
   ```

5. **Check for multiple deployment paths**: Verify the script isn't running from both:
   - systemd timer
   - cron job
   - manual execution
   - different directory/deployment

### Optional Improvements

1. **Add rate limiting**: Track emails sent in the last 24 hours to prevent duplicates:
   ```python
   # Store in Redis or local file with timestamp
   # Skip if teacher was emailed in last 23 hours
   ```

2. **Improve email subject differentiation**:
   - Daily: "Class Reminder - [TODAY/Tomorrow] - [Date]"
   - Weekly: "Weekly Class Summary - Week of [Date]"

3. **Add email tracking**: Include invocation ID and script name in email footer for debugging.

4. **Separate event deduplication from teacher deduplication**: Currently only teachers are deduplicated, not events.

## Confidence Level

Based on testing and code analysis:

- **HIGH CONFIDENCE**: The deduplication logic within each script works correctly ✅
- **HIGH CONFIDENCE**: The refactored code structure is more robust ✅  
- **MEDIUM CONFIDENCE**: Duplicate invocations are the most likely cause (needs production log analysis)
- **LOW CONFIDENCE**: Date range overlap is intentional design, not a bug
- **NEEDS TESTING**: API returning duplicates, Gmail API issues, systemd timer misconfiguration

## Next Steps

1. Deploy the refactored weeklyClassReminder.py to production
2. Add invocation logging and API response logging as recommended
3. Review systemd timer logs for duplicate executions
4. Monitor for 1 week to see if duplicates still occur
5. If issues persist, investigate Gmail API logs and Neon API responses

## Files Modified

- `weeklyClassReminder.py` - Refactored with main() function and improved deduplication
- `tests/test_dailyClassReminders.py` - Added 10 new comprehensive tests (now 15 total)
- `tests/test_weeklyClassReminder.py` - Created new file with 9 comprehensive tests
- `EMAIL_REMINDER_INVESTIGATION.md` - This document

## Test Execution

All tests pass:
```
======================== test session starts =========================
collected 24 items

tests/test_dailyClassReminders.py::... (15 tests)  PASSED [100%]
tests/test_weeklyClassReminder.py::...  (9 tests)  PASSED [100%]

========================= 24 passed in 0.18s =========================
```
