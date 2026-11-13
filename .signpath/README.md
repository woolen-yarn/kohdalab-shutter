# SignPath application preparation

**Status: not submitted or accepted; no signing credentials/service are configured.** This is the same preparation/approval policy as KohdaLab TRKR and IV, not a claim that those projects or this one already have trusted signatures.

Project: [woolen-yarn/kohdalab-shutter](https://github.com/woolen-yarn/kohdalab-shutter)  
Purpose: Rust desktop GUI/CLI for Pico W optical shutters; local device discovery, calibrated Open/Close control, optional authenticated loopback API.  
License: [MIT](../LICENSE), with bundled dependency/font notices.  
Existing distribution: [GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases).  
Proposed maintainer and approver: the repository owner in [CODEOWNERS](../.github/CODEOWNERS). MFA/reviewer/approver configuration must be confirmed by the owner; this repository does not attest it is already configured.

## Review inputs

[release.yml](../.github/workflows/release.yml) builds reviewed source on GitHub-hosted Windows runners, validates PE metadata and produces:

- `signpath-input-windows-<commit>`: only `kohdalab-shutter-gui.exe` and `kohdalab-shutter.exe`.
- `signing-review-windows-<commit>`: product metadata, current Authenticode status, and SHA-256 records.

Review [application-pe.xml](application-pe.xml), [code signing policy](../CODE_SIGNING_POLICY.md), [privacy](../PRIVACY.md), and the public source. No upstream standalone executable, installer, driver or uninstaller is included in this scope. The downloadable NSIS Setup.exe and generated uninstaller are unsigned, outside this scope. Signing them requires a separate provider-approved installer/uninstaller flow after the payload is signed. A future expansion requires provider approval.

## Owner actions

1. Apply at [SignPath Foundation](https://signpath.org/apply), using this public project and its existing release. Account creation, terms, maintainer identity and MFA are owner actions.
2. After acceptance, install the SignPath GitHub App for this repository and link GitHub.com as the trusted build system. Have the provider review the exact artifact configuration.
3. Confirm a production policy with manual approval; keep its restricted API token in the protected `code-signing` GitHub environment. Organization ID, project slug, policy slug and approved signer identity must be recorded.
4. Only then integrate the official pinned `signpath/github-action-submit-signing-request@v3`, using the artifact ID produced by the same trusted workflow. Never submit a locally built arbitrary ZIP or give a token to PR/fork jobs.
5. Verify both returned files with `scripts/check_windows_signatures.ps1 -RequireSigned -ExpectedSubject '<exact approved signer subject>'`, checking valid signatures, publisher and timestamps. Repackage those exact signed bytes and recompute the final archive hashes before publishing.
6. Add SignPath sponsorship attribution only after acceptance/activation. Do not mark current v0.4.1 as signed.

Signing submission and automatic Windows repackaging are intentionally not enabled before provider review. This is a remaining activation/integration step, not completed production signing.

See [trusted build integration](https://docs.signpath.io/trusted-build-systems/github), [Foundation terms](https://signpath.org/terms), and [setup checklist](../docs/code-signing.md).

## 日本語

現在は未申請・未承認です。GUI/CLIの2ファイルに対象を限定し、GitHub提供の由来情報が付く未署名成果物と審査用レポートを準備します。申請・利用規約への同意・MFA・承認者設定は所有者の作業です。承認後にGitHub Appと保護された環境を設定し、公式アクション・署名者/タイムスタンプ検証・署名後の再パッケージを有効化します。現在のリリースを署名済みと表示したり、承認前に支援クレジットを追加したりしません。
