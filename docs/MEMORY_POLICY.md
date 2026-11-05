# Memory policy

Metatron's default objective is a 2–3 GiB whole-platform envelope on the 16 GiB reference laptop. The policy is conservative because the application combines Python workers, WebView2, OpenVINO/NPU or GPU allocations, and short-lived coding-agent process trees.

## Strict profile

Logical admission ceiling: **2816 MiB**.

The control plane owns reservations for optional components. Before loading a worker it plans against placement-aware estimates, evicts lower-priority idle resources when safe, and then reconciles estimates with measured process-tree memory. On Windows, learned charges prefer **complete-tree private commit**; complete-tree working set is the fallback. A 10% measurement cushion is retained by the broker.

Protected behavior:

- STT has higher priority than cleanup/TTS/dashboard.
- The procedural orb degrades to Eco under system physical-memory pressure instead of disappearing.
- S1-mini is recomputable and is an early eviction candidate.
- Premium TTS is disposable.
- Cloud Ezra does not consume local model memory.
- 9B assistants are not admitted under Strict profile.
- Partial process-tree measurements are never used to lower a reservation.

## Runtime profiles

- **Strict**: 2816 MiB, one local coding agent.
- **Voice**: 2560 MiB, dashboard expected closed, aggressive idle eviction.
- **Agent**: 3072 MiB, upper edge, more local agent tooling.

## Qualification gates

The long-duration soak is intentionally independent of unrelated release failures. A requested soak still runs when another gate fails so memory evidence is not lost. Current default leak checks require:

- at least 95% complete private-working-set samples;
- at least 90% of the requested observation duration;
- private-working-set growth slope no greater than 64 MiB/hour;
- first-to-last-quartile drift no greater than 128 MiB;
- peak private working set no greater than 2560 MiB;
- complete-tree Private Bytes coverage at the same 95% minimum;
- Private Bytes growth no greater than 64 MiB/hour and quartile drift no greater than 128 MiB;
- peak complete-tree Private Bytes no greater than 3072 MiB.

Handle and thread growth are also summarized as leak signals. These thresholds are provisional release gates and should be tightened after several clean runs on the reference Windows machine.

## Measurement principle

Metatron never treats an estimate as a measurement. The Windows collector records working set, private working set, Private Bytes, system commit, GPU memory where available, handles, threads, and process churn. The broker uses a conservative charge and never substitutes missing measurements with zero.
