# ATXHS Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  [Neon API docs](https://developer.neoncrm.com/api-v2/#/)

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
#### Needs to be set to relative date range and setup on a monitored cron job.

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
- We will need to research how to interact with this system
<br><br>

### Skedda

- Scheduling system for booking time at the space
- Checked with CSM about API, they have integrations through Zapier, but no direct access endpoint.  May be able to reverse engineer to figure out endpoints and methods
<br><br>

<hr>

## About this repo

This is an open-source project for ATX Hackerspace.  Keep any API tokens or other private information should be stored in the `/private` directory which is ignored by git.  If you are interested in working on this project with us, please reach out to [it@atxhs.org](mailto:it@atxhs.org).
