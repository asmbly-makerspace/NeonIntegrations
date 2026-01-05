from pprint import pprint
from enum import StrEnum

import requests

from config import N_APIkey, N_APIuser

class CustomObjectSortOrder(StrEnum):
    ASC = 'ASC'
    DESC = 'DESC'

class CustomObjectSortColumn(StrEnum):
    IDENTIFIER = 'name'
    ASSIGNED_ACCOUNT = 'Assigned_Account_c'

class CustomObjectSearchFields(StrEnum):
    ASSIGNED_ACCOUNT = 'Assigned_Account_c'
    IDENTIFIER = 'name'

class CustomObjectSearchOperator(StrEnum):
    EQUAL = 'EQUAL'
    NOT_EQUAL = 'NOT_EQUAL'
    BLANK = 'BLANK'
    NOT_BLANK = 'NOT_BLANK'
    # CONTAIN can only be used when IDENTIFIER is the search field
    CONTAIN = 'CONTAIN'

class CustomObjectSearchValues(StrEnum):
    DEFAULT = 'placeholder'

class CustomObjectOutputFieldLabels(StrEnum):
    ASSIGNED_ACCOUNT = 'Assigned%20Account'
    LOFT_STORAGE_SPACES_IDENTIFIER = 'Loft%20Storage%20Spaces%20Identifier'
    COWORKING_SPACES_IDENTIFIER = 'Coworking%20Spaces%20Identifier'

class CustomObjectOutputColumnNames(StrEnum):
    ASSIGNED_ACCOUNT = 'Assigned_Account_c'
    IDENTIFIER = 'name'

class NeonCustomObjectAPIName(StrEnum):
    LOFT_STORAGE_SPACES = 'Loft_Storage_Spaces_c'
    COWORKING_SPACES = 'Coworking_Spaces_c'

def apiCall(httpVerb, url, data):
    # Make request
    if httpVerb == 'GET':
        response = requests.get(url, data=data, timeout=5)
    elif httpVerb == 'POST':
        response = requests.post(url, data=data, timeout=5)
    else:
        print(f"HTTP verb {httpVerb} not supported")

    return response

##### NEON #####

def api_login(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/common/login'
    queryParams = f'?login.apiKey={N_APIkey}&login.orgid={N_APIuser}'
    data = ''

    url = N_BASE_URL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data)

    sessionId = response.json().get("loginResponse").get('userSessionId')

    return sessionId

def api_logout(sessionId):
    httpVerb = 'GET'
    resourcePath = '/common/logout'
    queryParams = f'?userSessionId={sessionId}'
    data = ''

    url = N_BASE_URL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data).json()

    return response.get("logoutResponse").get("operationResult")

def getCustomObjects(sessionId: str, objectAPIName: str, requiredSearchFields: dict, **optionalSearchFields):
    httpVerb = 'GET'
    resourcePath = '/customObjectRecord/listCustomObjectRecords'
    queryParams = f'''?userSessionId={sessionId}&objectAPIName={objectAPIName}'''
    for key, value in requiredSearchFields.items():
        if isinstance(value, list):
            for item in value:
                queryParams += f'&{key}={item}'
        else:
            queryParams += f'&{key}={value}'
    if optionalSearchFields:
        for key, value in optionalSearchFields.items():
            if value is not None:
                if isinstance(value, list):
                    for item in value:
                        queryParams += f'&{key}={item}'
                else:
                    queryParams += f'&{key}={value}'
            else:
                continue
    data = ''

    url = N_BASE_URL + resourcePath + queryParams
    responseEvent = apiCall(httpVerb, url, data)

    return responseEvent.json()

def updateAssignedAccount(sessionId: str, objectAPIName: str, recordId: str, neonId: str = ""):
    httpVerb = 'GET'
    resourcePath = '/customObjectRecord/updateCustomObjectRecord'
    queryParams = f'''?userSessionId={sessionId}&customObjectRecord.objectApiName={objectAPIName}\
        &customObjectRecord.recordId={recordId}'''
    data = ''
    namePrefix = "customObjectRecord.customObjectRecordDataList.customObjectRecordData.name"
    valuePrefix = "customObjectRecord.customObjectRecordDataList.customObjectRecordData.value"

    updatedField = CustomObjectSearchFields.ASSIGNED_ACCOUNT

    # If neonId is an empty string, function will remove the assigned account
    queryParams += f'&{namePrefix}={updatedField}&{valuePrefix}={neonId}'

    url = N_BASE_URL + resourcePath + queryParams
    responseEvent = apiCall(httpVerb, url, data)

    return responseEvent.json()

### The following fields are required ###

N_BASE_URL = 'https://api.neoncrm.com/neonws/services/api'
SESSION_ID = api_login(N_APIkey, N_APIuser)
OBJECT_API_NAME = NeonCustomObjectAPIName.LOFT_STORAGE_SPACES

# This should be a list of constants from the CustomObjectOutputFieldLabels enum
OUTPUT_FIELD_LABELS = [
    CustomObjectOutputFieldLabels.ASSIGNED_ACCOUNT,
    CustomObjectOutputFieldLabels.LOFT_STORAGE_SPACES_IDENTIFIER
    ]

# This should be a list of constants from the CustomObjectOutputColumnNames enum
OUTPUT_FIELD_COLUMN_NAMES = [
    CustomObjectOutputColumnNames.ASSIGNED_ACCOUNT,
    CustomObjectOutputColumnNames.IDENTIFIER
    ]

requiredSearchCriteria = {
    "customObjectOutputFieldList.customObjectOutputField.label": OUTPUT_FIELD_LABELS,
    "customObjectOutputFieldList.customObjectOutputField.columnName": OUTPUT_FIELD_COLUMN_NAMES,
}

### end of required fields ###

### The following fields are optional and can be a blank list or set to None ###

SEARCH_CRITERIA_FIELDS = [CustomObjectSearchFields.ASSIGNED_ACCOUNT]

SEARCH_CRITERIA_OPERATORS = [CustomObjectSearchOperator.NOT_BLANK]

# E.g. "A1" for "name" or "Matthew Miller" for "Assigned_Account_c". If using the
# NOT_BLANK operator this can be any value, but there must be a value.
SEARCH_CRITERIA_VALUES = [CustomObjectSearchValues.DEFAULT]

RESULTS_PAGE_SIZE = 50
RESULTS_SORT_COLUMN = CustomObjectSortColumn.IDENTIFIER
RESULTS_CURRENT_PAGE = 1

optionalSearchCriteria = {
    "customObjectSearchCriteriaList.customObjectSearchCriteria.criteriaField": SEARCH_CRITERIA_FIELDS,
    "customObjectSearchCriteriaList.customObjectSearchCriteria.operator": SEARCH_CRITERIA_OPERATORS,
    "customObjectSearchCriteriaList.customObjectSearchCriteria.value": SEARCH_CRITERIA_VALUES,
    "page.pageSize": str(RESULTS_PAGE_SIZE),
    "page.sortColumn": RESULTS_SORT_COLUMN,
    "page.sortDirection": CustomObjectSortOrder.ASC,
    "page.currentPage": str(RESULTS_CURRENT_PAGE),
}

### end of optional fields ###

customObjects = getCustomObjects(
    SESSION_ID,
    OBJECT_API_NAME,
    requiredSearchFields = requiredSearchCriteria,
    **optionalSearchCriteria
)

storageAssignments = customObjects.get("listCustomObjectRecordsResponse")\
    .get("searchResults").get("nameValuePairs")

for assignment in storageAssignments:
    for value in assignment.get("nameValuePair"):
        print(f'{value.get("name")}: {value.get("value")}')
    print()

logout = api_logout(SESSION_ID)
