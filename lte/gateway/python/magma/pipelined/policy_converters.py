"""
Copyright 2020 The Magma Authors.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import ipaddress

from lte.protos.policydb_pb2 import FlowMatch
from lte.protos.mobilityd_pb2 import IPAddress
from magma.pipelined.openflow.magma_match import MagmaMatch
from magma.pipelined.openflow.registers import Direction, load_direction, \
    DPI_REG

from ryu.lib.packet import ether_types


class FlowMatchError(Exception):
    pass


def _check_pkt_protocol(match):
    '''
    Verify that the match flags are set properly

    Args:
        match: FlowMatch
    '''
    if (match.tcp_dst or match.tcp_src) and (match.ip_proto !=
                                             match.IPPROTO_TCP):
        raise FlowMatchError("To use tcp rules set ip_proto to IPPROTO_TCP")
    if (match.udp_dst or match.udp_src) and (match.ip_proto !=
                                             match.IPPROTO_UDP):
        raise FlowMatchError("To use udp rules set ip_proto to IPPROTO_UDP")
    return True


def flow_match_to_magma_match(match, ip_addr=None):
    '''
    Convert a FlowMatch to a MagmaMatch object

    Args:
        match: FlowMatch
    '''
    _check_pkt_protocol(match)
    match_kwargs = {'eth_type': ether_types.ETH_TYPE_IP}
    attributes = ['ip_dst', 'ip_src',
                  'ip_proto', 'tcp_src', 'tcp_dst',
                  'udp_src', 'udp_dst', 'app_name']
    for attrib in attributes:
        value = getattr(match, attrib, None)
        if not value:
            continue
        if attrib in {'ip_dst', 'ip_src'}:
            if not value.address:
                continue
            value = _get_ip_tuple(value.address.decode('utf-8'))
            if value is None:
                return
            # TODO add ipv6
            if attrib == 'ip_src':
                match_kwargs['ipv4_src'] = value
            elif attrib == 'ip_dst':
                match_kwargs['ipv4_dst'] = value
            continue

        if attrib == 'app_name':
            attrib = DPI_REG

        match_kwargs[attrib] = value

    if ip_addr:
        if ip_addr.version == ip_addr.IPV4:
            ip_src_reg = 'ipv4_src'
            ip_dst_reg = 'ipv4_dst'
        else:
            ip_src_reg = 'ipv6_src'
            ip_dst_reg = 'ipv6_dst'

        if ip_addr.address.decode('utf-8'):
            if _get_direction_for_match(match) == Direction.OUT:
                match_kwargs[ip_src_reg] = ip_addr.address.decode('utf-8')
            else:
                match_kwargs[ip_dst_reg] = ip_addr.address.decode('utf-8')

    return MagmaMatch(direction=_get_direction_for_match(match),
                      **match_kwargs)


def flow_match_to_actions(datapath, match):
    '''
    Convert a FlowMatch to list of actions to get the same packet

    Args:
        match: FlowMatch
    '''
    parser = datapath.ofproto_parser
    _check_pkt_protocol(match)
    # Eth type and ip proto are read only, can't set them here (set on pkt init)
    actions = [
        parser.OFPActionSetField(ipv4_src=getattr(match, 'ipv4_src', '1.1.1.1')),
        parser.OFPActionSetField(ipv4_dst=getattr(match, 'ipv4_dst', '1.2.3.4')),
        load_direction(parser, _get_direction_for_match(match)),
        parser.NXActionRegLoad2(dst=DPI_REG, value=getattr(match, 'app_id', 0)),
    ]
    if match.ip_proto == FlowMatch.IPPROTO_TCP:
        actions.extend([
            parser.OFPActionSetField(tcp_src=getattr(match, 'tcp_src', 0)),
            parser.OFPActionSetField(tcp_dst=getattr(match, 'tcp_dst', 0))
        ])
    elif match.ip_proto == FlowMatch.IPPROTO_UDP:
        actions.extend([
            parser.OFPActionSetField(udp_src=getattr(match, 'udp_src', 0)),
            parser.OFPActionSetField(udp_dst=getattr(match, 'udp_dst', 0))
        ])
    return actions


def flip_flow_match(match):
    '''
    Flips FlowMatch(ip/ports/direction)

    Args:
        match: FlowMatch
    '''
    if getattr(match, 'direction', None) == match.DOWNLINK:
        direction = match.UPLINK
    else:
        direction = match.DOWNLINK

    return FlowMatch(
        ip_src=getattr(match, 'ip_dst', None),
        ip_dst=getattr(match, 'ip_src', None),
        tcp_src=getattr(match, 'tcp_dst', None),
        tcp_dst=getattr(match, 'tcp_src', None),
        udp_src=getattr(match, 'udp_dst', None),
        udp_dst=getattr(match, 'udp_src', None),
        ip_proto=getattr(match, 'ip_proto', None),
        direction=direction,
        app_name=getattr(match, 'app_name', None)
    )


def get_ue_ipv4_match_args(ip_addr, direction):
    ip_match = {}

    if ip_addr:
        if ip_addr.version == ip_addr.IPV4:
            ip_src_reg = 'ipv4_src'
            ip_dst_reg = 'ipv4_dst'
        else:
            ip_src_reg = 'ipv6_src'
            ip_dst_reg = 'ipv6_dst'

        if not ip_addr.address.decode('utf-8'):
            return ip_match

        if direction == Direction.OUT:
            ip_match = {ip_src_reg: ip_addr.address.decode('utf-8')}
        else:
            ip_match = {ip_dst_reg: ip_addr.address.decode('utf-8')}
    return ip_match


def _get_ip_tuple(ip_str):
    '''
    Convert an ip string to a formatted block tuple

    Args:
        ip_str (string): ip string to parse
    '''
    try:
        ip_block = ipaddress.ip_network(ip_str)
    except ValueError as err:
        raise FlowMatchError("Invalid Ip block: %s" % err)
    block_tuple = '{}'.format(ip_block.network_address),\
                  '{}'.format(ip_block.netmask)
    return block_tuple


def _get_direction_for_match(flow_match):
    if flow_match.direction == flow_match.UPLINK:
        return Direction.OUT
    return Direction.IN


def convert_ipv4_str_to_ip_proto(ipv4_str):
    return IPAddress(version=IPAddress.IPV4,
                     address=ipv4_str.encode('utf-8'))


def convert_ipv6_bytes_to_ip_proto(ipv6_str):
    return IPAddress(version=IPAddress.IPV6,
                     address=ipv6_str)
