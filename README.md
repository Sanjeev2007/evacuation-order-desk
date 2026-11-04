# Evacuation Order Desk

**A hypothetical drill. No real alert is ever sent, and this has not been validated by any agency.**

When a dam is at risk, the river authority knows what's coming and the emergency team must tell people where to go. Evacuation Order Desk connects them in team chat through [Switch](https://docs.switchagents.ai/): agents check and draft, code tests the required details, and one named person approves the order.

Built for the Flip the Switch hackathon, Best Business Workflow track.

> **Status, 4 Nov 2026: work in progress.** The scripts and their tests run. The workflow has not yet run end to end in Switch, so everything below describes the design until this note changes.

## The scenario

The demo is a labelled hypothetical flood below the Forata reservoir in Valencia, Spain. Forata did not breach in 2024, and this dam scenario is invented.

## How Switch is used

| Room | Who's in it | Job |
|---|---|---|
| Reservoir | Reservoir agent, dam engineer | Propose and approve the release plan |
| Field | Flood mapper, field agent, site checker | Find towns at risk, check readiness, test evacuation sites |
| Decision | Alert writer, record keeper, duty officer | Draft, check, approve and record the order |

A coordinator agent sits in all three rooms and is the only link between them. It passes only a release notice, a staging request or an order package.

## The two locks

1. **Code check:** `check_draft.py` blocks a draft unless it's marked as a drill and names the at-risk towns, a valid release, a site, English and Spanish text, and the issuing office. It reruns the site check itself, so a draft can't simply claim a site passed.
2. **Switch approval:** the writer posts the full draft and its hash, then runs `issue_order.py`, which raises an approval card in the room. The writer's addressing setting means only its owner can answer. If the draft changed after the check, the script refuses it.

## Run it

You'll need [Switch Console](https://docs.switchagents.ai/switch-rooms/getting-started) (built on 0.40.1, with core 0.31.0), Docker, and Claude Code signed in. Full steps will be added once the workflow has been run from a clean clone.

**Trust your clone once before running it.** Switch starts Claude Code without showing its trust prompt, and until a folder is trusted, the folder's allow rules are ignored. In that state, the first lock's check raises a card it shouldn't need. Block rules apply either way. To trust it, run `claude` in the clone, accept the prompt, then type `/exit`.

To run the tests, with no install needed:
```
python3 -m unittest discover -s tests
```

## What this doesn't prove

- **It's a drill:** the flood, levels, releases, thresholds, evacuee counts, capacities and staffing are all invented.
- **"Approved" means a chat approval,** not a legally valid signature.
- **It isn't a security boundary:** rooms on one Mac separate conversations, not secure data. The folder rules and locks hold back agents following the workflow, but an agent or process working around them could still write a file.
- **The engineer's approval isn't a lock:** it's a typed message that the reservoir agent judges, and Switch doesn't enforce it.
- **Separate ownership is simulated:** one person owns every agent and plays both people in the demo.
- **Being cleared for this drill says nothing about a real building's safety,** in either direction. Sites are only ever called Site A, B and C.
- **The Spanish text hasn't been checked by a Spanish reader.**
- **It doesn't claim to save lives or time,** or that it would have changed any real event.

## Credits and licences

The MIT licence covers the code only. **It does not cover `data/`.** See `data/README.md`.

- **Flood hazard data:** Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO), Sistema Nacional de Cartografía de Zonas Inundables, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Traced to polygons, clipped and simplified by this project. MITECO does not endorse this project.
- **Site locations:** © OpenStreetMap contributors. Contains information from [OpenStreetMap](https://www.openstreetmap.org/), which is made available here under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).
