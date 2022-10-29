#Simple script to fetch the Neon account of a single member

import neonUtil
import logging
import sys
from pprint import pprint

logging.basicConfig(level=logging.INFO)

if len(sys.argv) != 2 or not str(sys.argv[1]).isnumeric():
    print(f'''Usage: {sys.argv[0]} <integer NeonID>''')
else:
    neon_account = neonUtil.getMemberById(str(sys.argv[1]), detailed = True)
    pprint(neon_account)
