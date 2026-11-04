# Model license gate (2026-11-04 review)

This file records the release gate for models referenced by Metatron. It is not legal advice.

## Parakeet Unified EN 0.6B

- Upstream model: `nvidia/parakeet-unified-en-0.6b`.
- Upstream Hugging Face model card identifies the governing license as the **NVIDIA Open Model License**.
- Metatron does **not** bundle Parakeet weights by default. A redistributing build must include the upstream license/notice obligations applicable to the exact conversion it ships.
- The FluidInference OpenVINO conversion used by an STT integration must be audited at its exact pinned revision before redistribution; do not infer conversion terms from a different CoreML conversion.

**Gate:** local download/use is allowed only according to the upstream terms; redistribution remains disabled by default until the exact conversion artifact's license/NOTICE is captured in the release manifest.

## S1-mini by Superwhisper

- Model: `superwhisper/s1-mini`, pin release `v1` unless deliberately upgraded.
- Model card states **Apache 2.0 plus an additional naming clause** requiring the model name to remain `S1-mini` by `Superwhisper` with exact capitalization wherever used.
- Metatron must retain LICENSE/NOTICE obligations if weights are redistributed and must preserve the required name.

**Gate:** runtime integration may proceed. Metatron does not bundle the weights in the default repository/release; packaged redistribution requires LICENSE + NOTICE + naming compliance in the release manifest.

## Release rule

Every packaged release must generate a third-party manifest recording model ID, exact revision/hash, source URL, license identifier/text location, whether weights are redistributed, and required notices. Missing data is a release blocker, not a warning.
