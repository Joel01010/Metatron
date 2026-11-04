# Text injection / UIPI contract

Text insertion is owned by the speech sidecar, not the Metatron control plane.

For the certified Windows path:

1. The default injection method is clipboard/paste.
2. Clipboard injection must save the existing clipboard content, set the transcript, request paste, then restore the original clipboard where possible.
3. A non-elevated Metatron/speech process must **not** claim successful insertion into an elevated target. Windows UIPI can block input across integrity levels.
4. If the foreground target is elevated or injection is rejected, the sidecar must return/emit an explicit `INJECTION_BLOCKED` or `ERROR` result and leave the transcript available for manual copy.
5. Metatron must not automatically self-elevate to bypass UIPI.
6. Voice barge-in is not certified while echo guard suppresses capture. The certified path is hotkey/button barge-in only until acoustic echo cancellation is separately proven.

These behaviors require a Windows end-to-end test with an ordinary target and an elevated test target.
