# 確認結果（正常時 / 障害時 / 復旧後）

試験手順・期待結果は [test-plan.md](test-plan.md) を参照。
生ログ（`show`コマンド生出力）は [../outputs/](../outputs/) 配下。

## フェーズ1: 正常時

### STPポート状態

| ノード | Interface | Role | Status | Cost | 備考 |
|---|---|---|---|---|---|
| SW1 (Root) | Et0/0 | Desg | FWD | 100 | SW2向け |
| SW1 (Root) | Et0/1 | Desg | FWD | 100 | SW3向け |
| SW2 | Et0/0 | Root | FWD | 100 | SW1向け（プライマリ） |
| SW2 | Et0/1 | Desg | FWD | 100 | SW3向け |
| SW3 | Et0/0 | Root | FWD | 100 | SW1向け |
| SW3 | Et0/1 | **Altn** | **BLK** | 100 | SW2向け（バックアップ、ブロッキング） |

### 疎通確認

SW2 → 192.168.1.3 (SW3) : `Success rate is 80 percent (4/5)`
（起動直後1発目のARP解決待ちによる欠落。以降は連続成功しており実運用上問題なし）

判定: **[OK]** 試験項目No.1, No.2 を満たす。ルートブリッジはSW1、SW3 Et0/1がAlternate/Blockingであることを確認。

## フェーズ2: 障害時（SW1 Et0/0 shutdown、30秒待機後に採取）

### STPポート状態

| ノード | Interface | Role | Status | Cost | 変化 |
|---|---|---|---|---|---|
| SW1 (Root) | Et0/0 | - | **disabled** | - | 手動shutdownによりSTPポートリストから消滅 |
| SW1 (Root) | Et0/1 | Desg | FWD | 100 | 変化なし |
| SW2 | Et0/0 | Desg | FWD(*) | 100 | Root→Desgへ変化（詳細は下記「観察事項」） |
| SW2 | Et0/1 | **Root** | FWD | 100 | Desg→**Root**へ昇格。コストが100→200に増加（SW3経由） |
| SW3 | Et0/0 | Root | FWD | 100 | 変化なし |
| SW3 | Et0/1 | **Desg** | **FWD** | 100 | **Altn/BLK → Desg/FWD へ遷移（バックアップパス有効化）** |

### 疎通確認

SW2 → 192.168.1.3 (SW3) : `Success rate is 100 percent (5/5)`
バックアップパス（SW2-SW3直接リンク）経由で疎通が維持されていることを確認。

判定: **[OK]** 試験項目No.4, No.5 を満たす。SW3 Et0/1がブロッキングからフォワーディングに遷移し、バックアップパスへのフェイルオーバーが機能した。

### 観察事項（技術的補足）

CML上の仮想リンク（IOL-L2間の veth 接続）は、片側インタフェースの `shutdown` を行っても
対向インタフェースのリンクキャリア断（line protocol down）としては伝播されない特性がある。
そのため SW2 の Et0/0 は `show interfaces status` 上 `connected` のままとなり、
STPの再収束はリンクダウン検知による即時のRSTP Proposal/Agreementではなく、
**BPDU途絶によるMax Age（20秒）タイムアウト経由**で発生した。
これが実機・実回線での物理断（Max Age 待ちなしでほぼ瞬時に収束）との差異点であり、
本試験では障害検知から収束まで30秒の待機時間を確保することで対応した。
実機/実リンクを用いた検証では、より高速な収束が期待できる。

## フェーズ3: 復旧後（SW1 Et0/0 no shutdown、45秒待機後に採取）

### STPポート状態

| ノード | Interface | Role | Status | Cost | 正常時との比較 |
|---|---|---|---|---|---|
| SW1 (Root) | Et0/0 | Desg | FWD | 100 | 一致 |
| SW1 (Root) | Et0/1 | Desg | FWD | 100 | 一致 |
| SW2 | Et0/0 | Root | FWD | 100 | 一致（Root役割に復帰） |
| SW2 | Et0/1 | Desg | FWD | 100 | 一致 |
| SW3 | Et0/0 | Root | FWD | 100 | 一致 |
| SW3 | Et0/1 | **Altn** | **BLK** | 100 | 一致（Blockingに復帰） |

### 疎通確認

SW2 → 192.168.1.3 (SW3) : `Success rate is 100 percent (5/5)`

判定: **[OK]** 試験項目No.7, No.8 を満たす。全ポートの役割・状態が正常時と完全に一致し、
元のトポロジ（SW3 Et0/1 = Alternate/Blocking）へ復帰したことを確認した。

## 7. 総合判定

| No | 試験項目 | 判定 |
|---|---|---|
| 1 | 正常時のSTPトポロジ確認 | OK |
| 2 | 正常時の疎通確認 | OK |
| 3 | 障害注入 | OK |
| 4 | 障害時のSTP再コンバージェンス確認 | OK |
| 5 | 障害時の疎通維持確認 | OK |
| 6 | リンク復旧 | OK |
| 7 | 復旧後のSTPトポロジ復帰確認 | OK |
| 8 | 復旧後の疎通確認 | OK |

**全項目 OK。** プライマリリンク障害時のバックアップパスへのフェイルオーバー、
および復旧後の元トポロジへの復帰が、いずれも設計通り動作することを確認した。
