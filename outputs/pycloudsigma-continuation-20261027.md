# pycloudsigma continuation closure evidence — 2026-10-27

## Authoritative tree

- Repository: `cloudsigma/pycloudsigma`
- Checkout: `/Users/rjenkin/Documents/Codex/2026-10-27/text-continue-the-pycloudsigma-work-autonomously/work/pycloudsigma-current-20261025`
- Base supplied by gateway-owner: `936fc5086c9bbbc565fae9cb80047f2843a8c9e8` (tree `78dcb0565fe4feccd54f3b9af6b19a5c64c1fa4c`)
- Evidence-base master: `6d8e78ee41972bd28c2420b380acc8cea7c1f9ee`
- Evidence-base tree: `8800218ab4c392d3066e66182f83f6d5c9aeb3ae`
- Working tree: clean
- All GitHub changes were pushed and merged as `rjcloudsigma`.

## Security and backlog disposition

Earlier merged work completed the CodeQL remediation and dependency backlog before this coverage pass:

- CodeQL alerts: 0 open after PR #74 (`a137e68cfe70ea297aef56acd874e60056e5a70e`); fixes covered temporary-file creation and sensitive command/sample logging.
- Dependabot alerts: 0 open after certifi PR #72 (`fd6c3a8a08d209e15d2b019ac91bc5191c2a6238`). Paramiko alert #35 has no upstream patched version and was dismissed as `tolerable_risk` with rationale.
- Open GitHub issues: 0 at the final review.
- Open GitHub pull requests: 0 at the final review.
- Stale OTP proposal PR #18 was reviewed as obsolete against current master and closed without merge.

## Merged contract-qualified slices in this continuation

| PR | Merge commit | Scope | CI evidence |
|---|---|---|---|
| #76 | `e87f704eb15702eb78ca860d8a31b8991196c734` | Virtual-router `get_keys` and `export_key` actions | Offline workflow run 85 passed |
| #77 | `fcaefc7eb355d6e6a18443c0171dc5e75f3aca32` | Virtual-router `enable_vpn` and `disable_vpn` actions | Offline workflow run 86 passed |
| #78 | `4d423b36ab8b3b8c9fcef5e0091fb4a6cf9ffa26` | `/tunnels/` VPN tunnel CRUD resource | Offline workflow run 88 passed after correcting singleton slash characterization |
| #79 | `61a38d136ae37e183cd7f29ac755b0404ef67d89` | `/usage/` usage collection resource | Offline workflow run 89 passed |
| #80 | `199d401f9e3d9d4bf52ca650ec78f2f3490e3bcb` | Subscription `auto_renew` action | Offline workflow run 90 passed |
| #81 | `2d0f2202136600799e13a88beff4c155a4c7bf75` | Correctly spelled `Capabilities` symbol with `Capabilites` compatibility alias | Offline workflow run 91 passed |

The offline guard is now `292` tests after the live-QA runner regression tests were merged in PR #85. Local syntax and whitespace gates passed for each slice. The local macOS checkout has no cached `pytest` or `configobj`; no dependency installation was performed. CI used the repository's existing hash-locked dependency workflow.

## Public documentation reconciliation

The current public API index and resource pages were reviewed, including:

- [API index](https://docs.cloudsigma.com/en/latest/)
- [Virtual Routers](https://docs.cloudsigma.com/en/latest/virtualrouters.html)
- [Virtual-router VPN tunnels](https://docs.cloudsigma.com/en/latest/virtualrouters_vpn_tunnels.html)
- [Usage](https://docs.cloudsigma.com/en/latest/usage.html)
- [Subscriptions](https://docs.cloudsigma.com/en/latest/subscriptions.html)
- [Capabilities](https://docs.cloudsigma.com/en/latest/capabilities.html)

The documented REST endpoint/action families are now represented by the existing generic or specialized surfaces plus the merged additions: accounts/authentication, ACLs, availability groups, backup schedulers, billing, burst/current/daily usage, capabilities, drives/uploads, keypairs/pubkeys, library drives, locations, networking, notification contacts/preferences, profile/global context, snapshots/remote snapshots, servers/VMware, subscriptions/grouped/calculator, tags, usage, virtual routers and all documented feature resources, and VPN tunnels.

The route/action matrix is evidence-backed at the endpoint level. It does not by itself certify every documented response field, writable-field rule, provider-specific validation rule, or asynchronous completion semantic. Those remain bounded by the existing generic SDK contract and the explicit specialized tests; no live provider acceptance was claimed or performed.

## File hashes for this closure

```text
`ci/run_offline.py`                                      b35b14037915695ab610aae3b3a881fb2af6960bcc613c97983076cf77fa0538
`src/cloudsigma/resource.py`                            7bb562df6dcff6650f510ad6cecac4bb3f72552fdd8342a30c19e099f9d54afa
`tests_offline/test_virtual_router_vpn_tunnels.py`       7f6d29ff2ddbaf83cb484274a6e9bc0d084643bd7a4ede0f13a1caa9a4525a78
`tests_offline/test_usage_resource.py`                   c92597c138e24edd881aaa54919bbba00d9e1017fe89972d61c892a715091ef4
`tests_offline/test_subscription_auto_renew.py`          6fdb2eca6bcdc35657de72abdda6cf16c1ad4a69f1aebb5b89c6c83878d9d614
`tests_offline/test_capabilities_symbol.py`              437a3d74226809f2a883ed2469c325ceb01a3fe09a21fea0433fa9b5aacd8293
`tests_offline/test_snapshot_singleton_query.py`         9afc3fc4a8fe62acea2e91f5ef32cd5a2a23f3e2efca5a90508763773047cfe6
```

This report records endpoint/action coverage and exact evidence. It does not claim package publication, release, deployment, live-provider acceptance, or a field-level 100% certification without an independently maintained field matrix.


## Addendum: singleton query forwarding

The post-report audit identified and fixed one documented query shape that had not been exposed: snapshot and remote-snapshot singleton reads may include `?drive={drive_uuid}`. `ResourceBase.get(..., query_params=...)` now forwards that mapping without changing existing calls. PR #83 adds synthetic coverage for both routes; its CI result and merge are the final evidence for this addendum.

## Final post-merge verification

- PR #85 (`6d8e78ee41972bd28c2420b380acc8cea7c1f9ee`) is merged by `rjcloudsigma`; the evidence-base checkout matched `github/master` and was clean before this documentation-only update.
- Live QA acceptance run [40541180791](https://github.com/cloudsigma/pycloudsigma/actions/runs/40541180791) passed on the merge commit. The installed wheel reported 5 read-only checks passed and 1 provider 404 skip for `vpn_tunnels.list`; no check failed.
- CodeQL push run [40541182599](https://github.com/cloudsigma/pycloudsigma/actions/runs/40541182599) passed both actions and Python analyses.
- GitHub API review at this commit: open pull requests `0`, open issues `0`, open Dependabot alerts `0`, open code-scanning alerts `0`.
- The repository has Dependabot security updates enabled. Secret scanning is disabled in the repository settings, so there is no secret-scanning alert status to report.
- The live workflow runs on every push to `master`, which executes after each merged pull request, and can also be dispatched manually. QA credentials remain repository secrets and are never committed.
