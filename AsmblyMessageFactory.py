from email.mime.text import MIMEText


commonMessageFooter = '''
    - Asmbly AdminBot

----------
To ensure message delivery, please add notification@asmbly.org to your address book

Do not reply to this message, as this email box is not monitored.  To contact Asmbly,
please email membership@asmbly.org'''


def getOpenPathEnableMessage(email, name):
    msg = MIMEText(f'''
    {name},

    As of now, your access to the Asmbly workshop is enabled.  Please email membership@asmbly.org
    if you have any questions about your OpenPath credentials.

    Happy Making!

    {commonMessageFooter}
    ''')
    msg['To'] = email
    msg['Subject'] = "Your Asmbly Facility Access is Enabled"
    return msg

def getOpenPathDisableMessage(email, name):
    msg = MIMEText(f'''
    {name},

    As of now, your access to the Asmbly workshop is disabled.
    If you feel this was in error, please email membership@asmbly.org.

    {commonMessageFooter}
    ''')
    msg['To'] = email
    msg['Subject'] = "Your Asmbly Facility Access is Disabled"
    return msg
