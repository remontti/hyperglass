"""Input validation functions for submitted queries."""

# Standard Library Imports
import operator
import re
from ipaddress import ip_network

# Project Imports
from hyperglass.configuration import params
from hyperglass.exceptions import InputInvalid
from hyperglass.exceptions import InputNotAllowed
from hyperglass.util import log


def _member_of(target, network):
    """Check if IP address belongs to network.

    Arguments:
        target {object} -- Target IPv4/IPv6 address
        network {object} -- ACL network

    Returns:
        {bool} -- True if target is a member of network, False if not
    """
    log.debug(f"Checking membership of {target} for {network}")

    membership = False
    if (
        network.network_address <= target.network_address
        and network.broadcast_address >= target.broadcast_address  # NOQA: W503
    ):
        log.debug(f"{target} is a member of {network}")
        membership = True
    return membership


def _prefix_range(target, ge, le):
    """Verify if target prefix length is within ge/le threshold.

    Arguments:
        target {IPv4Network|IPv6Network} -- Valid IPv4/IPv6 Network
        ge {int} -- Greater than
        le {int} -- Less than

    Returns:
        {bool} -- True if target in range; False if not
    """
    matched = False
    if target.prefixlen <= le and target.prefixlen >= ge:
        matched = True
    return matched


def validate_ip(value, query_type, query_vrf):  # noqa: C901
    """Ensure input IP address is both valid and not within restricted allocations.

    Arguments:
        value {str} -- Unvalidated IP Address
        query_type {str} -- Valid query type
        query_vrf {object} -- Matched query vrf
    Raises:
        ValueError: Raised if input IP address is not an IP address.
        ValueError: Raised if IP address is valid, but is within a restricted range.
    Returns:
        Union[IPv4Address, IPv6Address] -- Validated IP address object
    """
    query_type_params = getattr(params.queries, query_type)
    try:

        # Attempt to use IP object factory to create an IP address object
        valid_ip = ip_network(value)

    except ValueError:
        raise InputInvalid(
            params.messages.invalid_input,
            target=value,
            query_type=query_type_params.display_name,
        )

    """
    Test the valid IP address to determine if it is:
      - Unspecified (See RFC5735, RFC2373)
      - Loopback (See RFC5735, RFC2373)
      - Otherwise IETF Reserved
    ...and returns an error if so.
    """
    if valid_ip.is_reserved or valid_ip.is_unspecified or valid_ip.is_loopback:
        raise InputInvalid(
            params.messages.invalid_input,
            target=value,
            query_type=query_type_params.display_name,
        )

    ip_version = valid_ip.version
    if valid_ip.num_addresses == 1:

        if query_type in ("ping", "traceroute"):
            new_ip = valid_ip.network_address

            log.debug(
                "Converted '{o}' to '{n}' for '{q}' query",
                o=valid_ip,
                n=new_ip,
                q=query_type,
            )

            valid_ip = new_ip

        elif query_type in ("bgp_route",):
            max_le = max(
                ace.le
                for ace in query_vrf[ip_version].access_list
                if ace.action == "permit"
            )
            new_ip = valid_ip.supernet(new_prefix=max_le)

            log.debug(
                "Converted '{o}' to '{n}' for '{q}' query",
                o=valid_ip,
                n=new_ip,
                q=query_type,
            )

            valid_ip = new_ip

    vrf_acl = operator.attrgetter(f"ipv{ip_version}.access_list")(query_vrf)

    for ace in [a for a in vrf_acl if a.network.version == ip_version]:
        if _member_of(valid_ip, ace.network):
            if query_type == "bgp_route" and _prefix_range(valid_ip, ace.ge, ace.le):
                pass

            if ace.action == "permit":
                log.debug(
                    "{t} is allowed by access-list {a}", t=str(valid_ip), a=repr(ace)
                )
                break
            elif ace.action == "deny":
                raise InputNotAllowed(
                    params.messages.acl_denied,
                    target=str(valid_ip),
                    denied_network=str(ace.network),
                )
    log.debug("Validation passed for {ip}", ip=value)
    return valid_ip


def validate_community(value):
    """Validate input communities against configured or default regex pattern."""

    # RFC4360: Extended Communities (New Format)
    if re.match(params.queries.bgp_community.pattern.extended_as, value):
        pass

    # RFC4360: Extended Communities (32 Bit Format)
    elif re.match(params.queries.bgp_community.pattern.decimal, value):
        pass

    # RFC8092: Large Communities
    elif re.match(params.queries.bgp_community.pattern.large, value):
        pass

    else:
        raise InputInvalid(
            params.messages.invalid_input,
            target=value,
            query_type=params.queries.bgp_community.display_name,
        )
    return value


def validate_aspath(value):
    """Validate input AS_PATH against configured or default regext pattern."""

    mode = params.queries.bgp_aspath.pattern.mode
    pattern = getattr(params.queries.bgp_aspath.pattern, mode)

    if not re.match(pattern, value):
        raise InputInvalid(
            params.messages.invalid_input,
            target=value,
            query_type=params.queries.bgp_aspath.display_name,
        )

    return value
