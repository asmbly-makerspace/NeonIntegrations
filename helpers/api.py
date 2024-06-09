import requests


## Helper function for API calls
def apiCall(httpVerb, url, json, headers):
    # Make request
    if httpVerb == "GET":
        response = requests.get(url, json=json, headers=headers)
    elif httpVerb == "POST":
        response = requests.post(url, json=json, headers=headers)
    elif httpVerb == "PUT":
        response = requests.put(url, json=json, headers=headers)
    elif httpVerb == "PATCH":
        response = requests.patch(url, json=json, headers=headers)
    elif httpVerb == "DELETE":
        response = requests.delete(url, json=json, headers=headers)
    else:
        print(f"HTTP verb {httpVerb} not recognized")

    # These lines break the code for PATCH requests
    # response = response.json()
    # pprint(response)

    return response
