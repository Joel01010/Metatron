# Updates and release provenance

Metatron 1.2 does **not** enable an automatic updater. This is deliberate: there is no unsigned or unauthenticated background update path in the certified core.

Before an updater is enabled, release engineering must provide:

1. signed Windows artifacts and signature verification;
2. a signed release manifest containing SHA-256 hashes;
3. an SBOM/model manifest archived with the release;
4. HTTPS distribution from a repository/domain controlled by the project;
5. rollback and downgrade rules;
6. updater tests that reject a modified manifest, modified binary, wrong signer, and stale replayed metadata.

Use `scripts/Generate-SBOM.py` for the dependency/model inventory and `scripts/Sign-Windows.ps1` as the Windows signing hook. Certificate material is never stored in the repository.
