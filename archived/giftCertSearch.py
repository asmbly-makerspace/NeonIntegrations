import sys
import helpers.neon as neon


def giftCertSearch(certNumber):
    searchFields = [
        {"field": "Shopping Cart ID", "operator": "EQUAL", "value": str(certNumber)}
    ]

    outputFields = ["Account ID", "First Name", "Last Name", "Email 1"]

    response = neon.postOrderSearch(searchFields, outputFields)

    searchResults = response.get("searchResults")

    return searchResults


def main():
    if len(sys.argv) != 2 or not str(sys.argv[1]).isnumeric():
        print(f"""Usage: {sys.argv[0]} <integer Gift Certificate Number>""")
    else:
        gift_cert_num = sys.argv[1]
    holder = giftCertSearch(gift_cert_num)
    print(holder)


if __name__ == "__main__":
    main()
