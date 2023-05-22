########################## Asmbly Class Feedback Automation ###########################
#  Neon API docs - https://developer.neoncrm.com/api-v2/                              #
#  Gmail API docs - https://developers.google.com/gmail/api/reference/rest            #
#  Google Drive API docs - https://developers.google.com/drive/api/reference/rest/v3  #
#  Google Forms API docs - https://developers.google.com/forms/api/reference/rest     #
#######################################################################################
#######################################################################################
# This script pulls the previous day's events from Neon and gathers instructor, class #
# and registrant information. It references a JSON file containing Asmbly teachers    #
# and their classes. If the file does not exist, it creates a new empty dict that     #
# will be populated automatically. When a new survey needs to be created, the Google  #
# Drive API is called to copy a master survey template and rename the copied file     #
# to the class name in Neon (e.g. Woodshop Safety w/ Maz). The Forms API is used to   #
# get the survey response URL for the survey. The link is then copied to the          #
# surveyLinks dict, which will ultimately be written back to surveyLinks.json. Each   #
# succesful registrant for the event is emailed a link to the survey.                 #
#                                                                                     #
# When the surveys need to be refreshed periodically (e.g. quarterly), the old        #
# surveys should be moved to a new folder in Drive, and the surveyLinks.json file     #
# should be deleted.                                                                  #
#######################################################################################

# Run daily as cronjob on AWS EC2 instance

import json
import base64
import datetime
import smtplib
import ssl
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import helpers.neon as neon

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from helpers.config import G_user, G_password

logging.basicConfig(
    format = '%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt= '%Y-%m-%d %H:%H:%S'
)

#################################################################################
# Send a MIME email object to its recipient using GMail
#################################################################################
def sendMIMEmessage(MIMEmessage):
    #if not "@" in MIMEmessage['To']:
    #    raise ValueError("Message doesn't have a sane destination address")

    MIMEmessage['From'] = "Asmbly Education Team"

    logging.debug(
        f'''Sending email subject "{MIMEmessage['Subject']}" to {MIMEmessage['To']}''')

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(G_user, G_password)
            server.sendmail(G_user, [MIMEmessage['To'],'classes@asmbly.org'], MIMEmessage.as_string())
        logging.info(f"Sent survey email to {MIMEmessage['To']}")
    except:
        logging.exception(
            f'''Failed sending email subject "{MIMEmessage['Subject']}" to {MIMEmessage['To']}''')
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(G_user, G_password)
            MIMEmessage['To'] = 'classes@asmbly.org'
            MIMEmessage['Subject'] = 'Feedback Request Failure'
            server.sendmail(G_user, MIMEmessage['To'], MIMEmessage.as_string())

#Define Google OAuth2 scopes needed. See https://developers.google.com/identity/protocols/oauth2/scopes
SCOPES = ['https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/forms']

#File containing private key for the service account used to implement automation
#Edit service account in Google Cloud Console 
#This script requires domain-wide delegation to run. See https://support.google.com/a/answer/162106?hl=en
SERVICE_ACCOUNT_FILE = 'classFeedbackServiceAccountKey.json'

#User email that the service account will impersonate
USER_EMAIL = "admin@asmbly.org"

#Build OAuth credentials
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

creds = credentials.with_subject(USER_EMAIL)

#Create the API services using built credential tokens
driveService = build('drive', 'v3', credentials=creds)
formsService = build('forms', 'v1', credentials=creds)

#Check if instructor-class combo already has an active survey in the feedback folder. If not, create new survey
def getSurveyLink(eventName):

    #FileId of the folder where surveys will go. Find using driveService.files().get() on a test file in that folder
    #and copying the parents field
    parentFolderId = '17aM-fE8bBZqDZA1NhnWupAFan87Tpdsd'

    #Apostrophes in query params break the URL encoding using the service's "q" search queries, so remove them
    if "'" in eventName:
        eventName = eventName.replace("'", "")

    #Check to see if the event already has a survey in Drive in case the survey links JSON files was accidentally deleted
    surveyFileCheck = driveService.files().list(q=f"mimeType='application/vnd.google-apps.form' and trashed=false and '{parentFolderId}' in parents and name='{eventName}'",
                                    includeItemsFromAllDrives=True,
                                    supportsAllDrives=True,
                                    corpora='drive',
                                    driveId='0ADuGDgrEXJMJUk9PVA'
                                    ).execute()
    
    #check if the search returned a result for the teacher-class combo already in drive.
    #If so, get the response URL for the survey
    if len(surveyFileCheck.get('files')) > 0:
        surveyId = surveyFileCheck['files'][0]['id']
        formResponseUrl = formsService.forms().get(formId=surveyId).execute().get('responderUri')
    #if no hits, create a new survey for the teacher-class combo from the master survey template
    #and return the response URL
    else:
        originFileId = '1TG7_qzC728qaDcqZhAZ9NO4B6EtCPuPJd21qh6BemGA' #master survey template fileId
        copiedFileParams = {'name': eventName,
                           'parents': [f"{parentFolderId}"]}
        newSurvey = driveService.files().copy(
            fileId=originFileId, body=copiedFileParams, supportsAllDrives=True).execute()
        newSurveyId = newSurvey.get("id")

        formResponseUrl = formsService.forms().get(formId=newSurveyId).execute().get('responderUri')

    return formResponseUrl

#Import json file with survey links for each teacher-class combo
#When surveys need to be reset (e.g. quarterly), delete this file and move all current surveys to an archive folder
surveyLinkFile = "surveyLinks.json"
try:
    with open(surveyLinkFile, encoding="utf-8") as f:
        surveyLinks = json.load(f)
except: #if survey link file has been deleted to reset links, start over with fresh dict. 
        #Dict will contain nested dict for each teacher.
    surveyLinks = {}

dryRun = False

today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
#Search Neon for all active events that ended yesterday
searchFields = f'''
[
    {{
        "field": "Event End Date",
        "operator": "EQUAL",
        "value": "{yesterday}"
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
    "Event ID"
]
'''

responseEvents = neon.postEventSearch(
    searchFields, outputFields)['searchResults']

logging.info(f"\nBeginning survey emails for {yesterday}\n")
for event in responseEvents:
    eventName = event["Event Name"]
    instructor = event["Event Topic"]
    logging.info(f"{eventName}:")

    #Try to find teacher-class combo survey link in the imported survey links file/surveyLinks dict. If not present, 
    #create using Drive API and update the dict with the survey response URL
    instructorDict = surveyLinks.get(instructor)
    if instructorDict:
        surveyLink = instructorDict.get(eventName)
        if not surveyLink:
            surveyLink = getSurveyLink(eventName)
            instructorDict.update({eventName:surveyLink})
    elif not instructorDict:
        surveyLink = getSurveyLink(eventName)
        surveyLinks[instructor] = {eventName: surveyLink}

    #Get all registrants for the event with a Succeeded registration and populate dict with name and email
    registrants = neon.getEventRegistrants(event["Event ID"])[
        "eventRegistrations"]
    eventDict = {}
    for registrant in registrants:
        if registrant["tickets"][0]["attendees"][0]["registrationStatus"] == "SUCCEEDED":
            firstName = registrant["tickets"][0]["attendees"][0]["firstName"]
            lastName = registrant["tickets"][0]["attendees"][0]["lastName"]
            neonId = registrant["registrantAccountId"]
            fullName = firstName + " " + lastName
            email = neon.getAccountIndividual(
                neonId)["individualAccount"]["primaryContact"]["email1"]
            eventDict[neonId] = [firstName, email]

    for k, v in eventDict.items():
        emailMsg = f'''
            <html>
                <body>
                    <p>Hi {v[0]},</p>
                    <p>We hope you enjoyed your class yesterday!</p>
                    <p>
                        Asmbly is always looking to improve our class offerings. As part of that goal, we hope you will take a minute to respond to a very brief survey about your class.
                    </p>
                    <p><a href={surveyLink} target="_blank">This link</a> will take you to the survey.</p>
                    <p>We really appreciate your help in improving Asmbly!</p>
                    <p>Best, <br>Asmbly Education Team</p>
                </body>
            </html>
            '''
        if not dryRun:
            mimeMessage = MIMEMultipart()
            mimeMessage['To'] = f'{v[1]}'
            mimeMessage['Subject'] = f'Your Feedback is Requested'
            mimeMessage.attach(MIMEText(emailMsg, 'html'))
            raw_string = base64.urlsafe_b64encode(
                mimeMessage.as_bytes()).decode()

            sendMIMEmessage(mimeMessage)
            
        elif dryRun:
            mimeMessage = MIMEMultipart()
            mimeMessage['to'] = f'matthew.miller@asmbly.org'
            mimeMessage['subject'] = f'Your Feedback is Requested'
            mimeMessage.attach(MIMEText(emailMsg, 'html'))
            raw_string = base64.urlsafe_b64encode(
                mimeMessage.as_bytes()).decode()

            sendMIMEmessage(mimeMessage)

#Write surveyLinks dict back to surveyLinks.json to persist any created survey response URLs
with open(surveyLinkFile, 'w', encoding="utf-8") as f:
        json.dump(surveyLinks, f)
