"""STP障害試験ラボ (IOL-L2 x3, トライアングル構成) をCML上に構築・起動する。

接続情報は環境変数から取得する（このリポジトリに認証情報は含まれていない）:
  CML_URL       例: https://<your-cml-host>
  CML_USER
  CML_PASSWORD
"""
import os
import sys
import warnings
from virl2_client import ClientLibrary
from virl2_client.exceptions import InterfaceNotFound

warnings.filterwarnings("ignore")

CML_URL = os.environ["CML_URL"]
USER = os.environ["CML_USER"]
PASS = os.environ["CML_PASSWORD"]
LAB_TITLE = "stp-failure-test"

COMMON_HEAD = """no ip domain-lookup
!
spanning-tree mode rapid-pvst
"""

COMMON_TAIL = """!
line con 0
 logging synchronous
 exec-timeout 0 0
!
end
"""

CONFIGS = {}

CONFIGS["SW1"] = f"""hostname SW1
!
{COMMON_HEAD}spanning-tree vlan 1 priority 4096
!
interface Vlan1
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
interface Ethernet0/0
 description LINK-TO-SW2 (PRIMARY - FAILURE INJECTION POINT)
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/1
 description LINK-TO-SW3
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/2
 shutdown
!
interface Ethernet0/3
 shutdown
{COMMON_TAIL}"""

CONFIGS["SW2"] = f"""hostname SW2
!
{COMMON_HEAD}spanning-tree vlan 1 priority 8192
!
interface Vlan1
 ip address 192.168.1.2 255.255.255.0
 no shutdown
!
interface Ethernet0/0
 description LINK-TO-SW1 (PRIMARY - FAILURE INJECTION POINT)
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/1
 description LINK-TO-SW3 (BACKUP PATH)
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/2
 shutdown
!
interface Ethernet0/3
 shutdown
{COMMON_TAIL}"""

CONFIGS["SW3"] = f"""hostname SW3
!
{COMMON_HEAD}spanning-tree vlan 1 priority 32768
!
interface Vlan1
 ip address 192.168.1.3 255.255.255.0
 no shutdown
!
interface Ethernet0/0
 description LINK-TO-SW1
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/1
 description LINK-TO-SW2 (BACKUP PATH - EXPECTED BLOCKING PORT)
 switchport mode access
 switchport access vlan 1
 no shutdown
!
interface Ethernet0/2
 shutdown
!
interface Ethernet0/3
 shutdown
{COMMON_TAIL}"""

POS = {
    "SW1": (0, -200),
    "SW2": (-200, 100),
    "SW3": (200, 100),
}


def main():
    c = ClientLibrary(CML_URL, USER, PASS, ssl_verify=False)

    for lab in c.all_labs(show_all=True):
        if lab.title == LAB_TITLE:
            st = lab.state()
            if st in ("DEFINED_ON_CORE", "STOPPED"):
                print(f"未起動の残存 '{LAB_TITLE}' (id={lab.id}, {st}) を削除して作り直します")
                try:
                    lab.wipe(wait=True)
                except Exception as e:
                    print("  wipe:", e)
                lab.remove()
            else:
                print(f"'{LAB_TITLE}' が state={st} で存在。安全のため中断 (id={lab.id})。")
                sys.exit(1)

    lab = c.create_lab(title=LAB_TITLE)
    print(f"created lab id={lab.id}")

    sws = {}
    for name in ("SW1", "SW2", "SW3"):
        n = lab.create_node(name, "ioll2-xe", *POS[name], populate_interfaces=True)
        n.configuration = CONFIGS[name]
        sws[name] = n
    print("3 nodes (IOL-L2) created + day-0 config set")

    def slot(node, s):
        try:
            return node.get_interface_by_slot(s)
        except InterfaceNotFound:
            return node.create_interface(slot=s)

    lab.create_link(slot(sws["SW1"], 0), slot(sws["SW2"], 0))  # SW1-SW2 primary
    lab.create_link(slot(sws["SW1"], 1), slot(sws["SW3"], 0))  # SW1-SW3
    lab.create_link(slot(sws["SW2"], 1), slot(sws["SW3"], 1))  # SW2-SW3 backup
    print("3 links created (triangle)")

    print("starting lab ...")
    lab.start(wait=True)
    print("lab started; waiting for convergence ...")
    lab.wait_until_lab_converged()

    print()
    print("LAB_ID", lab.id)
    print("LAB_STATE", lab.state())
    for name, n in sws.items():
        print(f"{name}\tbooted={n.is_booted()}")


if __name__ == "__main__":
    main()
