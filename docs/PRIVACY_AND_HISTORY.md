# Privacy and local history

Transcript history is **off by default**. When enabled, history is stored in the local Metatron SQLite database with optional app/context/placement metadata. Unpinned entries are pruned by the configured age/count policy; pinned entries survive automatic pruning.

Per-app rules can request `allow`, `no_context`, or `pause`. The rule store always works locally. Runtime enforcement requires the speech sidecar to report the active app and implement the optional `set_app_policy` contract. Metatron exposes whether enforcement is active; it does not claim a stored rule is enforced when the runtime lacks the capability.

Dictionary synchronization follows the same principle: local vocabulary works regardless, but runtime injection is labeled as synchronized only after the sidecar accepts the optional personalization contract.

Support bundles exclude the DB, transcript history, audio and secrets.
