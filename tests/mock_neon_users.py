"""
Expanded MockNeonUserBuilder used by tests to construct Neon-style account dicts.
"""
import string
import random

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import neonUtil

class MockNeonUserBuilder():
    def __init__(self):
        self.reset()

    def random_alphanumeric(self, length):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def reset(self):
        # TODO: Determine whether Neon IDs are alphanumeric or just numeric
        # canonical internal account id
        self._account_id = self.random_alphanumeric(6)
        self._first_name = "John"
        self._last_name = "Doe"
        self._email = "john@example.com"
        self._individual_types = []
        # OpenPath IDs are numeric in real data; use None to indicate missing
        self._open_path_id = None
        # membership flags and dates mirror neonUtil.getMemberById output
        self._validMembership = False
        self._paidRegular = False
        self._paidCeramics = False
        self._ceramicsMembership = False
        self._WaiverDate = None
        self._FacilityTourDate = None
        self._Account_ID = self._account_id
        # membership raw entries (list of neon-style membership dicts)
        self._memberships = []
        return self

    def with_type(self, neon_type):
        self._individual_types.append({'name': neon_type})
        return self

    def with_random_alta_id(self):
        self._open_path_id = random.randint(1, 100000)
        return self

    def with_alta_id(self, alta_id: int):
        self._open_path_id = alta_id
        return self

    def with_id(self, acct_id: str):
        # keep method name for compatibility; set canonical internal id
        self._account_id = acct_id
        self._Account_ID = acct_id
        return self

    def with_names(self, first: str, last: str):
        self._first_name = first
        self._last_name = last
        return self

    def with_email(self, email: str):
        self._email = email
        return self

    def with_valid_membership(self, valid: bool = True):
        self._validMembership = valid
        return self

    def with_waiver_date(self, date_str: str):
        """Set the WaiverDate field (ISO date string)."""
        self._WaiverDate = date_str
        return self

    def with_tour_date(self, date_str: str):
        """Set the FacilityTourDate field (ISO date string)."""
        self._FacilityTourDate = date_str
        return self

    def with_membership(self, termStartDate: str, termEndDate: str, status: str = "SUCCEEDED", fee: float = 0.0, membershipLevelId: int = None, autoRenewal: bool = False):
        """Append a raw membership entry using Neon API-like keys.

        termStartDate and termEndDate should be ISO date strings (YYYY-MM-DD).
        membershipLevelId corresponds to Neon membership level id (e.g., 1 regular, 7 ceramics).
        """
        membership = {
            'termStartDate': termStartDate,
            'termEndDate': termEndDate,
            'status': status,
            'fee': fee,
            'autoRenewal': autoRenewal,
            'membershipLevel': {'id': membershipLevelId} if membershipLevelId is not None else {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
        self._memberships.append(membership)
        return self

    def with_memberships(self, memberships: list):
        """Accept a list of membership dicts already shaped like the Neon API."""
        for m in memberships:
            self._memberships.append(m)
        return self

    def build(self):
        # Build a dict that resembles the output of neonUtil.getMemberById()
        account = {
            'Account ID': self._Account_ID,
            'fullName': f"{self._first_name} {self._last_name}",
            # Mirror Neon API shape for primary contact
            'primaryContact': {
                'firstName': self._first_name,
                'lastName': self._last_name,
                'email1': self._email,
            },
            # Also expose flattened email location for convenience in scripts
            'Email 1': self._email,
            # Flattened name fields that neonUtil.getMemberById() creates based on primaryContact
            'First Name': self._first_name,
            'Last Name': self._last_name,
            'OpenPathID': self._open_path_id,
            'validMembership': self._validMembership,
            'WaiverDate': self._WaiverDate,
            'FacilityTourDate': self._FacilityTourDate,
            # replicate some of the membership flags neonUtil sets
            'paidRegular': self._paidRegular,
            'paidCeramics': self._paidCeramics,
            'ceramicsMembership': self._ceramicsMembership,
            'individualTypes': self._individual_types,
        }
        # If explicit raw membership entries were provided, synthesize the
        # summary fields that neonUtil.appendMemberships() would populate.
        if len(self._memberships) > 0:
            import datetime

            account['MembershipDetails'] = {'memberships': self._memberships}
            account['membershipDates'] = {}
            lastActiveMembershipExpiration = datetime.date(1970, 1, 1)
            lastCeramicsMembershipExpiration = datetime.date(1970, 1, 1)
            lastActiveMembershipTier = neonUtil.MEMBERSHIP_ID_REGULAR
            firstActiveMembershipStart = neonUtil.today
            firstCeramicsMembershipStart = neonUtil.today
            atLeastOneActiveMembership = False
            currentMembershipStatus = "No Record"

            for membership in self._memberships:
                membershipExpiration = datetime.datetime.strptime(membership['termEndDate'], "%Y-%m-%d").date()
                membershipStart = datetime.datetime.strptime(membership['termStartDate'], "%Y-%m-%d").date()
                membershipLevelId = int(membership.get('membershipLevel', {}).get('id', neonUtil.MEMBERSHIP_ID_REGULAR))

                if membershipExpiration >= neonUtil.today and membershipStart <= neonUtil.today:
                    currentMembershipStatus = membership['status']

                if membership['status'] == 'SUCCEEDED':
                    account['membershipDates'][membership['termStartDate']] = [membership['termEndDate'], membershipLevelId]
                    atLeastOneActiveMembership = True

                    if membershipExpiration > lastActiveMembershipExpiration:
                        lastActiveMembershipExpiration = membershipExpiration
                        lastActiveMembershipTier = membershipLevelId
                        account['autoRenewal'] = membership.get('autoRenewal')

                    if membershipLevelId == neonUtil.MEMBERSHIP_ID_CERAMICS and membershipExpiration > lastCeramicsMembershipExpiration:
                        lastCeramicsMembershipExpiration = membershipExpiration

                    if membershipStart < firstActiveMembershipStart:
                        firstActiveMembershipStart = membershipStart
                        if membershipLevelId == neonUtil.MEMBERSHIP_ID_CERAMICS:
                            firstCeramicsMembershipStart = membershipStart

                    if membershipExpiration >= neonUtil.today and membershipStart <= neonUtil.today:
                        account['validMembership'] = True
                        if membershipLevelId == neonUtil.MEMBERSHIP_ID_CERAMICS:
                            account['ceramicsMembership'] = True
                            if membership.get('fee', 0) == 0:
                                account['compedCeramics'] = True
                            else:
                                account['paidCeramics'] = True
                        else:
                            if membership.get('fee', 0) == 0:
                                account['compedRegular'] = True
                            else:
                                account['paidRegular'] = True

            if atLeastOneActiveMembership:
                account['Membership Start Date'] = str(firstActiveMembershipStart)
                account['Ceramics Start Date'] = str(firstCeramicsMembershipStart)
                account['Ceramics Expiration Date'] = str(lastCeramicsMembershipExpiration)
                account['Membership Expiration Date'] = str(lastActiveMembershipExpiration)

            if (not account.get('validMembership', False) and lastActiveMembershipExpiration == neonUtil.yesterday):
                if account.get('autoRenewal') == True and currentMembershipStatus == 'No Record':
                    account['validMembership'] = True
                    account['ceramicsMembership'] = (lastActiveMembershipTier == neonUtil.MEMBERSHIP_ID_CERAMICS)

        # Do not add legacy aliases here; tests should use canonical Neon fields.
        return account
