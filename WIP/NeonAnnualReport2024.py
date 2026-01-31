#!/usr/bin/env python3
########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################
#################################################################
#  This helper script is a work in progress...                  #
#################################################################

from pprint import pprint
import requests
import json
import base64
import time
from datetime import date, timedelta, datetime

# Ensure project root is on sys.path so project imports work from subfolders
import sys
from pathlib import Path
projectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(projectRoot))

import helpers.neon as neon

filenameMem = 'neonMembersAR2024'

# # Setup Helpers
# print("Account Fields:\n")
# pprint(neon.getAccountSearchFields())
# exit(0)

# General search fields with custom values for level, term, and enrollment counts
def generateSF(levelValue, termValue, allTimeCount, yearCount):
    return [
        {
            'field':'Membership Level',
            'operator':'EQUAL',
            'value':str(levelValue)
        },
        {
            'field':'Membership Term',
            'operator':'IN_RANGE',
            'valueList': termValue
        },
        {
            'field':'All Time Membership Enrollment Count',
            'operator':'GREATER_THAN',
            'value':str(allTimeCount)
        },
        {
            'field':'2024 Calendar Year Membership Enrollment Count',
            'operator':'GREATER_THAN',
            'value':str(yearCount)
        }
    ]


# Search fields for monthly members with more than 11 enrollments ever and over 10 in 2024 (long term members)
sfm = generateSF('Regular Membership',
                 ['Monthly Membership (Join, $95.00, 1 Month)',
                  'Monthly Membership (Renew, $95.00, 1 Month)'],
                 11, 10)
# Search fields for annual members with more than 0 enrollments ever and more than 0 in 2024 (long term members)
sfa = generateSF('Regular Membership',
                 ['Annual Membership (Join, $950.00, 1 Year)',
                  'Annual Membership (Renew, $950.00, 1 Year)'],
                 0, 0)

outputFields = [
    'Account ID',
    'All Time Membership Enrollment Count',
    '2024 Calendar Year Membership Enrollment Count',
    'First Name',
    'Last Name',
    'Email 1',
    'Membership Term',
    'Membership Level',
    'Membership Expiration Date',
    'Membership Start Date',
    'Individual Type',
    'Account Current Membership Status',
]
# Run searches for monthly and annual longterm members
longMem24M = neon.postAccountSearch(sfm, outputFields)
longMem24A = neon.postAccountSearch(sfa, outputFields)

print(f"Longterm monthly members: {longMem24M['pagination']['totalResults']}")
print(f"Longterm annual members:  {longMem24A['pagination']['totalResults']}")


# Combine the actual search result lists from each API response
def _extract_search_results(resp):
    if isinstance(resp, dict) and 'searchResults' in resp and isinstance(resp['searchResults'], list):
        return resp['searchResults']
    if isinstance(resp, list):
        return resp
    return []

parts = (_extract_search_results(r) for r in (longMem24M, longMem24A))
longMembers2024 = []
for p in parts:
    longMembers2024.extend(p)

total_records = len(longMembers2024)

# preserve insertion order while detecting duplicates
seen = set()
duplicate_map = {}
for obj in longMembers2024:
    aid = None
    if isinstance(obj, dict):
        aid = obj.get('Account ID')
    key = aid if aid is not None else f"__no_id__:{id(obj)}"
    if key in seen:
        duplicate_map.setdefault(aid, []).append(obj)
    else:
        seen.add(key)

num_duplicates = sum(len(v) for v in duplicate_map.values())
num_dup_ids = len(duplicate_map)

print("total_records:", total_records)
print("unique_account_keys (approx):", len(seen))
print("duplicate_account_ids:", num_dup_ids)
print("duplicate_records_count:", num_duplicates)

if num_dup_ids:
    print("\nSample duplicate counts by Account ID:")
    for aid, items in list(duplicate_map.items())[:10]:
        print(aid, "->", len(items) + 1)  # +1 to include the original occurrence
    print("\nSample duplicate objects for first duplicate Account ID:")
    first_aid = next(iter(duplicate_map))
    pprint(duplicate_map[first_aid][:3])

# create deduplicated ordered list (keep first occurrence)
seen_ids = set()
deduped_ordered = []
for obj in longMembers2024:
    aid = obj.get('Account ID') if isinstance(obj, dict) else None
    if aid is None:
        # treat missing ID objects as unique by object identity
        oid = id(obj)
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        deduped_ordered.append(obj)
    else:
        if aid in seen_ids:
            continue
        seen_ids.add(aid)
        deduped_ordered.append(obj)

print("deduped_ordered_count:", len(deduped_ordered))


# write CSV output
import csv
from pathlib import Path

outdir = Path('./private/AnnualReport24')
outdir.mkdir(parents=True, exist_ok=True)
csv_path = outdir / f'{filenameMem}.csv'

def _cell_value(v):
    if v is None:
        return ''
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

# prefer the declared outputFields for column order, otherwise derive from data
fieldnames = outputFields if 'outputFields' in globals() and outputFields else []
if not fieldnames and deduped_ordered:
    seen_cols = []
    for item in deduped_ordered:
        if isinstance(item, dict):
            for k in item.keys():
                if k not in seen_cols:
                    seen_cols.append(k)
    fieldnames = seen_cols

with csv_path.open('w', newline='', encoding='utf-8') as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for item in deduped_ordered:
        row = {col: _cell_value(item.get(col) if isinstance(item, dict) else None) for col in fieldnames}
        writer.writerow(row)

print("wrote CSV:", csv_path)

exit(0)