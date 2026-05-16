# Approval models

Each rule selects one of six approval models. The worker evaluates
the model after the rule matches; **step-up** logic can swap one
model for a stricter one when risk thresholds are crossed.

| Model           | Behaviour                                                                                  |
|-----------------|--------------------------------------------------------------------------------------------|
| `any_one`       | First approval from any listed approver wins.                                              |
| `specific`      | Only the designated approver can decide.                                                   |
| `all_of_n`      | Every approver in the list must approve. One denial blocks the action.                     |
| `k_of_n`        | `k` out of `n` approvals within `quorum_seconds`. Useful for "any two of three managers."  |
| `sequential`    | Approvers act in order. Each step waits for the previous step to approve before firing.    |
| `fga_dynamic`   | Approver list resolved at runtime from Auth0 FGA (or any compatible policy engine).        |

## Choosing a model

* **Low-risk, fast path** → `any_one`. Single notification, lowest
  latency.
* **Sensitive but routine** → `specific`. Auditable — exactly one
  person owns the decision.
* **High-risk / compliance** → `all_of_n` or `k_of_n`. Forces multiple
  sign-offs. Use `k_of_n` when you want quorum without requiring
  everyone to be online.
* **Layered review** → `sequential`. Engineer → manager → finance.
* **Dynamic teams** → `fga_dynamic`. Approver list is computed from
  org structure / on-call schedule.

## Step-up

A rule can declare a `step_up` block that escalates the approval model
when conditions are met. Example:

```json
{
  "approval_model": "any_one",
  "approvers": ["alice@corp", "bob@corp"],
  "step_up": {
    "when": "amount > 5000",
    "approval_model": "all_of_n",
    "approvers": ["alice@corp", "cfo@corp"]
  }
}
```

For a `$120` charge the rule stays `any_one`. For a `$5,001` charge it
becomes `all_of_n`. The condition is evaluated server-side against the
request payload — agents cannot bypass step-up by lying.

## Risk score

Every request receives a 0-100 score derived from amount, scope-creep
signals, model complexity, and history. The score is recorded in the
audit log and is the input for budget and step-up rules.

## Re-authorization

After `reauth_every_n` consecutive auto-approvals for the same
`agent + connection + action`, the next request forces a fresh human
approval even if the rule would otherwise auto-approve. This prevents
rubber-stamping repeated sensitive operations.
