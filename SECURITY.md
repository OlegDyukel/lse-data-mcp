# Security policy

## Reporting a vulnerability

Please do not publish credentials, private market data, or exploitable details in a public issue.
Report security concerns privately to the repository maintainer through GitHub's private vulnerability reporting feature when it is enabled.

## Credential handling

- The server reads the API key from `LSE_API_KEY`.
- Credentials must never be committed to the repository.
- Logs and exception messages must not contain API keys.
- Every user must supply their own provider credentials.

## Supported versions

Until the first public release, only the latest commit on `main` is supported.
