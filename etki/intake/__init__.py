"""Request intake orchestration — the APPLICATION CORE half of the intake
feature (the vendor connection is a plugin: ``etki-plugin-jira``).

Flow, policy and persistence live here: the polling loop (``service.py``), the
opaque-cursor store (``cursors.py``) and the decision write-back
(``respond.py``). The core owns dedup, the audit trail and the copilot
invariant (write-back defaults to AFTER the PMO decides); adapters only pull
requests and transport comments.
"""
