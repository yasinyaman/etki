# etki-plugin-jira

Jira **request-intake** + **response-channel** plugin for [Etki](https://github.com/yasinyaman/etki).

Two adapters, one options model, one credential set:

- **`request_intake`** — polls new issues via JQL (REST v3 enhanced search,
  `/rest/api/3/search/jql`). A minute-precision `created` watermark is the
  opaque cursor; issue descriptions (Atlassian Document Format) are flattened
  to plain text for triage.
- **`response_channel`** — writes the host-composed decision summary back as an
  issue comment (`POST /rest/api/3/issue/{id}/comment`). This is the **only
  write** — declared as `external_write` in the plugin's security capabilities.

## Config

```yaml
connectors:
  request_intake:
    adapter: jira
    options:
      base_url: https://your-site.atlassian.net
      email: bot@your-company.com
      api_token: env:JIRA_API_TOKEN   # secret ref — resolved by the host
      project_key: PROJ               # or: jql: "project = PROJ AND labels = triage"
```

The Etki UI's "Talep Kanalı" card configures both connectors + the write-back
timing (`on_decision` / `on_triage` / `both`) together.

## Auth

HTTP Basic (`email:api_token`, base64). Create an API token at
<https://id.atlassian.com/manage-profile/security/api-tokens>.

## Conformance

```bash
python -m etki_api.conformance etki-plugin-jira --report out.json
```

Runs the `RequestIntakeProvider` + `ResponseChannel` contract suites against
offline doubles — credential-free.
