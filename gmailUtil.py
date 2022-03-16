import smtplib, ssl, logging

from config import G_user, G_password

#################################################################################
# Sent a MIME email object to its recipient using GMail
#################################################################################
def sendMIMEmessage(MIMEmessage):
    if not "@" in MIMEmessage['To']:
        raise ValueError("Message doesn't have a sane destination address")

    MIMEmessage['From'] = "Asmbly AdminBot"

    logging.debug(f'''Sending email subject "{MIMEmessage['Subject']}" to {MIMEmessage['To']}''')

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(G_user, G_password)
            server.sendmail(G_user, MIMEmessage['To'], MIMEmessage.as_string())
    except:
        logging.exception(f'''Failed sending email subject "{MIMEmessage['Subject']}" to {MIMEmessage['To']}''')
