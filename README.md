# Asmbly Neon Integrations

In attempts to further simplify our administrative operations so that we can focus on making cool stuff rather than route work, we're working to integrate our member management software - NeonCRM - with all our other systems.  Completed scripts ready to set for automation are saved in the root directory.  Scripts in `/examples` are work in progress.  

## How to contribute:

First, thanks for collaborating! If you're looking for things to help with, check out the recent github issues. To get started with making changes, fork the repo to your own account, clone it locally, and create a branch.

Next, you'll need install the project dependencies. We recommend using [virutal environments](https://docs.python.org/3/library/venv.html) to avoid modifying your global system when installing project-specific dependencies. After activating an environment in your local repo, install dependencies from `requirements.txt`:

```
pip install -r requirements.txt
```

`requirements.txt` and `pyproject.toml` are both used to set up the environment in AWS, so if you add any new dependencies, make sure to update both of them.

After that, you can run all unit tests, which should pass:

```
pytest
```

Make sure to add new unit tests for each new change, to verify the code works the way you expect it to.

Once your changes are ready, push to your fork, and then send us a pull request. We will review it, and if it looks good, we'll merge and deploy it! You can also keep your fork in sync with the main repository by adding [an upstream origin](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork).

NOTE: To run all the scripts in production mode, you will need to create a separate file `config.py` with API keys (this will be ignored by git). Variables used are
`D_APIkey`, `D_APIuser`, `G_password `, `G_user`, `N_APIkey`, `N_APIuser`, `O_APIkey`, `O_APIuser`, and `S_APIkey`.
To run `attendanceToTestout.py` locally, also set `N_classFieldsFile` to the path of a class-to-field JSON file (see [Class-to-field table](#class-to-field-table-neonclass_fields)), for example:

```
mkdir -p private
python scripts/class_fields_seed.py > private/class_fields.json
# then in config.py:
N_classFieldsFile = "private/class_fields.json"
```

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
- The other scripts are run from systemd timers on an ec2 instance named AdminBot2025. They can be redeployed by connecting to the instance, going into the `/home/ec2-user/NeonIntegrations` directory, pulling the main branch, and installing any new dependencies:

```
cd /home/ec2-user/NeonIntegrations
git pull origin main
pip3.12 install -r requirements.txt
```

(Ideally github actions should update them automatically too, but that's not working at the moment.)


## Class-to-field table (`/neon/class_fields`)

`attendanceToTestout.py` gives people a sign-off when they attend a class: it writes the class date into a Neon account custom field. Which class goes with which field comes from one SSM parameter, so adding a class type is a parameter change, not a code change or deploy. The AsmblyMCPs account checkup tool reads the same parameter to explain a missing sign-off, so both always agree.

- Name `/neon/class_fields`, region `us-east-2`, Standard tier, type `String` (not secret).
- Read once at the start of every run. A change takes effect on the next run (the timer runs every 3 hours).
- If the parameter is missing, unreadable or invalid, the run logs one `ERROR` saying what is wrong and that no sign-offs were written, then exits with a non-zero status. There is no built-in fallback copy.

### Format

```json
{
  "version": 1,
  "fields": [
    ["Festool Domino", "440"],
    ["Woodshop Safety", "84"],
    ["CSI", "1248"]
  ]
}
```

Each entry is `[class phrase, Neon custom field ID]`. If an event name contains the phrase (case-sensitive), attendees get that field. **Order matters**: the first phrase in the list found in the event name wins, so put a more specific phrase before a shorter one it contains.

The whole value is rejected if any rule fails:

- `version` is `1`;
- `fields` has 1 to 200 entries, each a list of exactly two strings;
- phrase: 1 to 64 ASCII characters, made of letters, digits and `& ( ) + , . / : ' -`, with single spaces between words (regex `^[A-Za-z0-9&()+,./:'-]+( [A-Za-z0-9&()+,./:'-]+)*$`);
- field ID: 1 to 9 digits with no leading zero (regex `^[1-9][0-9]{0,8}$`), in quotes;
- no phrase appears twice (case-sensitive: `CSI` and `csi` are different phrases);
- the object has no keys other than `version` and `fields`.

### Adding or changing a class

**A change writes real sign-off dates to member accounts on the next run.** A wrong but valid-looking field ID sends sign-offs to the wrong field, so double-check the ID against the custom field in Neon before saving.

With the AWS CLI:

```
aws ssm get-parameter --profile asmbly --region us-east-2 --name /neon/class_fields \
  --query Parameter.Value --output text > class_fields.json
# edit class_fields.json
python -c "from helpers.class_fields import parseClassFields; print(len(parseClassFields(open('class_fields.json').read())), 'entries OK')"
aws ssm put-parameter --profile asmbly --region us-east-2 --name /neon/class_fields \
  --type String --overwrite --value file://class_fields.json
```

The `python -c` line runs the same validation the sync uses, from the repo root.

In the AWS console: Systems Manager > Parameter Store (region US East (Ohio)) > `/neon/class_fields` > Edit, change the value, Save changes. Keep it valid JSON; the console does not check it.

Then check the next run's log in CloudWatch (`/admin-bot/attendance-to-testout`) for `Loaded N class-to-field entries`.

### History and rollback

Every change is kept as a version (Standard tier keeps the last 100), and CloudTrail records who made it.

```
aws ssm get-parameter-history --profile asmbly --region us-east-2 --name /neon/class_fields \
  --query 'Parameters[].{Version:Version,Modified:LastModifiedDate,By:LastModifiedUser}' --output table
aws ssm get-parameter --profile asmbly --region us-east-2 --name /neon/class_fields:3 \
  --query Parameter.Value --output text > class_fields_v3.json
aws ssm put-parameter --profile asmbly --region us-east-2 --name /neon/class_fields \
  --type String --overwrite --value file://class_fields_v3.json
```

Rolling back puts the old value back as a new version. Sign-offs already written by the bad version stay on the accounts and have to be fixed in Neon.

`scripts/class_fields_seed.py` prints the table as it was hard-coded before the move; it was only used to create the parameter.

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
- Also sets the sign-off field for each tool/safety class attended, using the [class-to-field table](#class-to-field-table-neonclass_fields)

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
