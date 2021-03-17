# ATXHS Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  Completed scripts ready to set for automation are saved in the root directory.  Scripts in `/examples` are work in progress.  

### [Neon API docs](https://developer.neoncrm.com/api-v2/#/)

<br>
<hr>

## How to contribute:

First, thanks for collaborating!  If you are part of the organization, please create a branch to work then submit a pull request to main.  If you are outside the organization, we still welcome your collaboration!  Just fork the repo, then submit a pull request.

NOTE:  You will need to create a separate file `config.py` with API keys (this will be ignored by git).  Variables used are `N_APIkey`, `N_APIuser`, `D_APIkey`, `D_APIuser`, and `S_APIkey`.

<br>
<hr>

## Systems to integrate:

### Discourse

- Forum for member discussion
- [API docs](https://docs.discourse.org/)
- `GET` calls only require API key and API user in headers
- `POST` calls require API key, API user, and content-type in the headers
- Neon -> Discourse to update Discourse group membership
<br><br>

### Smartwaiver - COMPLETED

See [SWintegration.py](https://github.com/ATXHS/NeonIntegrations/blob/main/SWintegration.py).  
#### Needs to be set to run on a schedule.  Could be a monitored cron job or something else (AWS Lambda?).

- System for member agreement & waiver forms
- [API docs](https://api.smartwaiver.com/docs/v4/#api-_)
- To authenticate, add 'sw-api-key' to the headers with the API key.
- Smartwaiver -> Neon to update WaiverCompleted custom field in Neon
  - Smartwaiver - `GET` `/v4/waivers`
    - https://api.smartwaiver.com/docs/v4/#api-Search-Search
  - Neon - `PATCH` `/accounts/{id}`
    - https://api.smartwaiver.com/docs/v4/#api-Waivers-WaiverList
<br><br>

### Key fob system

- Used for access into the space
- We will need to research how to interact with this system (system change for better integration is in the works)
<br><br>

### Skedda

- Scheduling system for booking time at the space
- Checked with CSM about API, they have integrations through Zapier, but no direct access endpoint
- We will need to explore SSO/SAML options for user management (info [here](https://support.skedda.com/en/articles/4191038-single-sign-on-sso-via-saml-2-0))
<br><br>

<hr>



## About this repo

This is an open-source project for ATX Hackerspace.  Keep any API tokens or other private information should be stored in the `/private` directory or `config.py` both of which are ignored by git.  If you are interested in working on this project with us, please reach out to [it@atxhs.org](mailto:it@atxhs.org).
