use std::{
    collections::BTreeSet,
    io::{self, Error, ErrorKind},
    net::{Ipv4Addr, SocketAddr, SocketAddrV4, UdpSocket},
    time::{Duration, Instant},
};

pub const DISCOVERY_PORT: u16 = 12346;
pub const REQUEST: &[u8] = b"KOHDALAB_SHUTTER_DISCOVER_V1";

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Device {
    pub id: String,
    pub address: SocketAddr,
}

pub fn parse_reply(data: &[u8], source: SocketAddr) -> Option<Device> {
    let text = std::str::from_utf8(data).ok()?;
    let parts: Vec<_> = text.split_whitespace().collect();
    if parts.len() != 3
        || parts[0] != "KOHDALAB_SHUTTER_V1"
        || parts[1].is_empty()
        || parts[1].len() > 64
        || !parts[1].bytes().all(|b| b.is_ascii_hexdigit())
    {
        return None;
    }
    let port: u16 = parts[2].parse().ok()?;
    if port == 0 {
        return None;
    }
    Some(Device {
        id: parts[1].to_ascii_lowercase(),
        address: SocketAddr::new(source.ip(), port),
    })
}

/// Discover without issuing any shutter commands. Target may be a subnet's
/// directed broadcast address, or a unicast address for diagnostics/testing.
pub fn discover(target: SocketAddrV4, timeout: Duration) -> io::Result<Vec<Device>> {
    if timeout.is_zero() {
        return Err(Error::new(
            ErrorKind::InvalidInput,
            "Discovery timeout must be positive",
        ));
    }
    let socket = UdpSocket::bind((Ipv4Addr::UNSPECIFIED, 0))?;
    socket.set_broadcast(true)?;
    let deadline = Instant::now() + timeout;
    let mut next_send = Instant::now();
    let mut devices = BTreeSet::new();
    let mut buffer = [0; 512];
    loop {
        let now = Instant::now();
        if now >= deadline {
            break;
        }
        if now >= next_send {
            socket.send_to(REQUEST, target)?;
            next_send = now + Duration::from_millis(400);
        }
        socket.set_read_timeout(Some(
            (deadline - now)
                .min(next_send.saturating_duration_since(now))
                .max(Duration::from_millis(1)),
        ))?;
        match socket.recv_from(&mut buffer) {
            Ok((count, source)) => {
                if let Some(device) = parse_reply(&buffer[..count], source) {
                    devices.insert(device);
                }
            }
            Err(e)
                if matches!(
                    e.kind(),
                    ErrorKind::WouldBlock | ErrorKind::TimedOut | ErrorKind::Interrupted
                ) => {}
            Err(e) => return Err(e),
        }
    }
    Ok(devices.into_iter().collect())
}

pub fn default_target() -> SocketAddrV4 {
    SocketAddrV4::new(Ipv4Addr::BROADCAST, DISCOVERY_PORT)
}

pub fn select_device(devices: &[Device], id: Option<&str>) -> io::Result<Device> {
    let matching: Vec<_> = devices
        .iter()
        .filter(|d| id.is_none_or(|id| d.id.eq_ignore_ascii_case(id)))
        .collect();
    match matching.as_slice() {
        [device] => Ok((*device).clone()),
        [] => Err(Error::new(
            ErrorKind::NotFound,
            "Pico W not found. Start its server; check Wi-Fi/firewall, try --broadcast <subnet-broadcast>, or inspect via USB (docs/rust-client.md).",
        )),
        _ => Err(Error::other(
            "Multiple Pico W devices found. Use discover, then --device <id> or --host <IP> to select one.",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validates_reply_and_uses_source_ip() {
        let source = "127.0.0.1:55555".parse().unwrap();
        let device = parse_reply(b"KOHDALAB_SHUTTER_V1 A0ff 12345", source).unwrap();
        assert_eq!(device.address.to_string(), "127.0.0.1:12345");
        assert_eq!(device.id, "a0ff");
        for data in [
            "OTHER a0ff 12345",
            "KOHDALAB_SHUTTER_V1 zz 12345",
            "KOHDALAB_SHUTTER_V1 aa 0",
            "KOHDALAB_SHUTTER_V1 aa 65536",
            "KOHDALAB_SHUTTER_V1 aa 1 extra",
        ] {
            assert!(parse_reply(data.as_bytes(), source).is_none());
        }
        assert!(parse_reply(&[255], source).is_none());
    }
    #[test]
    fn never_chooses_an_arbitrary_device() {
        let a = Device {
            id: "aa".into(),
            address: "127.0.0.1:1".parse().unwrap(),
        };
        let b = Device {
            id: "bb".into(),
            address: "127.0.0.1:2".parse().unwrap(),
        };
        assert!(select_device(&[], None).is_err());
        assert_eq!(select_device(std::slice::from_ref(&a), None).unwrap(), a);
        assert!(select_device(&[a.clone(), b.clone()], None).is_err());
        assert_eq!(select_device(&[a, b.clone()], Some("BB")).unwrap(), b);
    }
    #[test]
    fn real_udp_discovery_ignores_invalid_and_deduplicates() {
        let server = UdpSocket::bind("127.0.0.1:0").unwrap();
        server
            .set_read_timeout(Some(Duration::from_secs(2)))
            .unwrap();
        let SocketAddr::V4(target) = server.local_addr().unwrap() else {
            unreachable!()
        };
        let worker = std::thread::spawn(move || {
            let mut buf = [0; 512];
            let (n, peer) = server.recv_from(&mut buf).unwrap();
            assert_eq!(&buf[..n], REQUEST);
            for reply in [
                "invalid",
                "KOHDALAB_SHUTTER_V1 ab12 12345",
                "KOHDALAB_SHUTTER_V1 ab12 12345",
            ] {
                server.send_to(reply.as_bytes(), peer).unwrap();
            }
        });
        let devices = discover(target, Duration::from_millis(150)).unwrap();
        worker.join().unwrap();
        assert_eq!(devices.len(), 1);
        assert_eq!(devices[0].address.to_string(), "127.0.0.1:12345");
        assert!(discover(target, Duration::ZERO).is_err());
    }
}
