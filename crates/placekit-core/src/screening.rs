//! The redirect and base URL screening family: judging the
//! hosts a configured base or a photo redirect may name, on
//! the parsed host alone. The family moved out of the client
//! module so the screening rules, which carry the crate's
//! network trust decisions, read on their own (audit
//! A50-160). Judged spellings and refusal texts are untouched.

use crate::errors::Error;

/// Whether the parsed host of a URL is loopback: the name
/// `localhost` or a name under it, in any case and with an optional
/// trailing dot, or an IP literal in a loopback range. The check
/// reads the parsed host only, because the URL parser canonicalises
/// spellings such as a hex or decimal IPv4 address to the dotted
/// form before this runs (red team R3), so a check on the raw
/// string would misread exactly the spellings worth catching. An
/// IPv6 literal that embeds an IPv4 address is judged by the
/// address it embeds, so the mapped, compatible,
/// translation and tunneling spellings of a loopback address
/// read as loopback here.
fn host_is_loopback(url: &reqwest::Url) -> bool {
    match url.host() {
        Some(url::Host::Domain(name)) => {
            let name = name.trim_end_matches('.').to_ascii_lowercase();
            name == "localhost" || name.ends_with(".localhost")
        }
        Some(url::Host::Ipv4(ip)) => ip.is_loopback(),
        Some(url::Host::Ipv6(ip)) => {
            ip.is_loopback() || ipv6_embedded_ipv4(ip).is_some_and(|v4| v4.is_loopback())
        }
        None => false,
    }
}

/// The host of a URL as an IP address, when the host is an IP
/// literal rather than a name.
fn host_ip(url: &reqwest::Url) -> Option<std::net::IpAddr> {
    match url.host() {
        Some(url::Host::Ipv4(ip)) => Some(std::net::IpAddr::V4(ip)),
        Some(url::Host::Ipv6(ip)) => Some(std::net::IpAddr::V6(ip)),
        _ => None,
    }
}

/// The IPv4 address an IPv6 literal embeds, when it carries one.
/// The IPv4-mapped form and the older IPv4-compatible form both
/// name an IPv4 address in their last 32 bits, and dual stack
/// sockets deliver them to that address. The translation forms
/// name an IPv4 address too, and a translator on the network
/// path delivers them to that address on the same reasoning: the
/// NAT64 well-known prefix 64:ff9b::/96 and the IPv4-translated
/// prefix ::ffff:0:0/96 both carry the address in their last 32
/// bits, and the NAT64 local-use prefix 64:ff9b:1::/48 can carry
/// it in two places, under the RFC 6052 layout for that prefix
/// length in segment 3, the low byte of segment 4 and the high
/// byte of segment 5 (the byte between the two halves is the
/// reserved u octet the layout sets to zero), and in the last
/// 32 bits under a /96 length. A screen cannot know the prefix
/// length the network is configured with, so either position
/// counts as the embedding, and where the two positions carry
/// different addresses the one a screen must act on wins, a
/// loopback address first, a non-public address next, and the
/// unspecified address ahead of a public one, because its
/// dotted form is refused for naming the local host and a
/// zero position is the only cover it could hide behind.
/// The tunneling forms name an IPv4 address too, and the
/// tunnel delivers to it: the 6to4 prefix 2002::/16 carries
/// the site address in segments 1 and 2, and the Teredo
/// prefix 2001:0000::/32 carries the client address, the
/// host a connection to the address is delivered to, in
/// the last 32 bits XORed with all ones. The Teredo server
/// address in segments 2 and 3 names the tunnel server the
/// client chose, not a delivery candidate, so it is not
/// extracted: judging by it could grant loopback trust to
/// a delivery that goes to the client (audit A50-006).
/// The unspecified address and the IPv6 loopback
/// address are not embeddings, they are addresses in their
/// own right, so they return None here and keep their IPv6
/// reading.
pub(crate) fn ipv6_embedded_ipv4(ip: std::net::Ipv6Addr) -> Option<std::net::Ipv4Addr> {
    if ip.is_unspecified() || ip.is_loopback() {
        return None;
    }
    if let Some(v4) = ip.to_ipv4() {
        return Some(v4);
    }
    let segments = ip.segments();
    let from_pair =
        |high: u16, low: u16| std::net::Ipv4Addr::from(((high as u32) << 16) | (low as u32));
    let low = from_pair(segments[6], segments[7]);
    match segments {
        // The NAT64 well-known prefix and the IPv4-translated
        // prefix carry the embedded address in the last 32 bits.
        [0x0064, 0xff9b, 0, 0, 0, 0, _, _] | [0, 0, 0, 0, 0xffff, 0, _, _] => Some(low),
        [0x0064, 0xff9b, 0x0001, _, _, _, _, _] => {
            // The local-use prefix, judged at both embedding
            // positions (see the doc comment). The /48 position
            // reads by the RFC 6052 layout for that length,
            // segment 3, then the low byte of segment 4 and the
            // high byte of segment 5, stepping over the reserved
            // u octet in the high byte of segment 4. When both
            // positions carry an address and they differ, the
            // one a screen must act on wins, a loopback address
            // first, a non-public address next, and the
            // unspecified address ahead of a public one, because
            // its dotted form is refused for naming the local
            // host and a zero position is the only cover it
            // could hide behind, so neither position can hide
            // the other from the consumers of this helper.
            let routed = std::net::Ipv4Addr::from(
                ((segments[3] as u32) << 16)
                    | (((segments[4] as u32) & 0xff) << 8)
                    | ((segments[5] as u32) >> 8),
            );
            Some(judge_embedded_pair(routed, low))
        }
        // The 6to4 prefix carries the site address in
        // segments 1 and 2 (audit A50-006).
        [0x2002, _, _, _, _, _, _, _] => Some(from_pair(segments[1], segments[2])),
        // The Teredo prefix delivers to the client address
        // in the last 32 bits XORed with all ones (audit
        // A50-006). The server address in segments 2 and 3
        // names the client's tunnel server, not a delivery
        // candidate, and is not judged.
        [0x2001, 0x0000, _, _, _, _, _, _] => {
            Some(from_pair(segments[6] ^ 0xffff, segments[7] ^ 0xffff))
        }
        _ => None,
    }
}

/// Judge the two candidate addresses of one spelling that
/// carries an IPv4 address in two positions. The address a
/// screen must act on wins, a loopback address first, a
/// non-public address next, and the unspecified address
/// ahead of a public one, because its dotted form is
/// refused for naming the local host and a zero position
/// is the only cover it could hide behind. When neither
/// position escalates, the primary stands, as the position
/// the spelling delivers to by default.
fn judge_embedded_pair(
    primary: std::net::Ipv4Addr,
    secondary: std::net::Ipv4Addr,
) -> std::net::Ipv4Addr {
    if primary.is_loopback() {
        primary
    } else if secondary.is_loopback() {
        secondary
    } else if ipv4_is_non_public(primary) && !primary.is_unspecified() {
        primary
    } else if ipv4_is_non_public(secondary) && !secondary.is_unspecified() {
        secondary
    } else if primary.is_unspecified() || secondary.is_unspecified() {
        std::net::Ipv4Addr::UNSPECIFIED
    } else {
        primary
    }
}

/// Whether an IPv4 address names a non-public address: a private
/// range, a link local range, the unspecified address, the whole
/// 0.0.0.0/8 this network range, whose single unspecified member
/// is the only address in it the standard library names, and the
/// 100.64.0.0/10 shared address space, which the standard library
/// does not count as private. Both extra ranges are IANA special
/// purpose space that can name the local host or internal
/// infrastructure.
fn ipv4_is_non_public(v4: std::net::Ipv4Addr) -> bool {
    let octets = v4.octets();
    v4.is_private()
        || v4.is_link_local()
        || v4.is_unspecified()
        || octets[0] == 0
        || (octets[0] == 100 && (octets[1] & 0b1100_0000) == 0b0100_0000)
}

/// Whether an IP literal names a non-public address: a private
/// range, a link local range, or the unspecified address. Loopback
/// is judged separately by [`host_is_loopback`], because its
/// treatment depends on the configured base. An IPv6 literal that
/// embeds an IPv4 address is judged by the address it embeds, so
/// the mapped, compatible, translation and tunneling spellings
/// of a private address cannot walk past the screen their
/// dotted spelling fails (Round 18 landing red team).
fn ip_is_non_public(ip: std::net::IpAddr) -> bool {
    match ip {
        std::net::IpAddr::V4(v4) => ipv4_is_non_public(v4),
        std::net::IpAddr::V6(v6) => {
            v6.is_unique_local()
                || v6.is_unicast_link_local()
                || v6.is_unspecified()
                || ipv6_embedded_ipv4(v6).is_some_and(ipv4_is_non_public)
        }
    }
}

/// Screen one photo redirect hop before it is followed (R18-A3).
/// Whoever answers the media request chooses the `Location`, so an
/// unscreened follower is a GET client against whatever that answer
/// names, including internal network addresses, with an https to
/// http downgrade available on the hop. A hop is followed only when
/// it stays inside the trust the configured base already carries:
///
/// - A target carrying userinfo is refused outright. The HTTP
///   layer promotes userinfo into an Authorization Basic header on
///   the followed request (red team R2), so such a hop would
///   present credentials its author chose to the named host.
/// - An https target is followed unless it names a loopback host
///   the base does not share, or a non-public IP literal.
/// - A plain http target is followed only inside the local
///   configuration, a loopback base steering to a loopback target,
///   which is the posture the base URL itself is held to (R18-A5)
///   and the shape the test stub serves photos in.
/// - Hostnames other than the loopback names are followed as
///   before. Screening a name would mean resolving it here, and
///   the answer could still change before the connection; that
///   residual is recorded in the Round 18 build report rather than
///   engineered around.
///
/// The refusal names the reason class only, never the target, so
/// nothing the redirect author chose (a password above all) can
/// ride into the caller's error text.
pub(crate) fn screen_redirect_target(
    base: &reqwest::Url,
    target: &reqwest::Url,
) -> Result<(), Error> {
    let refuse = |reason: &str| {
        Error::network_detail(format!(
            "redirect: refusing to follow the photo redirect: {reason}"
        ))
    };
    if !target.username().is_empty() || target.password().is_some() {
        return Err(refuse("the target carries credentials (userinfo)"));
    }
    if target.host_str().is_none() {
        return Err(refuse("the target names no host"));
    }
    let base_loopback = host_is_loopback(base);
    let target_loopback = host_is_loopback(target);
    match target.scheme() {
        "https" => {
            if target_loopback && !base_loopback {
                return Err(refuse("the target is a loopback address"));
            }
            if let Some(ip) = host_ip(target) {
                if ip_is_non_public(ip) {
                    return Err(refuse("the target is a non-public IP address"));
                }
            }
            Ok(())
        }
        "http" => {
            if base_loopback && target_loopback {
                Ok(())
            } else {
                Err(refuse("the target uses plain http"))
            }
        }
        _ => Err(refuse("the target scheme is not http or https")),
    }
}

/// Parse and normalize a configured base URL (R4-02). The value used
/// to be interpolated unchecked, so a base carrying a query string or
/// a fragment silently rerouted every request (the endpoint path
/// landed inside the query) and still built. Now the base must parse,
/// must be http or https with a host, and must carry neither a query
/// nor a fragment nor embedded credentials. Parsing also resolves dot
/// segments in the path, so
/// a configured prefix cannot be escaped by the appended endpoint
/// path. A trailing slash is trimmed as before, and path prefixes
/// (the documented stub form `http://host:port/v1`) keep working.
/// Plain http is accepted for loopback hosts only (R18-A5): it sends
/// both key forms, the header and the photo key query, over a
/// connection anyone on the path can read and modify, so a network
/// host must be reached over https.
pub(crate) fn parse_base_url(raw: &str) -> Result<String, Error> {
    let url = url::Url::parse(raw.trim())
        .map_err(|e| Error::config(format!("base_url is not a valid URL: {e}")))?;
    if url.scheme() != "http" && url.scheme() != "https" {
        return Err(Error::config(format!(
            "base_url scheme must be http or https, got {:?}",
            url.scheme()
        )));
    }
    if url.host_str().is_none() {
        return Err(Error::config("base_url must name a host"));
    }
    if url.query().is_some() || url.fragment().is_some() {
        return Err(Error::config(
            "base_url must not carry a query string or a fragment",
        ));
    }
    if !url.username().is_empty() || url.password().is_some() {
        // Embedded credentials are not inert text in the base: the
        // HTTP layer turns userinfo into an Authorization Basic
        // header sent to the API host on every request, invisible to
        // the caller. Credentials do not belong in a base URL.
        return Err(Error::config(
            "base_url must not carry credentials (userinfo)",
        ));
    }
    if url.scheme() == "http" && !host_is_loopback(&url) {
        // Classification reads the parsed host, never the raw
        // string, because the parser canonicalises spellings such
        // as a hex IPv4 address to the dotted form before this
        // runs (red team R3).
        return Err(Error::config(
            "base_url scheme http is only allowed for a loopback host; use https",
        ));
    }
    Ok(url.to_string().trim_end_matches('/').to_owned())
}
