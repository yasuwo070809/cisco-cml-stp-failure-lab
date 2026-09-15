# スパニングツリー障害試験 試験項目書

## 1. 試験目的

トライアングル構成（冗長リンクあり）のL2スイッチ環境において、
プライマリリンク障害発生時にSpanning Tree Protocol (Rapid PVST+) が
バックアップリンクへ正しくフェイルオーバーし、かつリンク復旧後に
元のトポロジへ復帰することを確認する。

## 2. 試験環境

| 項目 | 内容 |
|---|---|
| 仮想化基盤 | Cisco Modeling Labs (CML) |
| ノード種別 | IOL-L2 (ioll2-xe) x 3台（軽量化のためIOSvL2は不使用） |
| ノード名 | SW1 (Root, priority 4096) / SW2 (priority 8192) / SW3 (priority 32768) |
| STPモード | Rapid PVST+ (IEEE 802.1w) |
| 対象VLAN | VLAN 1 |
| トポロジ | SW1-SW2-SW3 のトライアングル（詳細は [topology.md](topology.md)） |

## 3. 前提条件

- 3台のIOL-L2が起動完了し、CLIプロンプトが取得できること
- 3台間のリンクがすべて `connected` であること
- SW1がルートブリッジとして選出されていること（`priority 4096` により決定的に固定）
- SW3 Et0/1（SW2向けポート）が Alternate/Blocking であること（`priority` 設定により決定的に固定）

## 4. 試験項目

| No | 試験項目 | 試験手順 | 期待結果 | 確認コマンド |
|---|---|---|---|---|
| 1 | 正常時のSTPトポロジ確認 | 3台起動後、初期コンバージェンスを待って状態を採取する | ・SW1: Et0/0, Et0/1 とも Desg/FWD（Root Bridge）<br>・SW2: Et0/0 Root/FWD、Et0/1 Desg/FWD<br>・SW3: Et0/0 Root/FWD、Et0/1 **Altn/BLK** | `show spanning-tree vlan 1`<br>`show interfaces status` |
| 2 | 正常時の疎通確認 | SW2からSW3のVLAN1 SVI(192.168.1.3)へping | 100%または高い成功率で疎通できる | `ping 192.168.1.3 repeat 5` |
| 3 | 障害注入（プライマリリンク断） | SW1の Et0/0（SW1-SW2間リンク）を `shutdown` する | SW1側は即座にEt0/0がリストから消える（Admin Down） | `interface Ethernet0/0` → `shutdown` |
| 4 | 障害時のSTP再コンバージェンス確認 | 障害注入後、十分な待機（Max Age 20秒超）ののち状態を採取する | ・SW1: Et0/1のみ Desg/FWD（Et0/0はdisabled）<br>・SW2: Et0/1が **Root/FWD** に昇格（旧Root Et0/0はBPDU途絶により経路喪失）<br>・SW3: Et0/1が **Altn/BLK → Desg/FWD** に遷移（旧backupリンクがフォワーディングへ） | `show spanning-tree vlan 1`<br>`show interfaces status` |
| 5 | 障害時の疎通維持確認 | 再コンバージェンス完了後、SW2からSW3へping | バックアップパス（SW2-SW3直接リンク）経由で100%疎通する | `ping 192.168.1.3 repeat 5` |
| 6 | リンク復旧 | SW1の Et0/0 を `no shutdown` する | リンクが再度connected状態に戻る | `interface Ethernet0/0` → `no shutdown` |
| 7 | 復旧後のSTPトポロジ復帰確認 | 復旧後、十分な待機ののち状態を採取する | 試験No.1（正常時）と同一のポート役割・状態に復帰すること（特にSW3 Et0/1が再度Altn/BLKへ戻ること） | `show spanning-tree vlan 1`<br>`show interfaces status` |
| 8 | 復旧後の疎通確認 | SW2からSW3へping | 100%疎通できる | `ping 192.168.1.3 repeat 5` |

## 5. 合否判定基準

- 各試験項目の「期待結果」欄と実機出力が一致していること
- 復旧後、正常時と同一のポート役割（Root / Designated / Alternate）・状態（FWD / BLK）に戻っていること
- 疎通試験（ping）について、障害時・復旧後とも再コンバージェンス完了後は成功率100%であること

## 6. 試験結果

実際の試験結果、判定は [verification.md](verification.md) を参照。
生ログは [../outputs/](../outputs/) 配下に格納。
