# ATXHS Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  Neon's API appears to only support HTTP GET.  Any API calls that make changes to the system will need to have data passed as parameters in the URL. [Neon API docs](https://developer.neoncrm.com/getting-started/)

## Systems to integrate:
### Discourse 
   - Forum for member discussion 
   - [API docs](https://docs.discourse.org/)
   - `GET` calls only require API key and API user in headers
   - `POST` calls require API key, API user, and content-type in the headers
<br><br>

### Smartwaiver 
   - System for member agreement & waiver forms 
   - [API docs](https://api.smartwaiver.com/docs/v4/#api-_)
   - To authenticate, add 'sw-api-key' to the headers with the API key.
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
This is an open-source project for ATX Hackerspace.  Keep any API tokens or other private information stored in the `/private` directory which is ignored by git.  If you are interested in working on this project with us, please reach out to [it@atxhs.org](mailto:it@atxhs.org).