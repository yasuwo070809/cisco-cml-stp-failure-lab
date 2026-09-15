# トポロジ構成

## 概要

Cisco Modeling Labs (CML) 上に **IOL-L2 (ioll2-xe)** ノードを3台使用し、
トライアングル（三角形）構成のスパニングツリー冗長トポロジを構築した。
IOSvL2ではなくIOL-L2（Docker/コンテナベースの軽量イメージ）を採用することで、
起動時間とリソース消費を抑えている。

- STPモード: Rapid PVST+ (`spanning-tree mode rapid-pvst`)
- 対象VLAN: VLAN 1（デフォルトVLANのみを使用する最小構成）
- ルートブリッジ: SW1（`priority 4096` を明示設定し決定的に固定）

## 構成図

```mermaid
graph TD
    SW1["SW1<br/>Root Bridge<br/>priority 4096"]
    SW2["SW2<br/>priority 8192"]
    SW3["SW3<br/>priority 32768 (default)"]

    SW1 -- "Et0/0 (Desg/FWD) <-> Et0/0 (Root/FWD)<br/>PRIMARY LINK (障害注入対象)" --- SW2
    SW1 -- "Et0/1 (Desg/FWD) <-> Et0/0 (Root/FWD)" --- SW3
    SW2 -- "Et0/1 (Desg/FWD) <-> Et0/1 (Altn/BLK)<br/>BACKUP LINK" --- SW3

    style SW1 fill:#dff0d8,stroke:#3c763d
    style SW2 fill:#fcf8e3,stroke:#8a6d3b
    style SW3 fill:#fcf8e3,stroke:#8a6d3b
```

## ポートマッピング表（正常時）

| リンク | SW側インタフェース | 役割/状態 | 対向インタフェース | 役割/状態 | 備考 |
|---|---|---|---|---|---|
| SW1 - SW2 | SW1 Et0/0 | Desg / FWD | SW2 Et0/0 | Root / FWD | 障害注入対象リンク |
| SW1 - SW3 | SW1 Et0/1 | Desg / FWD | SW3 Et0/0 | Root / FWD | |
| SW2 - SW3 | SW2 Et0/1 | Desg / FWD | SW3 Et0/1 | **Altn / BLK** | バックアップリンク（正常時ブロッキング） |

## 障害試験シナリオ

SW1 の Et0/0（SW1-SW2間のプライマリリンク）を `shutdown` し、
ルートブリッジ(SW1)への直接リンクを喪失した SW2 が、
SW3経由のバックアップパス（SW2-SW3間リンク、正常時はSW3側 Alternate/Blocking）
へフェイルオーバーすることを確認する。

```mermaid
sequenceDiagram
    participant SW1 as SW1 (Root)
    participant SW2 as SW2
    participant SW3 as SW3

    Note over SW1,SW3: 正常時: SW3 Et0/1 は Alternate/Blocking
    SW1->>SW2: BPDU (Et0/0, 2秒毎)
    SW1->>SW3: BPDU (Et0/1, 2秒毎)

    rect rgb(255,230,230)
    Note over SW1,SW2: 障害注入: SW1 Et0/0 shutdown
    SW1--xSW2: BPDU 途絶
    end

    Note over SW2: Max Age(20s)経過後、Et0/0の情報をエージングアウト
    Note over SW3: SW2への既存Desgを維持できると判断
    SW3->>SW2: Et0/1 が Blocking -> Forwarding へ遷移
    Note over SW2,SW3: SW2 Et0/1: Desg -> Root(FWD維持)<br/>SW3 Et0/1: Altn/BLK -> Desg/FWD

    rect rgb(230,255,230)
    Note over SW1,SW2: 復旧: SW1 Et0/0 no shutdown
    end
    Note over SW1,SW3: 再度BPDUを受信し、元のトポロジ（SW3 Et0/1 = Altn/BLK）に復帰
```
