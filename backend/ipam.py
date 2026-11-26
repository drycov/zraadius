"""Bounded inventory pools; no materialization of IPv6 subnets."""
import ipaddress

def pool_bounds(cidr, first=None, last=None):
    net=ipaddress.ip_network(cidr,strict=True)
    lo=int(net.network_address)
    hi=int(net.broadcast_address)
    if net.version==4 and net.prefixlen<31:
        lo+=1
        hi-=1
    elif net.version==6 and net.prefixlen<127:
        lo+=1
    if net.is_multicast or net.is_unspecified and net.prefixlen==net.max_prefixlen:
        raise ValueError("Invalid network")
    for value in (first,last):
        if value is not None:
            ip=ipaddress.ip_address(value)
            if ip.version!=net.version or not lo<=int(ip)<=hi:
                raise ValueError("Address outside usable network")
    a=int(ipaddress.ip_address(first)) if first is not None else lo
    b=int(ipaddress.ip_address(last)) if last is not None else hi
    if a>b:
        raise ValueError("Invalid range")
    cls=ipaddress.IPv4Address if net.version==4 else ipaddress.IPv6Address
    return str(net),str(cls(a)),str(cls(b)),b-a+1

def next_address(first,last,occupied):
    start=ipaddress.ip_address(first)
    end=ipaddress.ip_address(last)
    candidate=int(start)
    for value in occupied:
        n=int(ipaddress.ip_address(value))
        if n<candidate:
            continue
        if n>candidate:
            break
        candidate+=1
    if candidate>int(end):
        return None
    return str(type(start)(candidate))
