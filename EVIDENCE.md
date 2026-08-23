# Reproducibility evidence

## Local verification

The first public candidate is accepted only after all of these commands pass:

```bash
PYTHONPATH=.deps:. python -c \
  'from evidenceops_fleet.agent import root_agent; print(root_agent.name)'
PYTHONPATH=.deps:. python -m pytest -q
python -m compileall -q evidenceops_fleet tests
```

Expected ADK graph:

```text
Workflow evidenceops_fleet
  intake_agent
  policy_agent
  supervisor_agent
```

This receipt proves local code behavior and ADK construction. It is not evidence
of Gemini inference, Firestore persistence, Cloud Run deployment, users, revenue,
competition eligibility, judging, or prizes. Cloud claims will be added only
after a deployed revision and public logs are independently verified.
