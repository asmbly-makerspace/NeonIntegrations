# Asmbly Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  Completed scripts ready to set for automation are saved in the root directory.  Nothing in these folders is run by our automations:

- `WIP/` - scripts that are still a work in progress
- `examples/` - one-off and example scripts for exploring the APIs
- `archived/` - retired scripts kept for reference
- `it_volunteer_day/` - exploratory Neon query scripts and saved API responses

## How to contribute:

First, thanks for collaborating! If you're looking for things to help with, check out the recent github issues. To get started with making changes, fork the repo to your own account, clone it locally, and create a branch.

Next, you'll need to install the project dependencies. We recommend using [virtual environments](https://docs.python.org/3/library/venv.html) to avoid modifying your global system when installing project-specific dependencies. Use Python 3.12, which is what CI and the EC2 instance run. After activating an environment in your local repo, install dependencies from `requirements.txt`:

```
pip install -r requirements.txt
```

The Python version and dependency file depend on where the code runs:

| Where | Python | Dependencies installed from |
|---|---|---|
| EC2 instance (systemd timers) | 3.12 | `requirements.txt` |
| GitHub Actions tests (`.github/workflows/test.yml`) | 3.12 | `requirements.txt` |
| `alta_open_lambda` (Docker image) | 3.13 | `pyproject.toml` and `uv.lock` |

The dependency lists in `pyproject.toml` (which requires Python 3.13 or newer) and `uv.lock` are only used to build the Lambda image. `pytest` also reads its settings from the `[tool.pytest.ini_options]` section of `pyproject.toml`, so that file matters for the tests too. `.python-version` says 3.13 to match the Lambda, and tools such as uv and pyenv will pick it up, so ask for 3.12 explicitly when you create your environment (for example `python3.12 -m venv <dir>` or `uv venv --python 3.12`; uv will warn that 3.12 does not match `requires-python`, which is expected).

If you add any new dependencies, make sure to update both `requirements.txt` and `pyproject.toml`, then run `uv lock` (needs [uv](https://docs.astral.sh/uv/)) and commit the updated `uv.lock`. The Lambda image is built with `uv export --frozen`, which uses `uv.lock` as it is, so a package added to `pyproject.toml` without re-locking is silently left out of the Lambda.

After that, you can run all unit tests, which should pass:

```
pytest
```

Make sure to add new unit tests for each new change, to verify the code works the way you expect it to.

Once your changes are ready, push to your fork, and then send us a pull request. We will review it, and if it looks good, we'll merge and deploy it! You can also keep your fork in sync with the main repository by adding [an upstream origin](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork).

## Configuration:

You do not need any credentials to run the unit tests. `tests/conftest.py` supplies fake values and blocks network access.

When a script starts, it picks where to read its API credentials from:

- When the `USER` environment variable is `ec2-user` (the EC2 instance) or `LAMBDA_TASK_ROOT` is set (the Lambda), they are read from AWS SSM Parameter Store by `aws_ssm.py`.
- Anywhere else, such as your own computer, they are read from a `config.py` file in the repo root that you create yourself (it is ignored by git). The variables the current scripts use are `N_APIkey`, `N_APIuser` (Neon), `O_APIkey`, `O_APIuser` (OpenPath), `D_APIkey`, `D_APIuser` (Discourse), `G_user` and `G_password` (Gmail).

Mailjet is the exception. `dailyMaintenance.py` (through `mailjetUtil.run_mailjet_maintenance()`) and `alta_open_lambda` always read `/mailjet/api_key` and `/mailjet/api_secret` from SSM with boto3. There is no `config.py` fallback, even on your own computer. So a local run of `dailyMaintenance.py` uses whatever AWS credentials and region your machine is set up with, which could be Asmbly's production account. Without AWS credentials it fails at the Mailjet step, after it has already made its Neon, OpenPath and Discourse changes.

Some scripts also need files that hold private data. These files are ignored by git, so they are not in this repo. The scripts open them by relative path, so they must be in the directory the script runs from:

- `teachers.json` - read by `dailyClassReminder.py`. Maps each teacher's name, as entered in the Neon event's "Event Topic" field, to their email address.
- `classFeedbackServiceAccountKey.json` - Google service account key that `classFeedbackAutomation.py` uses for the Google Drive and Forms APIs (with domain-wide delegation, acting as admin@asmbly.org).
- `surveyLinks.json` - read and rewritten by `classFeedbackAutomation.py`. It stores the survey link for each teacher and class. If it is missing, the script starts a new one.

## Systems:

### Neon
- CRM storing information about all members
- [API docs](https://developer.neoncrm.com/api-v2/#/)

### Discourse

- Forum for member discussion
- [API docs](https://docs.discourse.org/)
- `GET` calls only require API key and API user in headers
- `POST` calls require API key, API user, and content-type in the headers
- Neon -> Discourse to update Discourse group membership
- Discourse -> Neon to keep the `DiscourseID` field in Neon matched to the right Discourse user (matched by email)

### OpenPath

- Used for access into the space
- [API docs](https://openpath.readme.io/docs/basics-to-start)

### Mailjet

- Email marketing lists
- [API docs](https://dev.mailjet.com/email/guides/)
- Neon -> Mailjet to add contacts to the `AllContacts` and `NewMembers` lists
- Credentials always come from AWS SSM (see Configuration above)

### Gmail and Google Workspace

- Outgoing emails (class reminders, the class schedule, feedback surveys, daily subscriber reports) are sent through Gmail SMTP using `G_user` and `G_password`
- `classFeedbackAutomation.py` also uses the Google Drive and Forms APIs to create a feedback survey for each class

### Skedda

- Not integrated. These are notes from earlier research.
- Scheduling system for booking time at the space
- Checked with CSM about API, they have integrations through Zapier, but no direct access endpoint
- We will need to explore SSO/SAML options for user management (info [here](https://support.skedda.com/en/articles/4191038-single-sign-on-sso-via-saml-2-0))

<hr>

## Deployment:

Here is how to update our automations from the code in this repo:
- `alta_open_lambda`: Pushing to the `main` branch on github will automatically trigger github actions that will deploy the AWS lambda. The action builds a Python 3.13 Docker image from `alta_open_lambda/Dockerfile` (dependencies from `uv.lock`) and deploys it to the `alta-open-update` function. See the `.github` folder for the action definitions.
- The other scripts are run from systemd timers on an ec2 instance named AdminBot2025. They can be redeployed by connecting to the instance, going into the `/home/ec2-user/NeonIntegrations` directory, pulling the main branch, and installing any new dependencies:

```
cd /home/ec2-user/NeonIntegrations
git pull origin main
pip3.12 install -r requirements.txt
```

(Ideally github actions should update them automatically too, but that's not working at the moment. `.github/workflows/ec2_deploy.yml` runs on every push to `main` and shows as successful, but it does not update the code on the instance. See [#64](https://github.com/asmbly-makerspace/NeonIntegrations/issues/64). The workflow only queues `git checkout main` and `git pull` with `aws ssm send-command`, does not check whether they worked, and never installs dependencies. Until that is fixed, run the steps above by hand after each merge.)


## Logging:

All logs from the scripts are recorded in AWS cloudwatch. The log group for alta-open-update is named `/aws/lambda/alta-open-update`, and the other scripts are prefixed with `/admin-bot/` (`/admin-bot/attendance-to-testout` contains the logs for `attendanceToTestout.py`).

For systemd timers, logging is configured by redirecting stdout and stderr to a dedicated logging file for each timer, which is then tailed and uploaded by amazon cloudwatch agent. On adminbot, see the systemd configuration files and `/home/ec2-user/robz` for how to update it.

## Entrypoints:

Here are the scripts that are currently being executed by our automation. Note that the triggers for these automations are configured in asmbly's AWS account, not in this repo.

### alta_open_lambda

- Triggered by Neon webhooks. It acts on `createMembership`, `updateMembership`, `deleteMembership`, `editAccount` and `mergedAccount` events. `updateEventRegistration` events are logged and otherwise ignored, as are any other event types. Webhooks that arrive between 2:30 and 5:00 AM Central time are skipped.
- For each event it acts on, it looks up the Neon account and creates or updates that user in OpenPath (`openPathUpdateSingle.py`). For example, it will update a user's openpath account to give them access to the space if a user has met all the criteria.
- For a successful `JOIN` or `REJOIN` `createMembership` that starts today (a first membership, or one starting at least 365 days after the previous one ended), it also adds the member to the Mailjet `NewMembers` and `AllContacts` lists. This only happens if the Neon account already has a `FacilityTourDate`, an email, a first and last name, and a `MailjetContactID`.
- It does not touch Discourse.

### dailyMaintenance.py

- Triggered daily by systemd timer asmbly-daily-maintenance.service
- Similar to `alta_open_lambda`, it syncs **all** accounts from neon -> OpenPath, discourse, and Mailjet.
- It also matches Discourse users to Neon accounts by email and updates the `DiscourseID` field in Neon.
- When it runs before about 6 AM Central time, it emails the daily subscriber report to membership@asmbly.org and a summary to membership.committee@asmbly.org.

### attendanceToTestout.py

- Triggered every 3 hours by systemd timer tool-testing-update.service
- For Neon events that ended in the last 7 days and are not archived, it finds registrants marked as attended and sets the matching date field on their Neon account to the event's end date. The class names and field IDs are in `EVENT_FIELDS` in the script (for example Orientation sets `FacilityTourDate`, and Woodshop Safety, Big Lasers and CSI each set their own field). Fields that already have a value are left alone.
- Attendance that is marked more than 7 days after a class ends is not picked up and has to be entered by hand (see [#104](https://github.com/asmbly-makerspace/NeonIntegrations/issues/104)).

### dailyClassChecker.py

- Triggered daily by systemd timer internal-class-checker.service
- Emails classes@ with list of scheduled classes

### dailyClassReminder.py

- Triggered daily by systemd timer class-reminders.service
- Emails each teacher, with classes@asmbly.org on CC, about the classes they teach that start today or in the next two days. Teacher addresses come from `teachers.json`. Reminders for classes with no teacher, or for a teacher missing from that file, go to classes@asmbly.org instead.

### classFeedbackAutomation.py

- Triggered daily by systemd timer class-feedback.service
- For Neon events that ended yesterday, emails everyone with a successful registration (attendance is not checked) a link to a Google Forms feedback survey for that class and teacher. A copy of each email also goes to classes@asmbly.org.
- The first time a class and teacher pair needs a survey, it reuses a survey with the same name in the Google Drive survey folder or copies the template survey. Survey links are kept in `surveyLinks.json`.

## About this repo

This is an open-source project for Asmbly Makerspace, Inc. 501(c)3.  Any API tokens or other private information should be stored in the `/private` directory or `config.py`, both of which are ignored by git.  If you are interested in working on this project with us, please reach out to [it@asmbly.org](mailto:it@asmbly.org).
