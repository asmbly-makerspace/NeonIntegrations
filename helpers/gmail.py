import smtplib
import ssl
import logging

from email.mime.multipart import MIMEMultipart

from config import G_user, G_password


#################################################################################
# Sent a MIME email object to its recipient using GMail
#################################################################################
def sendMIMEmessage(MIMEmessage: MIMEMultipart):
    if not "@" in MIMEmessage["To"]:
        raise ValueError("Message doesn't have a sane destination address")

    MIMEmessage["From"] = "Asmbly AdminBot"

    logging.debug(
        "Sending email subject '%s' to %s", MIMEmessage["Subject"], MIMEmessage["To"]
    )

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(G_user, G_password)
            server.send_message(MIMEmessage, G_user)
    except:
        logging.exception(
            "Failed sending email subject '%s' to %s",
            MIMEmessage["Subject"],
            MIMEmessage["To"],
        )
