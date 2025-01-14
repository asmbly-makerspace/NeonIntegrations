import requests
from bs4 import BeautifulSoup
import secrets
import string
import csv
from config import N_user, N_password

###########################################################################################
# This script will generate either event (class) or membership discount codes and output  #
# the resulting codes to a CSV file. To use this script, add your Neon login credentials  #
# to config.py as N_user and N_password (Neon user credentials, not API creds). Update    #
# the global variables VALID_FROM_DATE, VALID_TO_DATE, BASE_STRING, LENGTH_RANDOM,        #
# COUPON_AMOUNT, CSV_CODES_FILE, NUM_COUPONS, and CODE_TYPE to your desired values before #
# running the script. The script is capable of handling accounts with MFA enabled.        #
###########################################################################################

# Coupon validity dates in MM/DD/YYYY format
VALID_FROM_DATE = "11/09/2024"
VALID_TO_DATE = "03/31/2025"
# Prefix of the generated codes
BASE_STRING = "TWF_MEM"
# Length of the randomly generated portion of the code
LENGTH_RANDOM = 7
# Amount in dollars of the discount
COUPON_AMOUNT = 25
CSV_CODES_FILE = "MemCodes.csv"
NUM_COUPONS = 30

# CODE_TYPE can be either "Membership" or "Event"
CODE_TYPE = "Membership"

if CODE_TYPE == "Membership":
    sellingItemType = 2
elif CODE_TYPE == "Event":
    sellingItemType = 3
else:
    sellingItemType = None

if not sellingItemType:
    raise Exception("Invalid sellingItemType, please check your CODE_TYPE variable")


def randomGen(baseString: str, length: int):
    """
    Generates a random string of a specified length and appends it to a base string.

    Args:
        baseString (str): The base string to which the random string will be appended.
        length (int): The length of the random string to be generated.

    Returns:
        str: The base string with the randomly generated string appended to it.
    """
    possibilities = string.ascii_uppercase + string.digits
    randomString = "".join(secrets.choice(possibilities) for _ in range(length))
    return baseString + randomString


defaultHeaders = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/116.0",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.5",
    "accept-encoding": "gzip, deflate, br",
}

# Start a requests session to handle cookie management during the login flow
flow = requests.Session()
flow.headers.update(defaultHeaders)

neon = flow.get("https://app.neonsso.com")
soup = BeautifulSoup(neon.text, "lxml")
csrf_token = soup.select_one('meta[name="csrf-token"]')["content"]
loginInfo = {
    "_token": f"{csrf_token}",
    "email": f"{N_user}",
    "password": f"{N_password}",
}

login = flow.post("https://app.neonsso.com/login", data=loginInfo)

# Additional login flow if MFA is enabled
if login.url != "https://app.neonsso.com/user":
    soup = BeautifulSoup(login.text, "lxml")
    csrf_token = soup.select_one('meta[name="csrf-token"]')["content"]

    mfaCode = input("Enter Neon MFA Code: ")

    mfaInfo = {
        "_token": f"{csrf_token}",
        "trust_device": "true",
        "mfa_code": f"{mfaCode}",
    }

    mfa = flow.post("https://app.neonsso.com/mfa", data=mfaInfo)

    while mfa.url != "https://app.neonsso.com/user":
        print("MFA failed, please try again")
        mfaCode = input("Enter Neon MFA Code: ")

        mfaInfo = {
            "_token": f"{csrf_token}",
            "trust_device": "true",
            "mfa_code": f"{mfaCode}",
        }

        mfa = flow.post("https://app.neonsso.com/mfa", data=mfaInfo)


crmLogin = flow.get("https://app.neoncrm.com/np/ssoAuth")

discountCodesPage = flow.get(
    f"https://asmbly.app.neoncrm.com/np/admin/systemsetting/newCouponCodeDiscount.do?sellingItemType={sellingItemType}&discountType=1"
)

codesList = []

for code in range(NUM_COUPONS):

    couponCodeName = randomGen(BASE_STRING, LENGTH_RANDOM)

    if CODE_TYPE == "Event":
        data = {
            "z2DuplicateRequestToken": "",
            "priceOff": "coupon",
            "currentDiscount.couponCode": f"{couponCodeName}",
            "currentDiscount.sellingItemId": "",
            "currentDiscount.eventTicketPackageGroupId": "",
            "currentDiscount.maxUses": "1",
            "currentDiscount.validFromDate": f"{VALID_FROM_DATE}",
            "currentDiscount.validToDate": f"{VALID_TO_DATE}",
            "currentDiscount.percentageValue": "0",
            "currentDiscount.absoluteDiscountAmount": f"{COUPON_AMOUNT}",
            "submit": "+Save+",
        }

    elif CODE_TYPE == "Membership":
        data = {
            "z2DuplicateRequestToken": "",
            "priceOff": "coupon",
            "currentDiscount.couponCode": f"{couponCodeName}",
            "currentDiscount.sellingItemId": "",
            "currentDiscount.maxUses": "1",
            "currentDiscount.validFromDate": f"{VALID_FROM_DATE}",
            "currentDiscount.validToDate": f"{VALID_TO_DATE}",
            "currentDiscount.percentageValue": "0",
            "currentDiscount.absoluteDiscountAmount": f"{COUPON_AMOUNT}",
            "submit": "+Save+",
        }
    else:
        data = None

    headers = {
        "content-type": "application/x-www-form-urlencoded",
    }

    if data:
        codeGen = flow.post(
            "https://asmbly.app.neoncrm.com/np/admin/systemsetting/couponCodeDiscountSave.do",
            data=data,
            headers=headers,
        )
        codesList.append(couponCodeName)
    else:
        break

if len(codesList) > 0:
    with open(CSV_CODES_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        for code in codesList:
            writer.writerow([code])
