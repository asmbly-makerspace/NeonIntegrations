import datetime

import helpers.neon as neon

today = datetime.date.today()
#deltaDays = today + datetime.timedelta(days=90)

CLASS_NAME = "Orientation"

searchFields = f'''
[
    {{
        "field": "Event Name",
        "operator": "CONTAIN",
        "value": "{CLASS_NAME}"
    }},
    {{
        "field": "Event End Date",
        "operator": "GREATER_THAN",
        "value": "{today}"
    }},
    {{
        "field": "Event Archived",
        "operator": "EQUAL",
        "value": "No"
    }}
]
'''
outputFields = '''
[
    "Event Name", 
    "Event Topic",
    "Event Start Date",
    "Event End Date",
    "Event Start Time",
    "Event End Time",
    "Event ID",
    "Event Code"
]
'''
totalPatched = 0
response = neon.postEventSearch(searchFields, outputFields)
totalPages = response["pagination"]["totalPages"]
responseEvents = response['searchResults']

for event in responseEvents:
    if event.get("Event Start Time") == "18:00:01":
        eventStartTime = "6:00 PM"
        eventEndTime = "7:00 PM"
    elif event.get("Event Start Time") == "11:30:01":
        eventStartTime = "11:30 AM"
        eventEndTime = "12:30 PM"
    timePatch = neon.eventTimePatch(event["Event ID"], eventStartTime, eventEndTime)
    print(event["Event Name"] + " Status Code: " + f"{timePatch.status_code}")
    totalPatched += 1

for page in range(totalPages):
    responseEvents = neon.postEventSearch(searchFields, outputFields, page=page)['searchResults']
    for event in responseEvents:
        if event.get("Event Start Time") == "18:00:01":
            eventStartTime = "6:00 PM"
            eventEndTime = "7:00 PM"
        elif event.get("Event Start Time") == "11:30:01":
            eventStartTime = "11:30 AM"
            eventEndTime = "12:30 PM"
        timePatch = neon.eventTimePatch(event["Event ID"], eventStartTime, eventEndTime)
        print(event["Event Name"] + " Status Code: " + f"{timePatch.status_code}")
        totalPatched += 1

print(totalPatched)
