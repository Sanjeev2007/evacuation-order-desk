# Settings test

Run this first. The two locks depend on Claude Code following each folder's `.claude/settings.json` when Switch starts it, and the only way to know is to try it.

**What it checks:** with Auto off, does an allow rule stop a card, does a deny rule refuse a command, and does everything else still raise a card?

**Status:** written, not yet run.

## Before you start

1. Commit this folder, then run `git pull` in your run clone. The agent runs from the clone, so a file that is only in your working folder doesn't count.
2. In Console, open **Templates** and paste `settings-test.template.yaml`.
3. Fill in the form:
   - **Test prefix:** `st1`
   - **Path to this test folder:** the full path to `tests/settings-test` in the run clone, such as `/Users/you/projects/eod-run/tests/settings-test`
4. Check that the agent's card on the form shows that exact path, then create it.
5. Confirm the folder holds no `allowed.txt`, `blocked.txt` or `other.txt`.

**Don't trust the clone yet.** The first run is meant to show what happens without it (see result B).

## The three messages

Post these one at a time in the private room `st1-settings-test-room`, signed in as yourself. Wait for each to finish before sending the next. Change `st1` if you used another prefix.

```
@st1-settings-test run this exact command: touch allowed.txt
```
```
@st1-settings-test run this exact command: touch blocked.txt
```
```
@st1-settings-test run this exact command: touch other.txt
```

The answer can land in the thread or the channel, and a card can stay hidden until you reload, so press Cmd + R before deciding no card appeared. Press **Allow once** on a card for `other.txt`. Never press "Allow for this session".

## Expected results

| Message | Expected | File afterwards |
|---|---|---|
| `allowed.txt` | Runs with no card | Exists |
| `blocked.txt` | Refused, with no card | Doesn't exist |
| `other.txt` | Raises a card, and runs only after Allow once | Exists after you approve |

## What each result means

| | `allowed.txt` | `blocked.txt` | `other.txt` | Meaning | What to do |
|---|---|---|---|---|---|
| **A** | No card | Refused | Card | Everything is honoured | Build the locks as planned |
| **B** | Card | Refused | Card | Deny rules work and allow rules don't. The docs predict this for an untrusted folder | Decline the card, then follow "If you get B" |
| **C** | Card | Card | Card | The settings file isn't being applied at all | Decline the `blocked.txt` card, then read "If Switch ignores the settings" |
| **D** | Any | Any | **No card** | Something other than the card is approving commands | **Stop.** Read "If `other.txt` raises no card" |
| **E** | Any | **File created** | Any | The deny rule failed, or the agent got round it | Read the command it ran. See "If `blocked.txt` gets created" |

An agent that replies without trying the command proves nothing. Send the message again.

## If you get B

Claude Code applies a project's allow rules only after someone accepts its trust prompt for that folder. Switch starts Claude Code through its SDK, which never shows that prompt. Deny rules don't wait for trust, because they only restrict.

1. Trust the clone once by hand:
   ```
   cd ~/projects/eod-run
   claude
   ```
   Accept the trust prompt, then type `/exit`.
2. Confirm it worked. This should print `True`:
   ```
   python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.claude.json')))['projects'].get(os.path.expanduser('~/projects/eod-run'),{}).get('hasTrustDialogAccepted'))"
   ```
3. Delete the three test files if they exist, and create the template again with a new prefix (`st2`), so a new session starts.
4. Send the three messages again, using the new prefix.

Result A now means the locks work as planned, **and that every clone needs this step**, so the main README must tell judges. If you still get B, allow rules aren't reaching the agent, even though deny rules are:
- **Writer:** you'd also approve a card for `check_draft.py` and for each draft it saves. That adds clicks, but both locks still work.
- **Other desks:** their block rules are deny rules, so they still apply.

## If Switch ignores the settings (result C)

- **Writer:** you approve a card for the check as well as the issue. That adds a click, but both locks still work: the check still blocks a bad draft, and the issue still raises a card.
- **Other desks:** their block rules are lost. Only their briefs and the folder check in `issue_order.py` hold them back. The main README must say so, and the "Field agent is refused" step in Stage 3 changes to show the script's own refusal.

## If `other.txt` raises no card (result D)

The second lock relies on a command raising a card when no rule settles it, so don't build on this until you know why.

Check, in this order:
1. The agent's page in Console shows Auto and Bypass both off. Claude Code's `acceptEdits` mode also approves `touch` without asking.
2. `~/.claude/settings.json` and `.claude/settings.local.json` at the top of the clone have no allow rule covering `touch`.
3. `~/.claude/settings.json` has no hook approving commands.

Then repeat the test with a new prefix.

## If `blocked.txt` gets created (result E)

Ask the agent in the room which exact command it ran, and check the thread.
- **A different command or tool**, such as `touch ./blocked.txt` or a file write: the agent worked round the rule. Rerun with a new prefix. This is a limit to disclose, and it's expected: a deny rule matches command text, not the file.
- **Exactly `touch blocked.txt`:** deny rules aren't being applied, so treat it as result C.

## What this test doesn't prove

- That deny rules hold for agents with Auto on. The docs say they hold in every mode, and Stage 3 tests it on a real Field agent.
- That these rules are a security boundary. They hold back an agent following the workflow, and a command written another way can slip past them.

## Clean up

Remove the agent from Console if it clutters the list. Don't delete the room (#1202 can silence replies afterwards). Use a new prefix for any rerun.

To see refusals in the log on a Mac:
```
grep -i refused ~/Library/Application\ Support/switchdash/local-switch-server/native/logs/switch-core.log
```
This log records card answers refused by Switch, such as an account that may not answer. A deny rule refuses inside Claude Code, so it may not appear here. Rely on the agent's report and the empty folder.
