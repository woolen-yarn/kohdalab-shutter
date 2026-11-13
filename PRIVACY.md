# Privacy policy / プライバシーポリシー

KohdaLab Shutter does not send telemetry, upload experiment data, contact analytics services, or automatically check for updates. The operator starts Pico W discovery; it sends the shutter discovery protocol on the local network and receives device IDs and addresses. The operator selects a controller before TCP shutter commands are sent. Status and activity history are kept in memory. This is not a claim that the app never uses the network.

The optional GUI control API listens on loopback and writes its endpoint/authentication descriptor into a private per-user local directory. Python/Jupyter clients use that local API when explicitly enabled. Credentials are not submitted to a remote service. Demo screenshots are saved only to an operator-specified path.

Wi-Fi configuration belongs to the Pico W firmware and the user's local upload process. Real SSIDs/passwords are not bundled with desktop releases or included in signing requests.

GitHub downloads and issue reports use GitHub's [privacy policy](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement). Do not post private network addresses, Wi-Fi passwords, API tokens or private keys in public issues. SignPath signing and Apple's notarization are maintainer operations; the signing service receives build artifacts and necessary project/account metadata, not end-user experiment data. OS certificate validation, SmartScreen and Gatekeeper services follow the operating system's settings.

---

本アプリはテレメトリー・分析サービス・自動更新確認を使用せず、実験データを送信しません。利用者が検索を開始すると、ローカルネットワークでPico W用の検索要求を送り、装置ID・IPアドレスを受け取ります。選択した装置へTCPでシャッター指令を送信します。状態・操作履歴はメモリー上に保持します。

Local control APIを有効にすると、ローカルPC内で待受し、接続先・認証情報を利用者専用のローカルフォルダへ保存します。外部サービスへ認証情報を送るものではありません。デモ画像は指定先にのみ保存します。

Pico WのWi-Fi情報は利用者のローカル転送手順で扱い、実際のSSID・パスワードをPCアプリや署名要求へ同梱しません。GitHubの公開Issueには秘密鍵・トークン・ネットワーク情報を書かないでください。SignPath署名とApple公証は保守担当者の配布作業で、送信対象はアプリと必要なプロジェクト・アカウント情報です。OSの証明書確認等はOS側の設定に従います。
