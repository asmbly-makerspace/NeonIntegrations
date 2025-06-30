################## Asmbly Neon API Integrations ###################
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

import pdb
import openPathUtil
import neonUtil
import logging
import argparse



def getParserArgs():
    parser = argparse.ArgumentParser(
        prog='Alta User Audit',
        description='Help find users who have an entry in the Alta database, but are not supported by an entry in Neon.',
    )
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    return args


def getLogger(verbose=True):
    logLevel = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logLevel,
        datefmt='%Y-%m-%d %H:%M:%S')
    return logging.getLogger(__name__)


def main():
    args = getParserArgs()
    log = getLogger(args.verbose)

    # Get the list of users from the Alta database
    altaUsers = openPathUtil.getAllUsersMock()
    neonUsers = neonUtil.getRealAccountsMock()

    # Find all users in Alta who _are not_ in Neon
    extraAltaUsers = []
    for uid, user in altaUsers.items():
        match = False
        log.debug(f'Checking for Alta user {uid}')
        for nuid, neonUser in neonUsers.items():
            log.debug(f'Comparing Alta user {uid} to Neon user {nuid}')
            opid = neonUser.get('OpenPathID')
            log.debug(f'Neon user {nuid} has OpenPathID {opid}')
            if opid and int(uid) == int(opid):
                match = True
                log.debug(f'Alta user {uid} is Neon user {neonUser.get("fullName")} ({nuid})')
                continue
            else:
                log.debug('No match')
        if not match:
            log.debug('No match found for {uid}')
            extraAltaUsers.append(uid)

    # Display
    if len(extraAltaUsers) == 0:
        log.info('All users in Alta are supported by a Neon entry')
    else:
        log.info('The following Alta users are not found in Neon:')
        for uid in extraAltaUsers:
            log.info(f'{uid}: {altaUsers[uid]}')


if __name__ == '__main__':
    main()
