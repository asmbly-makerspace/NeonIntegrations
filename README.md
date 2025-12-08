# Asmbly Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  Completed scripts ready to set for automation are saved in the root directory.  Scripts in `/examples` are work in progress.  

## How to contribute:

First, thanks for collaborating! If you're looking for things to help with, check out the recent github issues. To get started with making changes, fork the repo to your own account, clone it locally, and create a branch.

Next, you'll need install the project dependencies. We recommend using [virutal environments](https://docs.python.org/3/library/venv.html) to avoid modifying your global system when installing project-specific dependencies. After activating an environment in your local repo, install dependencies from `requirements.txt`:

```
pip install -r requirements.txt
```

`requirements.txt` is also used to set up the environment in AWS, so if you add any new dependencies, make sure to update it as well.

After that, you can run all unit tests, which should pass:

```
pytest
```

Make sure to add new unit tests for each new change, to verify the code works the way you expect it to.

Once your changes are ready, push to your fork, and then send us a pull request. We will review it, and if it looks good, we'll merge and deploy it! You can also keep your fork in sync with the main repository by adding [an upstream origin](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork).

NOTE: To run all the scripts in production mode, you will need to create a separate file `config.py` with API keys (this will be ignored by git). Variables used are
`D_APIkey`, `D_APIuser`, `G_password `, `G_user`, `N_APIkey`, `N_APIuser`, `O_APIkey`, `O_APIuser`, and `S_APIkey`.

## Systems:

### Neon
- CRM storing information about all memebers
- [API docs](https://developer.neoncrm.com/api-v2/#/)

### Discourse

- Forum for member discussion
- [API docs](https://docs.discourse.org/)
- `GET` calls only require API key and API user in headers
- `POST` calls require API key, API user, and content-type in the headers
- Neon -> Discourse to update Discourse group membership

### OpenPath

- Used for access into the space
- [API docs](https://openpath.readme.io/docs/basics-to-start)

### Skedda

- Scheduling system for booking time at the space
- Checked with CSM about API, they have integrations through Zapier, but no direct access endpoint
- We will need to explore SSO/SAML options for user management (info [here](https://support.skedda.com/en/articles/4191038-single-sign-on-sso-via-saml-2-0))

<hr>

## Deployment:

Here is how to update our automations from the code in this repo:
- `alta_open_lambda`: Pushing to the `main` branch on github will automatically trigger github actions that will deploy the AWS lambda. See the `.github` folder for the action definitions.
- The other scripts are run from systemd timers on an ec2 instance named AdminBot2025. They can be redeployed by connecting to the instance and running `git pull origin main` in the `/home/ec2-user/NeonIntegrations` directory. Ideally github actions should update them automatically too, but that's not working at the moment.

## Logging:

All logs from the scripts are recorded in AWS cloudwatch. The log group for alta-open-update is named `/aws/lambda/alta-open-update`, and the other scripts are prefixed with `/admin-bot/` (`/admin-bot/attendance-to-testout` contains the logs for `attendanceToTestout.py`).

For systemd timers, logging is configered by redirecting stdout and stdin to a dedicated logging file for each timer, which is then tailed and uploaded by amazon cloudwatch agent. On adminbot, see the systemd configeration files and `/home/ec2-user/robz` for how to update it.

## Entrypoints:

Here are the scripts that are currently being executed by our automation. Note that the triggers for these automations are configered in asmbly's AWS account, not in this repo.

### alta_open_lambda

- Triggered by Neon webhooks that are called whenever Neon accounts are updated, created, and deleted
- Synced information from the Neon account to openpath and discourse. For example, it will update a user's openpath account to give them access to the space if a user has met all the criteria.

### dailyMaintenance.py

- Triggered daily by systemd timer asmbly-daily-maintenance.service
- Similar to `alta_open_lambda`, it syncs **all** accounts from neon -> OpenPath, discourse, and Mailjet.

### attendanceToTestout.py

- Triggered every 3 hours by systemd timer tool-testing-update.service
- Sets FacilityTourDate field on a user's Neon profile by checking whether they attended a recent orientation

### dailyClassChecker.py

- Triggered daily by systemd timer internal-class-checker.service
- Emails classes@ with list of scheduled classes

### dailyClassReminder.py

- Triggered daily by systemd timer class-reminders.service
- Email teachers with classes they're teaching that day

### classFeedbackAutomation.py

- Triggered daily by systemd timer class-feedback.service
- Email students who completed yesterday's classes with feedback surveys

## About this repo

This is an open-source project for Asmbly Makerspace, Inc. 501(c)3.  Keep any API tokens or other private information should be stored in the `/private` directory or `config.py` both of which are ignored by git.  If you are interested in working on this project with us, please reach out to [it@asmbly.org](mailto:it@asmbly.org).
