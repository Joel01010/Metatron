# Security

Please report security issues privately to the repository owner rather than opening a public issue with exploit details.

Metatron may launch local coding agents and connect to remote agent endpoints. Treat these as privileged capabilities:

- use loopback or authenticated transports
- keep remote Hermes/Ezra behind a trusted private network or TLS
- keep API keys in environment variables / OS credential storage
- require explicit approvals for destructive tools
- do not enable arbitrary shell execution from untrusted remote input
- keep cloud-context sharing disabled by default

Metatron's SQLite database is not a secret store.
