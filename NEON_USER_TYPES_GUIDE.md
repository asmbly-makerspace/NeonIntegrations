# Neon CRM User Types Guide

This document describes the different user types in Neon CRM, what access each type has, payment information, special Neon fields, and hidden behaviors in the code.

---

## 1. **Paid Staff** (`STAFF_TYPE`)
**Neon Field:** `Individual Type` = "Paid Staff"

### Access
- **Facility Access:** YES - 24/7 access to all facilities
- **OpenPath Groups:** SUBSCRIBERS, STEWARDS, INSTRUCTORS, COWORKING, CERAMICS (both interior and exterior doors)
- **Facility Requirements:** None - staff access is not gated by waiver, tour, or membership status
- **Special Tool Access:** Granted via separate custom fields (see below)

### Payment
- **Membership Required:** NO - staff accounts do not need a membership to have facility access
- **Payment Status:** Can be paid, comped, or have no membership at all
- **Regular Membership ID:** 1
- **Ceramics Membership ID:** 7

### Special Neon Fields
- `Individual Type` = "Paid Staff" (the identifying field)
- Optional fields that may be present but don't gate access:
  - `OpenPathID` (numeric ID linking to access control system)
  - `DiscourseID` (numeric ID for community forum)
  - `WaiverDate` (safety waiver - may not be required for staff)
  - `FacilityTourDate` (facility orientation - may not be required for staff)
  - `KeyCardID` (88) - physical key card
  - `AccessSuspended` (180) - flag to suspend access despite staff type
  - `Shaper Origin` (274) - access to specialized woodworking tool
  - `Woodshop Specialty Tools` (440) - access to Festool Domino and Makita Track Saw

### Hidden Behaviors
- Staff get their own dedicated storage in OpenPath (STEWARDS group) and INSTRUCTORS group
- They bypass all membership validation checks
- If a staff account has a valid regular membership, they get additional tracking fields:
  - `membershipDates` - dict of all successful membership periods
  - `Membership Start Date` - earliest successful membership start
  - `Membership Expiration Date` - latest successful membership expiration
  - `autoRenewal` - whether membership auto-renews
  - `validMembership` flag (will be True if current)
  - `paidRegular` or `compedRegular` flags
- Multiple staff can exist; the code uses `getRealAccounts()` to fetch them along with members

---

## 2. **Leader** (`DIRECTOR_TYPE`)
**Neon Field:** `Individual Type` = "Leader"

### Access
- **Facility Access:** YES - 24/7 access (same as Super Steward and Space Lead)
- **OpenPath Groups:** MANAGEMENT (unrestricted 24/7 access)
- **Facility Requirements:** None - leadership access is not gated by membership or waiver

### Payment
- **Membership Required:** NO
- **Payment Status:** Can be paid, comped, or have no membership

### Special Neon Fields
- `Individual Type` = "Leader" (the identifying field)
- Optional fields:
  - `OpenPathID` (numeric ID linking to access control)
  - `DiscourseID` (numeric ID for community forum)
  - `AccessSuspended` (180) - can override access despite leader type
  - Same optional tool access fields as staff

### Hidden Behaviors
- Grouped with SUPER_TYPE and LEAD_TYPE in access checks (all get GROUP_MANAGEMENT in OpenPath)
- If leader has a valid membership, they get the same tracking fields as staff
- Can have ceramics membership in addition to regular membership

---

## 3. **Space Lead** (`LEAD_TYPE`)
**Neon Field:** `Individual Type` = "Space Lead"

### Access
- **Facility Access:** YES - 24/7 access (same as Leader and Super Steward)
- **OpenPath Groups:** MANAGEMENT (unrestricted 24/7 access)
- **Facility Requirements:** None

### Payment
- **Membership Required:** NO
- **Payment Status:** Can be paid, comped, or have no membership

### Special Neon Fields
- `Individual Type` = "Space Lead" (the identifying field)
- Optional fields: Same as Leader and Staff types

### Hidden Behaviors
- Treated identically to DIRECTOR_TYPE for access purposes (both get MANAGEMENT group)
- Special role semantically distinct from Director but technically equivalent in code
- Likely represents a different organizational role (e.g., space manager vs board director)

---

## 4. **Super Steward** (`SUPER_TYPE`)
**Neon Field:** `Individual Type` = "Super Steward"

### Access
- **Facility Access:** YES - 24/7 access (same as Leader and Space Lead)
- **OpenPath Groups:** MANAGEMENT (unrestricted 24/7 access)
- **Facility Requirements:** None

### Payment
- **Membership Required:** NO
- **Payment Status:** Can be paid, comped, or have no membership

### Special Neon Fields
- `Individual Type` = "Super Steward" (the identifying field)
- Optional fields: Same as other leadership types

### Hidden Behaviors
- Grouped with DIRECTOR_TYPE and LEAD_TYPE in code (all get MANAGEMENT access)
- Likely represents an elevated steward role with full facility oversight

---

## 5. **CoWorking Tenant** (`COWORKING_TYPE`)
**Neon Field:** `Individual Type` = "CoWorking Tenant"

### Access
- **Facility Access:** CONDITIONAL
  - Must have valid waiver and facility tour
  - AccessSuspended flag must NOT be set
  - **SPECIAL:** Can access facility even with LAPSED membership if waiver and tour are current
  - **OpenPath Groups:** COWORKING group (plus SUBSCRIBERS if membership is valid)
- **Membership Requirements:** Regular membership (ID 1), but can have lapsed with waiver/tour

### Payment
- **Membership Status:** Usually paid or comped, but access can survive membership lapse
- **Amount:** Variable membership fee structure
- **Special Behavior:** Most permissive group regarding membership lapses

### Special Neon Fields
- `Individual Type` = "CoWorking Tenant" (the identifying field)
- **Required for access:**
  - `WaiverDate` - safety waiver date
  - `FacilityTourDate` - facility orientation date
  - `AccessSuspended` (180) - flag that can override coworking access
- **Optional:**
  - `OpenPathID`
  - `DiscourseID`
  - Special tool access fields

### Hidden Behaviors
- Explicitly checked with special logic in `accountHasFacilityAccess()` to allow lapsed membership
- Code contains a warning log: "CoWorking subscriber %s has access despite a lapsed membership"
- Even with valid tour/waiver, still needs ceramics-specific checks for ceramics shop access
- Gets COWORKING group in OpenPath for dedicated coworking space access

---

## 6. **Steward** (`STEWARD_TYPE`)
**Neon Field:** `Individual Type` = "Steward"

### Access
- **Facility Access:** CONDITIONAL - requires valid membership + waiver + tour
- **OpenPath Groups:** STEWARDS group (dedicated steward storage) plus SUBSCRIBERS group
- **Ceramics Access:** Only if they also have valid ceramics membership + CSI training

### Payment
- **Membership Required:** YES - valid membership mandatory (unlike coworking)
- **Membership Type:** Regular (ID 1) or Ceramics (ID 7)
- **Payment:** Must be SUCCEEDED transaction, or comped

### Special Neon Fields
- `Individual Type` = "Steward" (the identifying field)
- **Required for access:**
  - `WaiverDate` - safety waiver
  - `FacilityTourDate` - facility orientation
  - Must have valid membership with SUCCEEDED status
  - `AccessSuspended` (180) - can block access
- **For Ceramics:**
  - `CsiDate` (1248) - ceramics safety/training certification

### Hidden Behaviors
- Stricter than coworking: membership lapse immediately blocks access
- Gets STEWARDS group in OpenPath (separate storage from regular members)
- If they also have ceramics membership and CSI cert, they unlock GROUP_CERAMICS access
- Full facility access is membership + waiver + tour based

---

## 7. **Instructor** (`INSTRUCTOR_TYPE`)
**Neon Field:** `Individual Type` = "Instructor"

### Access
- **Facility Access:** CONDITIONAL - can access facility if member, OR access instructor storage even if non-member
- **OpenPath Groups:** INSTRUCTORS group (dedicated instructor storage) - granted regardless of membership
- **Special:** Can be granted access to teach without being a member

### Payment
- **Membership Required:** NO - not required to have facility access as instructor
- **But:** Can have valid membership if they are also members
- **Payment:** Can be paid member, comped member, or have no membership

### Special Neon Fields
- `Individual Type` = "Instructor" (the identifying field)
- **Optional:**
  - `OpenPathID`
  - `DiscourseID`
  - `WaiverDate` (may be required by individual facility policies)
  - `FacilityTourDate` (may be required by individual facility policies)
  - Same optional tool fields as others

### Hidden Behaviors
- `getOpGroups()` explicitly adds INSTRUCTORS group if account is Instructor type (no membership check)
- If instructor ALSO has a valid membership with waiver/tour, they get full member access on top
- This allows non-member instructors to teach while preventing unsupervised facility access
- Instructors get dedicated storage access in OpenPath

---

## 8. **Wiki Admin** (`WIKI_ADMIN_TYPE`)
**Neon Field:** `Individual Type` = "Wiki Admin"

### Access
- **Facility Access:** CONDITIONAL - requires valid membership + waiver + tour (like regular members)
- **OpenPath Groups:** SUBSCRIBERS group (standard member access only)
- **Facility Requirements:** Same as regular members

### Payment
- **Membership Required:** YES
- **Membership Type:** Regular (ID 1)
- **Payment:** Must be SUCCEEDED transaction status

### Special Neon Fields
- `Individual Type` = "Wiki Admin" (the identifying field)
- No special access fields beyond what regular members need
- Same fields as regular members apply

### Hidden Behaviors
- No special handling in OpenPath group assignment code
- Treated as regular member for facility access purposes
- The "Wiki Admin" designation appears to be for community documentation/management, not facility access
- Gets SUBSCRIBERS group in OpenPath (same as regular members)

---

## 9. **Volunteer** (`ONDUTY_TYPE`)
**Neon Field:** `Individual Type` = "Volunteer"

### Access
- **Facility Access:** CONDITIONAL - can access interior door/clock-in buttons even without membership
- **OpenPath Groups:** ONDUTY group (volunteers-only access) - granted regardless of membership
- **Special:** Designed for on-duty volunteer shifts; can access limited area without membership

### Payment
- **Membership Required:** NO - volunteers don't need memberships
- **Payment:** Can be paid/comped members, or have no membership

### Special Neon Fields
- `Individual Type` = "Volunteer" (the identifying field)
- **Optional:**
  - `OpenPathID`
  - `WaiverDate` (may be required for facility access)
  - Same optional fields as other types

### Hidden Behaviors
- `getOpGroups()` explicitly grants ONDUTY group regardless of membership status
- Access is specifically limited to interior doors (not full unsupervised facility access)
- Non-member volunteers can clock in/out for shifts but cannot access full facility
- If volunteer ALSO has valid membership with requirements met, they get regular member access on top

---

## 10. **Ceramics Volunteer** (`ONDUTY_TYPE_CERAMICS`)
**Neon Field:** `Individual Type` = "Ceramics Volunteer"

### Access
- **Facility Access:** CONDITIONAL - can access ceramics interior door only, even without membership
- **OpenPath Groups:** GROUP_CERAMICS_ONDUTY - interior ceramics door only (not exterior)
- **Special:** Similar to regular volunteer but for ceramics studio specifically

### Payment
- **Membership Required:** NO
- **Payment:** Can be paid/comped members, or non-members

### Special Neon Fields
- `Individual Type` = "Ceramics Volunteer" (the identifying field)
- **Optional:**
  - `OpenPathID`
  - `CsiDate` (1248) - ceramics safety certification (may be required)
  - `WaiverDate` (may be required)

### Hidden Behaviors
- Explicitly granted CERAMICS_ONDUTY group (interior only)
- By design, they get INTERIOR access only - not the exterior shop door
- This prevents non-member volunteers from accessing ceramics shop unsupervised
- Code comment: "ceramics_onduty gets the interior ceramics door but not exterior entry so non-member volunteers can't get into the shop unsupervised via ceramics"
- If they become members with ceramics membership, they'd additionally get GROUP_CERAMICS (full ceramics access)

---

## Summary Table: Access & Payment

| User Type | Type Field | 24/7 Access | Needs Membership | Needs Waiver/Tour | Ceramics Access | Special Access |
|-----------|-----------|-----------|-----------------|-------------------|-----------------|-----------------|
| Paid Staff | "Paid Staff" | YES | NO | NO | Via custom field | Via custom field |
| Leader | "Leader" | YES | NO | NO | Via custom field | Via custom field |
| Space Lead | "Space Lead" | YES | NO | NO | Via custom field | Via custom field |
| Super Steward | "Super Steward" | YES | NO | NO | Via custom field | Via custom field |
| CoWorking | "CoWorking Tenant" | NO* | NO** | YES | NO | Coworking space |
| Steward | "Steward" | Conditional | YES | YES | Via CSI cert | Steward storage |
| Instructor | "Instructor" | Conditional*** | NO | Maybe | No | Instructor storage |
| Wiki Admin | "Wiki Admin" | NO | YES | YES | NO | None |
| Volunteer | "Volunteer" | NO**** | NO | Maybe | NO | Limited (interior) |
| Ceramics Volunteer | "Ceramics Volunteer" | NO**** | NO | Maybe | Interior only | Interior ceramics |

*Can access with lapsed membership if waiver/tour are current (unique behavior)
**Usually needs membership but can lapse if waiver/tour current
***Can access instructor storage without membership; facility access with membership
****Limited access - specific doors/buttons only

---

## Custom Neon Fields Reference

These are the special fields stored in Neon's account custom fields. They are fetched as part of account data and made available as top-level keys in the account dictionary:

| Field ID | Field Name | Purpose | Format | Used By |
|----------|-----------|---------|--------|---------|
| 85 | DiscourseID | Link to community forum account | String/Numeric | Discourse sync scripts |
| 77 | OrientationDate | Facility tour completion date | Date (YYYY-MM-DD) | FacilityTourDate in code |
| 179 | WaiverDate | Safety waiver signed date | Date (YYYY-MM-DD) | Facility access gating |
| 178 | OpenPathID | Link to access control system | Numeric | OpenPath sync scripts |
| 88 | KeyCardID | Physical access card number | String/Numeric | Key card systems |
| 180 | AccessSuspended | Flag to disable facility access | Boolean/Flag | Override access regardless of type |
| 182 | (Unknown) | Fetched but not used in provided code | ? | Unknown |
| 274 | Shaper Origin | Woodshop: Shaper Origin tool access | Date | Tool access checks |
| 440 | Woodshop Specialty Tools | Woodshop: Domino/Track Saw access | Date | Tool access checks |
| 1248 | CsiDate | Ceramics Safety Instruction certification | Date | Ceramics access gating |

---

## Membership Information

Neon stores membership records separately from account records. Each account can have multiple membership records over time.

### Membership Fields
- `termStartDate` - membership term start (YYYY-MM-DD)
- `termEndDate` - membership term end (YYYY-MM-DD)
- `status` - transaction status: "SUCCEEDED", "FAILED", "No Record", etc.
- `fee` - amount paid (0 = comped/complimentary)
- `autoRenewal` - whether membership auto-renews
- `membershipLevel.id` - tier ID (1 = regular, 7 = ceramics)

### Membership Flags Set by `appendMemberships()`
- `validMembership` - TRUE if ANY membership is: (status == SUCCEEDED) AND (termEndDate >= today) AND (termStartDate <= today)
- `ceramicsMembership` - TRUE if current valid membership is ceramics tier (ID 7)
- `paidRegular` - TRUE if current regular membership has fee > 0
- `paidCeramics` - TRUE if current ceramics membership has fee > 0
- `compedRegular` - TRUE if current regular membership has fee == 0
- `compedCeramics` - TRUE if current ceramics membership has fee == 0

### Special Membership Logic
- **Lapsed Renewal Grace:** If membership expired yesterday AND autoRenewal == TRUE AND no current membership status record, account is kept as `validMembership = True` pending auto-renewal processing
- **Continuous Membership:** NOT guaranteed between dates in `Membership Start Date` and `Membership Expiration Date` (membership may have lapses)

---

## OpenPath Group Mapping

When an account is synced to OpenPath access control, it's assigned to these groups based on its Neon type and membership:

| OpenPath Group | Group ID | Who Gets It |
|---|---|---|
| GROUP_MANAGEMENT | 23174 | Leader, Director, Space Lead, Super Steward |
| GROUP_SUBSCRIBERS | 23172 | Staff, members with facility access |
| GROUP_CERAMICS | 691741 | Members with ceramics membership + CSI cert |
| GROUP_COWORKING | 23175 | CoWorking tenants with facility access |
| GROUP_STEWARDS | 27683 | Stewards with facility access |
| GROUP_INSTRUCTORS | 96676 | Instructors (membership not required) |
| GROUP_SHAPER_ORIGIN | 37059 | Any account with Shaper Origin custom field set |
| GROUP_DOMINO | 96643 | Any account with Woodshop Specialty Tools custom field set |
| GROUP_ONDUTY | 507223 | Volunteers |
| GROUP_CERAMICS_ONDUTY | 730657 | Ceramics Volunteers |

---

## Code Entry Points

Key functions for understanding user types:

- `neonUtil.getRealAccounts()` - Fetches all staff, members, and volunteers with detailed membership data
- `neonUtil.getAccountsByType(type)` - Get all accounts of a specific type
- `neonUtil.accountIsType(account, type)` - Check if account has a specific type
- `neonUtil.accountHasFacilityAccess(account)` - Check if account has any facility access
- `neonUtil.subscriberHasFacilityAccess(account)` - Check if member has access (membership + waiver + tour)
- `neonUtil.subscriberHasCeramicsAccess(account)` - Check if member has ceramics access
- `openPathUtil.getOpGroups(account)` - Determine which OpenPath groups an account should be in


