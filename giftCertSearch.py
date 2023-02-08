import neon
import requests
import json
import sys

""" json_OrderOutputFields = neon.getOrderOutputFields()
json_OrderSearchFields = neon.getOrderSearchFields() """

""" with open('Search_and_output.json', "w", encoding="utf-8") as f:
    json.dump(json_OrderOutputFields, f, indent=3)
    json.dump(json_OrderSearchFields, f, indent=3) """

def main():
    if len(sys.argv) != 2 or not str(sys.argv[1]).isnumeric():
        print(f'''Usage: {sys.argv[0]} <integer Gift Certificate Number>''')
    else:
        gift_cert_num = sys.argv[1]
        searchFields =  f'''
[
    {{
        "field": "Shopping Cart ID",
        "operator": "EQUAL",
        "value": "{gift_cert_num}"
    }}
]
'''

        outputFields =  '''
[
    "Account ID",
    "First Name",
    "Last Name"
]
'''

        response = neon.postOrderSearch(searchFields, outputFields)

        searchResults = response.get("searchResults")

        print(searchResults)

if __name__ == "__main__":
    main()