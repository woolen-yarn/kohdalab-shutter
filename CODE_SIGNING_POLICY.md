# Code signing policy / コード署名方針

## Current status / 現在の状態

The published Windows binaries are unsigned; the Mac app is ad-hoc signed and not Apple-notarized. This repository is not accepted by SignPath Foundation and does not claim sponsorship or a trusted signing certificate. Preparation files and passing CI are not evidence that a release is signed.

現在の配布版はWindowsが未署名、Macがアドホック署名のみでApple公証なしです。SignPath Foundationの承認・支援を受けたとの表明ではありません。準備ファイルやCIの成功だけで、署名済みになったとは表示しません。

## Shared KohdaLab policy / 共通方針

This follows the first-party scope and approval policy used by [KohdaLab TRKR](https://github.com/woolen-yarn/kohdalab-trkr/blob/main/CODE_SIGNING_POLICY.md) and [KohdaLab IV](https://github.com/woolen-yarn/kohdalab-iv/blob/main/CODE_SIGNING_POLICY.md):

- Build reviewed source on GitHub-hosted runners and require successful CI.
- The proposed maintainer/approver is listed in [CODEOWNERS](.github/CODEOWNERS). Confirm actual review/approval roles and MFA before activation.
- Keep signing credentials in a protected GitHub environment, never in source, releases, logs, pull requests or forks.
- Require release approval by the designated maintainer. SignPath production policy must separately require manual approval.
- Sign only first-party executables explicitly approved by the provider; no recursive executable/DLL wildcard.
- Verify publisher identity, timestamp and signatures, then compute checksums over the final signed bytes. Publish only the bytes that passed verification.
- Never weaken Defender, SmartScreen or Gatekeeper to simulate signing or suppress warnings.

TRKR・IVと同じく、GitHub runnerによるソースからのビルド、CI成功、保守担当者の承認、署名者・タイムスタンプの検証、署名後のチェックサム作成を原則とします。認証情報をPR・fork・配布物へ渡さず、OSの保護機能を無効化しません。

## Windows / SignPath Foundation

The proposed exact signing allowlist is:

- `kohdalab-shutter-gui.exe`
- `kohdalab-shutter.exe`

Both are built from this repository and embed CompanyName `Kohdalab`, ProductName `KohdaLab Shutter`, and the Cargo release version. There is no third-party helper, installer or uninstaller in this allowlist. Extending the list requires provider review. The downloadable NSIS Setup.exe and its generated uninstaller are currently unsigned and remain outside this two-executable scope; signing only Setup would not sign its embedded payload or uninstaller.

The release workflow stages those two files in a separate unsigned workflow artifact. It does not submit a request or receive a signed file. See [application preparation](.signpath/README.md), [artifact configuration](.signpath/application-pe.xml), and [SignPath's GitHub origin verification](https://docs.signpath.io/trusted-build-systems/github).

Windowsの方針はSignPath Foundationへの申請・承認を経て有効化します。現状は対象2ファイルとメタデータ・ハッシュ・未署名状態を審査できる準備までで、本番の署名要求は送信しません。承認前にSignPathの支援クレジットを表示しません。

## Mac / Developer ID and Apple notarization

After account/certificate setup, the manual [Mac notarization workflow](.github/workflows/macos-notarization.yml) rebuilds an existing validated release, waits for the protected `code-signing` environment, signs the CLI and app with a Developer ID Application identity, enables hardened runtime and secure timestamps, and submits to Apple. Both app and DMG must receive `Accepted` receipts; tickets must be stapled and Gatekeeper assessment must succeed. An ad-hoc or mismatched identity cannot pass these gates.

The workflow is inactive until the owner sets `MACOS_NOTARIZATION_READY=true` after configuring environment protections and credentials. No private key is supplied to the build job. The signing job uses an ephemeral keychain, removes it even after failure, and uploads candidates only after all gates pass. The optional publish step adds separately named signed assets without changing v0.4.1's original files or checksums.

Apple Developer登録と証明書の準備後に手動ワークフローを有効化します。Developer ID署名・タイムスタンプ・Hardened Runtime・AppleのAccepted・チケット添付・Gatekeeper評価を必須にします。失敗時にアドホック署名へ切り替えて公開することはありません。ビルドjobには秘密鍵を渡さず、署名jobの一時キーチェーンは失敗時も削除します。

## Limits / 警告について

A signature identifies the publisher and detects modification; it does not certify the hardware or measurement. Windows SmartScreen also uses reputation and can warn for a correctly signed new binary. OS confirmation dialogs and local-network permission prompts are separate from unidentified-publisher warnings. See [Microsoft](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) and [Apple](https://developer.apple.com/developer-id/).

正規署名でもWindowsの評価や組織の管理ポリシーにより警告が出る場合があり、「すべてのPCで警告ゼロ」とは保証しません。通常の初回確認・ネットワークアクセス許可も別のものです。
