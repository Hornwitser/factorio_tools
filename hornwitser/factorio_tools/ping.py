# factorio_tools - Debugging utilities for Factorio
# Copyright (C) 2020  Hornwitser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import itertools
import random
import selectors
import socket
from statistics import mean, pstdev
import struct
import sys
import time

MESSAGE_TYPE = [
    'Ping', # 0
    'PingReply', # 1
    'ConnectionRequest',
    'ConnectionRequestReply',
    'ConnectionRequestReplyConfirm',
    'ConnectionAcceptOrDeny',
    'ClientToServerHeartbeat',
    'ServerToClientHeartbeat',
    'GetOwnAddress',
    'GetOwnAddressReply',
    'NatPunchRequest', # 10
    'NatPunch', # 11
    'TransferBlockRequest',
    'TransferBlock',
    'RequestForHeartbeatWhenDisconnecting',
    'LANBroadcast',
    'GameInformationRequest',
    'GameInformationRequestReply',
    'Empty',
]

PINGPONG_SERVERS = [
    ('pingpong1.factorio.com', 34197),
    ('pingpong2.factorio.com', 34197),
    ('pingpong3.factorio.com', 34197),
    ('pingpong4.factorio.com', 34197),
]

def format_ip(ip):
    return ip if ':' not in ip else f'[{ip}]'

def format_addr(addr):
    return f'{format_ip(addr[0])}:{addr[1]}'

class PingClientProtocol:
    def __init__(self, addr, pingpong_servers, punch, quiet):
        self.transport = None
        self.sent = 0
        self.pings = {}
        self.in_flight = {}
        self.last_punch = 0
        self.addr = addr
        self.pingpong_servers = pingpong_servers
        self.send_punch = punch
        self.quiet = quiet

    def connection_made(self, transport):
        self.transport = transport

    def ping(self, seq):
        send_time = time.perf_counter_ns()
        if self.send_punch and (not self.last_punch or (send_time - self.last_punch) / 1e9 >= 1):
            self.last_punch = send_time
            self.punch()
        self.in_flight[seq & 0xffff] = (send_time, seq)
        self.transport.sendto(struct.pack("<BH", 0, seq & 0xffff), self.addr)
        #self.transport.get_extra_info("socket").sendto(struct.pack("<BH", 0, seq & 0xffff), self.addr[:2])
        self.sent += 1

    def punch(self):
        target = format_addr(self.addr).encode()
        self.transport.sendto(struct.pack("<BI", 10, len(target)) + target, random.choice(self.pingpong_servers))

    def datagram_received(self, data, addr):
        flags = data[0]
        net_type = flags & 0x1f
        if net_type == 1:
            crop_seq, = struct.unpack("<xH", data)
            try:
                send_time, seq = self.in_flight[crop_seq]
            except KeyError:
                if not self.quiet:
                    print(f"bogus PingReply from {format_addr(addr)}: seq={crop_seq}")
                return
            self.pings[seq] = (send_time, time.perf_counter_ns())
            self.send_punch = False
            if not self.quiet:
                print(f"PingReply from {format_addr(addr)}: seq={seq} time={(self.pings[seq][1] - self.pings[seq][0]) / 1e6}ms")

        elif net_type == 11:
            if not self.quiet:
                print(f"NatPunch from {format_addr(addr)}")
        else:
            packet_bytes = "".join(f" {hex(c)[2:]:>02}" for c in data)
            print(f"Uhandled message {MESSAGE_TYPE[net_type] if net_type < len(MESSAGE_TYPE) else 'Unknown'} ({net_type}):{packet_bytes}")
            return

    def error_received(self, exc):
        print(f"{type(exc).__name__}: {exc}")

    def connection_lost(self, exc):
        pass


async def ping_server(host, port, family, addr, interval, count, punch, pingpong_servers, quiet):
    loop = asyncio.get_running_loop()
    sock = socket.socket(family, type=socket.SOCK_DGRAM)
    if family == socket.AF_INET:
        sock.bind(('0.0.0.0', 0))
    elif family == socket.AF_INET6:
        sock.bind(('::1', 0, 0, 0))
    else:
        sock.close()
        raise ValueError("invalid address family")


    transport, protocol = await loop.create_datagram_endpoint(
        lambda: PingClientProtocol(addr, pingpong_servers, punch, quiet),
        sock=sock,
    )

    # delays smaller than 0.02 gets rounded down to 0 by asyncio sleep.
    if not interval > 0.02:
        interval = 1 / 30

    start = time.perf_counter_ns()
    try:
        for seq in itertools.count(0):
            protocol.ping(seq)
            if protocol.sent == count:
                break
            await asyncio.sleep(interval)
        await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass

    transport.close()
    received = len(protocol.pings)
    end = time.perf_counter_ns()
    times = [(p[1] - p[0]) / 1e6 for p in protocol.pings.values()]
    loss = round((protocol.sent - received) / protocol.sent * 100, 2)
    print()
    print(f"--- {host}:{port} ping statistics ---")
    print(f"{protocol.sent} packets sent, {received} received, {loss}% loss, time {(end - start) / 1e6:.2f}ms")
    if len(times):
        print(f"rtt min/avg/max/mdev {min(times):.2f}/{mean(times):.2f}/{max(times):.2f}/{pstdev(times):.2f}")

def ping(args):
    if args.ipv4 and args.ipv6:
        print("--ipv4/-4 and --ipv6/-6 are mutually exclusive")
        sys.exit(1)

    if args.ipv4:
        family = socket.AF_INET
    elif args.ipv6:
        family = socket.AF_INET6
    else:
        family = 0

    try:
        addrs = socket.getaddrinfo(args.target, args.port, family=family)
    except socket.gaierror:
        print(f"Unable to resolve {args.target}")
        sys.exit(1)

    family, addr = addrs[0][0], addrs[0][4]

    pingpong_servers = []
    if args.punch:
        for pingpong_server in PINGPONG_SERVERS:
            try:
                result = socket.getaddrinfo(*pingpong_server, family=family)
                pingpong_servers.append(result[0][4])
            except socket.gaierror:
                print(f"Unable to resolve {pingpong_server[0]}")
                sys.exit(1)

    # The ProactorEventLoop gives some random nonsense error on IPv6 ping of localhost
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    task = asyncio.ensure_future(ping_server(
        args.target, args.port, family, addr, args.interval, args.count, args.punch, pingpong_servers, args.quiet
    ), loop=loop)
    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        task.cancel()
        loop.run_until_complete(task)
