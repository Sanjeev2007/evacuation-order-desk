# Evacuation Order Desk

**A hypothetical drill. No real alert is ever sent, and this has not been validated by any agency.**

When a dam is at risk, the river authority knows what's coming and the emergency team must tell people where to go. Evacuation Order Desk connects them in team chat through [Switch](https://docs.switchagents.ai/): agents check and draft, code tests the required details, and one named person approves the order.

Built for the Flip the Switch hackathon, Best Business Workflow track.

> **Status, 6 Nov 2026:** the full story has run end to end in Switch. That covered two orders, a declined staging request, and the second order replacing the first. A run from a clean clone using only these steps is next.

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

1. **Code check:** `check_draft.py` blocks a draft unless it's marked as a drill and names the at-risk towns, a valid release, a site, English and Spanish text, and the issuing office. It reruns the site check itself, so a draft can't simply claim a site passed. It also reads the order's wording: each language must open with its drill word and name only the checked site, and a new order must replace the one that stands.
2. **Switch approval:** the writer posts the full draft and its hash, then runs `issue_order.py`, which raises an approval card in the room. The writer's addressing setting means only its owner can answer. If the draft changed after the check, the script refuses it.

## Run it

You'll need [Switch Console](https://docs.switchagents.ai/switch-rooms/getting-started) (built on 0.40.1, with core 0.31.0), Docker, and Claude Code signed in. Python 3 is used with its standard library only, so there's nothing to install.

### Set up

1. Clone the repo:
   ```
   git clone https://github.com/Sanjeev2007/evacuation-order-desk.git ~/eod-run
   ```
2. **Trust the clone once.** Switch starts Claude Code without showing its trust prompt, and until a folder is trusted, the folder's allow rules are ignored. In that state, the first lock's check raises a card it shouldn't need. Block rules apply either way. To trust it, run `claude` in the clone, accept the prompt, then type `/exit`.
3. **Create the engineer.** The briefs name the dam engineer as `@dave_007`. Create a Mattermost user with that name, and open a second browser window signed in as them. You stay signed in to Console as the owner, who is the duty officer.
4. In Console, go to **Templates → Import template**, choose `templates/evacuation-order-desk.template.yaml`, and save it.
5. Click **Use** on the template. Enter a short team prefix such as `t1`, and the path to your clone. Then click **Create all**. This creates seven agents in three private rooms.
6. Add `@dave_007` to the Reservoir and Decision rooms.

### Run the story

Each message names an agent with your prefix, shown here as `t1`.

1. **Stage 1.** As `@dave_007`, post `@t1-reservoir Propose a release for stage 1.` in the Reservoir room. When it proposes R1, reply `@t1-reservoir approved`. The notice crosses to Field, the towns and sites are checked, and package P1 reaches the writer in Decision.
2. **Approve the order.** The writer posts the draft and its hash, then raises a card. Open the card in the thread on the order package message in Decision. As the owner, press **Allow once**. The engineer can't answer it, and anything they type there is refused. The record keeper then writes the record.
3. **Staging.** As the owner, post `@t1-field Please ask for staged release R1-S. Reason: Carlet's evacuation roads need more time.` in Field. The request reaches the reservoir agent. As `@dave_007`, decline it. Nothing crosses after that.
4. **The twist.** As `@dave_007`, post `@t1-reservoir Inflow update: stage 2. Propose a release for stage 2.` and then approve it. Five towns are now at risk. Site A and Site B fail, Site C passes, and package P2 reaches the writer. Its draft must name P1 as the order it replaces. Approve the card as before.

### What you get

- `desks/writer/orders/order-P1.md` and `order-P2.md`, the issued drill orders
- `desks/record/records/record-P1.md` and `record-P2.md`, each tracing every decision to a chat message

Times in the release notices and records are in UTC.

**To run it again,** move those `orders`, `drafts` and `records` folders out of the clone, and use a new team prefix. Otherwise the old P1 counts as the standing order.

To run the tests, with no install needed:
```
python3 -m unittest discover -s tests
```

## What this doesn't prove

- **It's a drill:** the flood, levels, releases, thresholds, evacuee counts, capacities and staffing are all invented.
- **"Approved" means a chat approval,** not a legally valid signature.
- **The code can't judge every word of an order:** it catches a wrong site, a missing drill marking and listed phrases, but not, for example, a building's name. The person reading the draft before approving is the check for that.
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
