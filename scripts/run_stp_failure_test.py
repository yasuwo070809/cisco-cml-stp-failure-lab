"""CML コンソールサーバ (SSH:22) 経由で stp-failure-test ラボの3台のIOL-L2に接続し、
1) 正常時   2) 障害時 (SW1 Eth0/0 shutdown)   3) 復旧後 (no shutdown)
の各フェーズで確認コマンドを実行し、生ログを ./outputs 相当のディレクトリに保存する。

接続情報は環境変数から取得する（このリポジトリに認証情報は含まれていない）:
  CML_HOST      例: <your-cml-host-or-ip>
  CML_USER
  CML_PASSWORD
"""
import os
import re
import time
import paramiko

HOST = os.environ["CML_HOST"]
USER = os.environ["CML_USER"]
PASS = os.environ["CML_PASSWORD"]
LAB = "stp-failure-test"
NODES = ("SW1", "SW2", "SW3")

PROMPT_RE = re.compile(r"[\r\n][A-Za-z0-9_.\-]+[#>][ \t]*$")
CONSOLES_RE = re.compile(r"consoles>\s*$")

VERIFY_CMDS = [
    "show spanning-tree vlan 1",
    "show interfaces status",
]

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs")


def recv_until(chan, pattern, timeout=30, settle=0.4):
    buf = ""
    end = time.time() + timeout
    while time.time() < end:
        if chan.recv_ready():
            buf += chan.recv(65535).decode(errors="replace")
            end = time.time() + settle * 8
        else:
            time.sleep(settle)
            if pattern.search(buf):
                return buf, True
    return buf, bool(pattern.search(buf))


class Console:
    def __init__(self, name):
        self.name = name
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(HOST, port=22, username=USER, password=PASS,
                          look_for_keys=False, allow_agent=False, timeout=20)
        self.chan = self.cli.invoke_shell(width=240, height=20000)
        time.sleep(1.5)
        recv_until(self.chan, CONSOLES_RE, timeout=10)
        self.chan.send(f"open /{LAB}/{name}/0\r")
        time.sleep(3)
        self.chan.send("\r")
        out, ok = recv_until(self.chan, PROMPT_RE, timeout=20)
        tries = 0
        while not ok and tries < 8:
            self.chan.send("\r")
            o2, ok = recv_until(self.chan, PROMPT_RE, timeout=12)
            out += o2
            tries += 1
        if re.search(r"[\r\n][A-Za-z0-9_.\-]+>[ \t]*$", out):
            self.chan.send("enable\r")
            recv_until(self.chan, PROMPT_RE, timeout=10)
        self.chan.send("terminal length 0\r")
        recv_until(self.chan, PROMPT_RE, timeout=10)
        time.sleep(1)
        self.chan.send("\r")
        recv_until(self.chan, PROMPT_RE, timeout=8)

    def cmd(self, c, timeout=45):
        self.chan.send(c + "\r")
        time.sleep(0.5)
        out, ok = recv_until(self.chan, PROMPT_RE, timeout=timeout)
        body = re.sub(r"^[^\n]*\n", "", out, count=1)
        body = re.sub(r"[\r\n][A-Za-z0-9_.\-]+[#>][ \t]*$", "", body)
        return body.strip("\r\n")

    def close(self):
        self.cli.close()


def collect_phase(consoles, phase_name):
    parts = [f"########## PHASE: {phase_name} ##########", ""]
    for name in NODES:
        con = consoles[name]
        parts.append(f"===== {name} =====")
        for cmd in VERIFY_CMDS:
            body = con.cmd(cmd)
            parts.append(f"\n{name}# {cmd}\n{body}")
        parts.append("")
    with open(os.path.join(OUTDIR, f"stp_{phase_name}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def ping_test(consoles, src, dst_ip, phase_name):
    con = consoles[src]
    out = con.cmd(f"ping {dst_ip} repeat 5", timeout=30)
    with open(os.path.join(OUTDIR, f"ping_{phase_name}_{src}.txt"), "w", encoding="utf-8") as f:
        f.write(out)


def main():
    print("connecting consoles ...")
    consoles = {name: Console(name) for name in NODES}

    print("waiting for initial STP convergence (20s) ...")
    time.sleep(20)

    print("=== PHASE 1: NORMAL ===")
    collect_phase(consoles, "normal")
    ping_test(consoles, "SW2", "192.168.1.3", "normal")

    print("=== INJECT FAILURE: SW1 Ethernet0/0 shutdown (link to SW2) ===")
    consoles["SW1"].cmd("configure terminal")
    consoles["SW1"].cmd("interface Ethernet0/0")
    consoles["SW1"].cmd("shutdown")
    consoles["SW1"].cmd("end")
    print("waiting for STP reconvergence (30s) ...")
    time.sleep(30)

    print("=== PHASE 2: FAILURE ===")
    collect_phase(consoles, "failure")
    ping_test(consoles, "SW2", "192.168.1.3", "failure")

    print("=== RESTORE: SW1 Ethernet0/0 no shutdown ===")
    consoles["SW1"].cmd("configure terminal")
    consoles["SW1"].cmd("interface Ethernet0/0")
    consoles["SW1"].cmd("no shutdown")
    consoles["SW1"].cmd("end")
    print("waiting for STP reconvergence (45s) ...")
    time.sleep(45)

    print("=== PHASE 3: RECOVERY ===")
    collect_phase(consoles, "recovery")
    ping_test(consoles, "SW2", "192.168.1.3", "recovery")

    for con in consoles.values():
        con.close()

    print()
    print("done. raw logs saved under", OUTDIR)


if __name__ == "__main__":
    main()
