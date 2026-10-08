# Host the Asmbly MCP server on AWS

This puts the server on AWS so everyone in the Asmbly org on claude.ai can use it. People sign in with Google, and only `@asmbly.org` accounts get in.

You do the setup once. After that, updating is two commands or one button.

## What gets created

Everything is defined in [infra/template.yaml](infra/template.yaml):

| AWS resource | What it's for |
|---|---|
| A Lambda function, `asmbly-mcp` | Runs the server |
| A public HTTPS address for it | What claude.ai connects to |
| A DynamoDB table | Remembers who is signed in. Holds no member data. |
| A log group, kept 90 days | The server's logs |
| A role with three permissions | Read the six keys, use the table, look up its own address |

It should cost very little. Everything is pay-per-use and this gets light use.

## Before you start

You need three things on the computer you deploy from:

- **AWS CLI**, signed in to the Asmbly AWS account with permission to create the resources above (an admin login works)
- **AWS SAM CLI** ([install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- **Docker**, running

And two people's worth of access, which may be the same person:

- A **Google Workspace admin** for asmbly.org, to create the sign-in client
- A **claude.ai Owner** for the Asmbly org, to add the connector

## Step 1: Create the Google sign-in client

This is what lets the server offer "Sign in with Google".

1. Go to the [Google Cloud console](https://console.cloud.google.com/), signed in with your asmbly.org admin account.
2. Create a project. Name it `Asmbly MCP`. Make sure the organization is **asmbly.org**.
3. Open **Google Auth Platform** (search for it in the top bar) and click **Get started**.
   - App name: `Asmbly MCP`
   - Audience: **Internal**. This is important: it means only asmbly.org accounts can sign in at all.
4. Go to **Clients**, click **Create client**.
   - Application type: **Web application**
   - Name: `Asmbly MCP server`
   - Leave the redirect URIs empty for now. You add one in Step 4.
5. Copy the **Client ID** and **Client secret**. You need them in the next step.

Google moves these menus around from time to time. If the names don't match, look for "OAuth consent screen" and "Credentials".

## Step 2: Put the two Google values in Parameter Store

1. In the [AWS console](https://console.aws.amazon.com/), switch to region **us-east-2 (Ohio)** in the top-right corner.
2. Search for **Parameter Store** and open it.
3. Click **Create parameter** twice:

| Name | Type | Value |
|---|---|---|
| `/asmbly-mcp/google_client_id` | String | The Client ID from Step 1 |
| `/asmbly-mcp/google_client_secret` | **SecureString** | The Client secret from Step 1 |

The four Neon and Alta Open parameters (`/neon/api_user`, `/neon/api_key`, `/altaopen/api_user`, `/altaopen/api_key`) are already there, because the door sync uses them.

## Step 3: Deploy

From the repo:

```
cd asmbly_mcp/infra
sam build
sam deploy
```

`sam deploy` shows what it is about to create and asks you to confirm. Type `y`.

If a parameter from Step 2 is missing or misnamed, the deploy stops and says which one.

When it finishes, it prints two values under **Outputs**. Keep them:

- **ConnectorUrl** (ends in `/mcp`)
- **GoogleRedirectUri** (ends in `/auth/callback`)

## Step 4: Tell Google where to send people back

1. Back in the Google Cloud console, open **Google Auth Platform > Clients** and click the client from Step 1.
2. Under **Authorized redirect URIs**, click **Add URI** and paste the **GoogleRedirectUri** exactly.
3. Save.

## Step 5: Add it to claude.ai

A claude.ai **Owner** does this once for the org:

1. Go to **Organization settings > Connectors**.
2. Click **Add**, then **Custom**. If it asks for a type, choose **Web**.
3. Name it `Asmbly` and paste the **ConnectorUrl**.
4. Leave the sign-in settings as Claude detects them, and save.

Then each person who wants to use it:

1. Goes to **Customize > Connectors** in claude.ai, finds **Asmbly** and clicks **Connect**.
2. Signs in with their asmbly.org Google account.

## Step 6: Try it

In a new chat on claude.ai:

> Check door access for jane@example.com

---

## Updating later

After code changes are merged to `main`, either:

- run `sam build` and `sam deploy` again from `asmbly_mcp/infra`, or
- in GitHub, open **Actions > Deploy Asmbly MCP server > Run workflow**.

The GitHub button uses the same AWS role as the other deploy workflows (`AWS_GITHUB_ACTIONS_ROLE`). That role doesn't have permission to deploy this stack until someone adds it: CloudFormation, Lambda, IAM roles, DynamoDB, CloudWatch Logs and ECR for the `asmbly-mcp` stack, plus read access to the six parameters. Until then, deploy from a computer.

## Using read-only keys

By default the server uses the same Neon and Alta Open keys as the door sync. The server only reads, but those keys can also write. If you create read-only API users in Neon and Alta Open, store their keys under new parameter names and point the server at them:

```
sam deploy --parameter-overrides \
  NeonApiUserParam=/asmbly-mcp/neon_api_user NeonApiKeyParam=/asmbly-mcp/neon_api_key \
  AltaApiUserParam=/asmbly-mcp/altaopen_api_user AltaApiKeyParam=/asmbly-mcp/altaopen_api_key
```

## How access is controlled

- The server's address is public, because Claude connects from Anthropic's servers. Every request to the tools still needs a valid sign-in.
- Sign-in is Google only. On every request the server checks with Google that the account has a verified `@asmbly.org` email. Anything else is refused.
- The "Internal" setting from Step 1 is a second lock: Google itself won't sign in accounts outside asmbly.org.
- Everyone who can sign in can look up any member's door access status. If that should be a smaller group, say so before rolling it out; the rule lives in `asmbly_mcp/auth.py`.
- The logs record who used which tool, not who they looked up.

## Troubleshooting

| Problem | What to do |
|---|---|
| `sam deploy` says a parameter doesn't exist | Check the name and that you're in region us-east-2 (Step 2). |
| Google says `redirect_uri_mismatch` | The URI in Step 4 doesn't match exactly. Paste the **GoogleRedirectUri** output again. |
| Google says the app is restricted to its organization | That's the "Internal" lock working. Sign in with an asmbly.org account. |
| Sign-in works but Claude says it can't connect | The account isn't a verified asmbly.org account, or the server failed to start. Check the logs. |
| Where are the logs? | CloudWatch, log group `/aws/lambda/asmbly-mcp`. |
| You replaced the Google client secret | Update the parameter in Parameter Store. The server reads it when it starts, so the change takes effect the next time AWS restarts the server, which happens on its own after it sits idle. Everyone then has to click **Connect** once more. |
| You want to remove everything | `sam delete` from `asmbly_mcp/infra`. |
