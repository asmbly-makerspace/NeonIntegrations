import datetime

import helpers.neon as neon

CLASSES = {
    "Woodshop Safety": 1,
    "Metal Shop Safety": 1,
    "Woodshop Specialty Tools": 2,
    "Metal Lathe": 2,
    "Milling": 2,
    "MIG Welding": 2,
    "TIG Welding": 2,
    "Beginner CNC": 3,
    "Filament 3D Printing": 1,
    "Resin 3D Printing":2,
    "Wood Lathe": 2,
    "Big Lasers": 3,
    "Small Lasers": 2,
    "Sublimation": 1,
    "Shaper Origin": 2,
    "Stationary Sanders": 1,
    "Bowl Turning": 2,
    "Vinyl Cutter": 1,
    "Round Materials": 3,
    "Stained Glass": 2,
    "Sewing": 1,
    "Fusion 360 CAM": 2,
    "Orientation": "PS",
}

today = datetime.date.today()
#deltaDays = today + datetime.timedelta(days=90)
searchFields = f'''
[
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
    "Event Registration Attendee Count",
    "Event ID",
    "Event Code"
]
'''
totalPatched = 0
response = neon.postEventSearch(searchFields, outputFields)
totalPages = response["pagination"]["totalPages"]
responseEvents = response['searchResults']

for event in responseEvents:
    if not event.get("Event Code"):
        for eventName, tier in CLASSES.items():
            if eventName in event["Event Name"]:
                codePatch = neon.eventTierCodePatch(event["Event ID"], tier)
                print(event["Event Name"] + " Status Code: " + f"{codePatch.status_code}")
                totalPatched += 1

for page in range(totalPages):
    responseEvents = neon.postEventSearch(searchFields, outputFields, page=page)['searchResults']
    for event in responseEvents:
        if not event.get("Event Code"):
            for eventName, tier in CLASSES.items():
                if eventName in event["Event Name"]:
                    codePatch = neon.eventTierCodePatch(event["Event ID"], tier)
                    print(event["Event Name"] + " Status Code: " + f"{codePatch.status_code}")
                    totalPatched += 1

print(totalPatched)
