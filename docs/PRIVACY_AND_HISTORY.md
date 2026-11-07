# Privacy and local history

Transcript history is **off by default**. When enabled, completed dictation history is stored in the local Metatron SQLite database with optional app/context/placement metadata. Unpinned entries are pruned by the configured age/count policy; pinned entries survive automatic pruning.

Per-app rules support `allow`, `no_context`, and `pause`. With the pinned Metatron EZSTT adapter, these rules are enforced at runtime: the adapter reports the foreground executable, Metatron returns the matching rule, and capture is refused for `pause`. The adapter also re-checks the rule at injection time to cover a focus change between capture and paste. A policy is never carried from one foreground application to another while the new rule is being resolved.

A privacy-paused capture is **not eligible for local history or dictionary learning**, even when transcript history is otherwise enabled. The runtime can emit a redacted/accountability state to the UI, but Metatron does not persist that text.

`no_context` keeps dictation available while suppressing app-context use. Context profiles are propagated only when allowed by the current rule.

Dictionary synchronization is runtime-active with the pinned adapter. Replacements are bounded, longest-first and case-insensitive; alphanumeric terms use word boundaries so a short term cannot rewrite the interior of a larger word. The original transcript remains available to the immediate event payload for diagnostics while the injected/final text uses the approved replacement.

Support bundles exclude the database, transcript history, captured audio and secrets. Runtime capability state remains visible in diagnostics; if a different speech sidecar does not implement `set_app_policy` or `set_personalization`, Metatron degrades visibly rather than pretending those controls are enforced.
