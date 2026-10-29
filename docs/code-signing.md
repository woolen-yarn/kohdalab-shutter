# Trusted signing setup / 署名・公証の設定

[Policy](../CODE_SIGNING_POLICY.md) · [Privacy](../PRIVACY.md) · [Current downloads](install.md)

**Current release v0.4.1 remains unsigned on Windows and ad-hoc signed/unnotarized on Mac.** No provider application, certificate enrollment, account purchase or signing request has been performed by this repository change.

現在のv0.4.1は変更しません。Windowsは未署名、Macはアドホック署名・未公証です。この変更で外部サービスへの申請・契約・証明書発行・署名要求を行ったわけではありません。

## Windows: the same SignPath preparation policy as TRKR/IV

1. Review [SignPath application preparation](../.signpath/README.md), the exact [two-file PE configuration](../.signpath/application-pe.xml), [policy](../CODE_SIGNING_POLICY.md), and [privacy](../PRIVACY.md).
2. The owner applies at [SignPath Foundation](https://signpath.org/apply) and confirms ownership, maintainer/approver roles, MFA and the provider's terms. Approval is not implied by adding configuration files.
3. Supply `signpath-input-windows-<commit>` and `signing-review-windows-<commit>` from the GitHub-hosted release build for review. The input is exactly the native GUI and CLI; reports include product metadata, SHA-256 and current signature status.
4. After acceptance, configure the GitHub App, trusted build system and a manually approved production policy. Add the restricted token to a protected environment. Do not put a token in a pull request or chat.
5. The remaining production integration submits the same-workflow artifact ID through the official pinned SignPath action, obtains signed files, verifies the exact approved publisher and timestamp, and repackages from those signed bytes. This cannot be activated/tested before provider review.

Strict verification is already available for provider-returned files:

```powershell
./scripts/check_windows_signatures.ps1 -Directory signed `
  -RequireSigned -ExpectedSubject '<exact approved certificate subject>' `
  -ReportPath windows-signatures.json
```

`ExpectedSubject` is obtained from the approved provider certificate. Do not substitute a self-signed certificate or turn off SmartScreen. Signing improves publisher identity and reputation but cannot guarantee zero warnings for a new binary. [Microsoft's explanation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

TRKR・IVと同じ申請準備の方針です。SignPathへの本人による申請・承認、MFA・役割・GitHub App・本番ポリシーの設定が必要です。現在は署名要求を送信しません。承認後の署名アクション接続と実際の署名結果の検証・再パッケージを経て、署名済み配布を有効化します。

## Mac: Apple enrollment and identity

The owner must first [enroll in the Apple Developer Program](https://developer.apple.com/programs/enroll/). Apple lists 99 USD per membership year, with regional pricing; qualifying educational institutions/nonprofits/government organizations may request a fee waiver. Enrollment includes identity/authority verification, legal agreement and payment/waiver decisions. The account holder must perform these steps.

Create a **Developer ID Application** certificate with its private key and export it as password-protected PKCS#12 (`.p12`). A development certificate, Mac App Distribution certificate, or ad-hoc signature is not a substitute. Create a Team App Store Connect API key usable by `notarytool`; this workflow uses its issuer ID and `.p8` key. See [Apple Developer ID](https://developer.apple.com/developer-id/) and [notarization documentation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

MacはまずApple Developer Programへの登録が必要です。個人・組織の本人確認、利用規約、費用または免除申請はアカウント所有者の操作になります。大学等の名義を使う場合は、その組織を代表する権限が必要です。登録後にDeveloper ID Application証明書・秘密鍵と、公証用APIキーを用意します。

## Protected GitHub configuration

Create environment **`code-signing`** in repository Settings → Environments. Restrict deployments to `main`, require the designated maintainer's approval, and configure MFA for repository/signing accounts. Environment protections are owner configuration, not automatically guaranteed by a workflow file. The Mac workflow must run from `main` and only rebuilds a stable release tag that is an ancestor of reviewed main and already passed the tag's complete Test workflow.

### Environment variables (nonsecret)

| Variable | Meaning |
| --- | --- |
| `APPLE_TEAM_ID` | Apple developer team ID |
| `APPLE_SIGNING_IDENTITY_SHA1` | SHA-1 fingerprint of the Developer ID Application identity |
| `APPLE_NOTARY_KEY_ID` | Team App Store Connect API key ID |
| `APPLE_NOTARY_ISSUER_ID` | Team API key issuer UUID |

### Environment secrets

| Secret | Meaning |
| --- | --- |
| `APPLE_CERTIFICATE_P12_BASE64` | Base64 of the password-protected certificate/private-key `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | PKCS#12 export password |
| `APPLE_NOTARY_KEY_P8_BASE64` | Base64 of the Apple Team API private key `.p8` |

Enter these only in GitHub's protected environment secret settings; never paste the private material into chat, issues, source, build artifacts or release notes. Use a trusted local machine to prepare base64 values. Remove local export copies after storing them securely.

Only after configuring the environment and credentials, create repository variable **`MACOS_NOTARIZATION_READY=true`**. The preflight refuses execution while this activation flag is absent. Do not set the flag to bypass incomplete registration.

保護環境の承認者・main制限とシークレットを設定した後にだけ、リポジトリ変数`MACOS_NOTARIZATION_READY=true`を設定します。秘密鍵・パスワードをチャットやIssueへ送らないでください。現在は未設定のため、公証処理は実行できません。

## Run and review

1. Open Actions → **Developer ID signing and Apple notarization** → Run workflow from `main`.
2. Select an existing stable `release_tag`, such as `v0.4.1`. Leave `publish=false` for the first validation.
3. The build job rebuilds the tag on GitHub-hosted Mac runners without private credentials. Inspect the unsigned input and source commit, then approve the `code-signing` environment.
4. The signing job verifies the input hash, uses an ephemeral keychain, signs CLI before app, requires Developer ID/team/timestamp/hardened runtime, notarizes app and DMG, staples both tickets, and assesses Gatekeeper. An Apple response other than `Accepted` stops the process.
5. Download `macos-signed-and-notarized`, inspect `SIGNING-macos.json`, checksums, source identity and the actual app on supported Macs. The script's local tests exercise rejection/identity/archive checks; a real Apple end-to-end run remains pending until enrollment.
6. When ready to publish, run with `publish=true` and the same protected approval process. Verified `*-macos-universal-signed.zip/.dmg` and their report/checksums are added to the existing release. Original unsigned assets/checksums are not overwritten. The optional publication step downloads and verifies the newly uploaded files again.

The workflow can run again with `publish=true` after a nonpublishing trial; it performs a fresh signing/notarization and obtains approval again. An attempt to overwrite an existing signed asset fails instead of silently changing public bytes. The secret directory/keychain is removed even after failure, before candidate artifacts are uploaded.

実際のApple処理は登録・証明書設定後の検証が必要です。ローカルのテスト成功だけで公証済みとは表示しません。公開を選んだ場合も、署名済みの別名ファイルを追加するだけで既存の配布物を上書きしません。

## What warnings can be removed

Developer ID plus successful notarization addresses macOS's unidentified-developer/notarization blockers under normal Gatekeeper policy; normal download confirmation, network permissions or organizational controls may still apply. Windows SmartScreen additionally depends on reputation and may warn for valid signatures. We do not promise that every machine will show no dialogs. No workflow disables OS protection to obtain a passing result.
