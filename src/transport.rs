use crate::{
    protocol::{Operation, Snapshot, Status, parse_state, parse_status},
    session::{ControllerInfo, invalid, parse_info},
};
use serde_json::{Value, json};
use std::{
    io::{self, Error, ErrorKind, Read, Write},
    net::{TcpStream, ToSocketAddrs},
    thread,
    time::{Duration, Instant},
};

#[derive(Clone)]
pub struct Client {
    pub host: String,
    pub port: u16,
    pub timeout: Duration,
    pub retries: u8,
    token: Option<String>,
}

impl std::fmt::Debug for Client {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("Client")
            .field("host", &self.host)
            .field("port", &self.port)
            .field("timeout", &self.timeout)
            .field("retries", &self.retries)
            .field("session", &self.token.as_ref().map(|_| "active"))
            .finish()
    }
}

impl Client {
    pub fn new(host: String, port: u16, timeout: Duration, retries: u8) -> io::Result<Self> {
        if host.trim().is_empty() || port == 0 || timeout.is_zero() || retries == 0 {
            return Err(Error::new(
                ErrorKind::InvalidInput,
                "Host, port, timeout and retries must be non-empty/positive",
            ));
        }
        Ok(Self {
            host,
            port,
            timeout,
            retries,
            token: None,
        })
    }

    pub fn status(&self) -> io::Result<Status> {
        parse_status(&self.send("STATUS", true)?)
    }

    pub fn snapshot(&self) -> io::Result<Snapshot> {
        let raw = self.send("STATE", true)?;
        if raw == "UNKNOWN" {
            return self.status().map(Snapshot::legacy);
        }
        parse_state(&raw)
    }

    pub fn operate(&self, operation: Operation, channel: u8) -> io::Result<()> {
        if self.token.is_some() {
            return self.operate_many(operation, &[channel]);
        }
        let command = operation.command(channel)?;
        let response = self.send(&command, operation != Operation::Toggle)?;
        if response != "OK" {
            return Err(Error::other(format!("Pico rejected {command}: {response}")));
        }
        Ok(())
    }

    /// Read the shared controller label and the current lock state without
    /// acquiring any shutters.
    pub fn info(&self) -> io::Result<ControllerInfo> {
        parse_info(self.session("info", json!({}), true)?)
    }

    /// Store a human-readable controller label when no channels are leased.
    pub fn set_label(&self, label: &str) -> io::Result<()> {
        validate_label(label)?;
        self.session("set_label", json!({"label": label}), true)?;
        Ok(())
    }

    /// Acquire all requested shutters atomically. The returned clone holds an
    /// opaque session token; it is deliberately not exposed or printed.
    pub fn claim(&self, channels: &[u8]) -> io::Result<Self> {
        validate_channels(channels)?;
        let token = uuid::Uuid::new_v4().simple().to_string();
        self.claim_with_token(channels, token)
    }

    fn claim_with_token(&self, channels: &[u8], token: String) -> io::Result<Self> {
        validate_channels(channels)?;
        self.session("claim", json!({"token": token, "channels": channels}), true)?;
        Ok(Self {
            host: self.host.clone(),
            port: self.port,
            timeout: self.timeout,
            retries: self.retries,
            token: Some(token),
        })
    }

    /// Extend the active session lease. Calling this on an unclaimed client is
    /// an error so callers cannot accidentally believe a lock exists.
    pub fn renew(&self) -> io::Result<()> {
        self.session_with_token("renew", json!({}), true)?;
        Ok(())
    }

    /// Release this client's channels. It is idempotent at the Pico protocol
    /// level and a no-op for clients that never acquired a lease.
    pub fn release(&self) -> io::Result<()> {
        let Some(_) = self.token else {
            return Ok(());
        };
        self.session_with_token("release", json!({}), true)?;
        Ok(())
    }

    /// Perform one all-or-nothing action over channels owned by this session.
    pub fn operate_many(&self, operation: Operation, channels: &[u8]) -> io::Result<()> {
        validate_channels(channels)?;
        let action = match operation {
            Operation::Open => "open",
            Operation::Close => "close",
            Operation::Toggle => "toggle",
        };
        // Toggle is intentionally never retried: a lost reply leaves the
        // physical outcome ambiguous. Open and Close are idempotent.
        self.session_with_token(
            "operate",
            json!({"action": action, "channels": channels}),
            operation != Operation::Toggle,
        )?;
        Ok(())
    }

    fn session_with_token(&self, operation: &str, value: Value, retry: bool) -> io::Result<Value> {
        let token = self.token.as_deref().ok_or_else(|| {
            Error::new(
                ErrorKind::PermissionDenied,
                "Acquire shutter channels before controlling them",
            )
        })?;
        self.session(operation, merge(value, json!({"token": token})), retry)
    }

    fn session(&self, operation: &str, value: Value, retry: bool) -> io::Result<Value> {
        let command = format!("SESSION {}", merge(value, json!({"op": operation})));
        let raw = self.send(&command, retry)?;
        if raw == "UNKNOWN" {
            return Err(invalid(
                "Update Pico firmware: upload sessions.py and the updated main.py",
            ));
        }
        let value: Value = serde_json::from_str(&raw)
            .map_err(|_| invalid("Invalid session response from Pico W"))?;
        let object = value
            .as_object()
            .ok_or_else(|| invalid("Invalid session response from Pico W"))?;
        match object.get("ok").and_then(Value::as_bool) {
            Some(true) => Ok(value),
            Some(false) => {
                let code = object
                    .get("error")
                    .and_then(Value::as_str)
                    .unwrap_or("invalid_request");
                let kind = match code {
                    "busy" => ErrorKind::WouldBlock,
                    "lease_lost" => ErrorKind::PermissionDenied,
                    "storage" => ErrorKind::Other,
                    "invalid_request" => ErrorKind::InvalidInput,
                    _ => ErrorKind::InvalidData,
                };
                Err(Error::new(
                    kind,
                    format!("Pico session rejected request: {code}"),
                ))
            }
            None => Err(invalid("Invalid session response from Pico W")),
        }
    }

    fn send(&self, command: &str, retry: bool) -> io::Result<String> {
        let attempts = if retry { self.retries } else { 1 };
        let mut last_error = Error::other("No connection attempt made");
        for attempt in 0..attempts {
            match self.send_once(command) {
                Ok(response) => return Ok(response),
                Err(e) if e.kind() == ErrorKind::InvalidData => return Err(e),
                Err(e) => last_error = e,
            }
            if attempt + 1 < attempts {
                thread::sleep(Duration::from_millis(100 * (1u64 << attempt.min(4))));
            }
        }
        let ambiguity = if !retry {
            " TOGGLE was attempted once; its outcome may be unknown. Check STATUS before another action."
        } else {
            ""
        };
        Err(Error::new(
            last_error.kind(),
            format!(
                "Cannot communicate with {}:{} after {attempts} attempt(s): {last_error}.{ambiguity}",
                self.host, self.port
            ),
        ))
    }

    fn send_once(&self, command: &str) -> io::Result<String> {
        let deadline = Instant::now() + self.timeout;
        let addresses = (self.host.as_str(), self.port).to_socket_addrs()?;
        let mut socket = None;
        let mut last_error = Error::new(ErrorKind::NotFound, "Host has no addresses");
        for address in addresses {
            let remaining = remaining(deadline)?;
            match TcpStream::connect_timeout(&address, remaining) {
                Ok(stream) => {
                    socket = Some(stream);
                    break;
                }
                Err(e) => last_error = e,
            }
        }
        let mut socket = socket.ok_or(last_error)?;
        socket.set_write_timeout(Some(remaining(deadline)?))?;
        socket.write_all(format!("{command}\n").as_bytes())?;
        let mut response = Vec::new();
        loop {
            socket.set_read_timeout(Some(remaining(deadline)?))?;
            let mut byte = [0];
            if socket.read(&mut byte)? == 0 {
                return Err(Error::new(
                    ErrorKind::UnexpectedEof,
                    "Pico closed connection before a complete response",
                ));
            }
            if byte[0] == b'\n' {
                break;
            }
            response.push(byte[0]);
            if response.len() > 4096 {
                return Err(Error::new(
                    ErrorKind::InvalidData,
                    "Pico response exceeds 4096 bytes",
                ));
            }
        }
        let response = String::from_utf8(response)
            .map_err(|_| Error::new(ErrorKind::InvalidData, "Pico response is not UTF-8"))?;
        if response.trim().is_empty() {
            return Err(Error::new(ErrorKind::InvalidData, "Empty Pico response"));
        }
        Ok(response.trim().to_owned())
    }
}

fn merge(mut left: Value, right: Value) -> Value {
    let left = left.as_object_mut().expect("session values are objects");
    left.extend(
        right
            .as_object()
            .expect("session values are objects")
            .clone(),
    );
    Value::Object(left.clone())
}

fn validate_channels(channels: &[u8]) -> io::Result<()> {
    if channels.is_empty() || channels.len() > 16 || channels.iter().any(|&channel| channel > 15) {
        return Err(Error::new(
            ErrorKind::InvalidInput,
            "Channels must be unique values in 0..15",
        ));
    }
    let mut ordered = channels.to_vec();
    ordered.sort_unstable();
    if ordered.windows(2).any(|pair| pair[0] == pair[1]) {
        return Err(Error::new(
            ErrorKind::InvalidInput,
            "Channels must be unique values in 0..15",
        ));
    }
    Ok(())
}

fn validate_label(label: &str) -> io::Result<()> {
    if label.is_empty()
        || label.chars().count() > 32
        || label.len() > 96
        || label.chars().any(char::is_control)
    {
        return Err(Error::new(
            ErrorKind::InvalidInput,
            "Label must be 1..32 printable characters",
        ));
    }
    Ok(())
}

fn remaining(deadline: Instant) -> io::Result<Duration> {
    deadline
        .checked_duration_since(Instant::now())
        .filter(|d| !d.is_zero())
        .ok_or_else(|| Error::new(ErrorKind::TimedOut, "Response deadline exceeded"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader},
        net::TcpListener,
    };
    fn server(replies: Vec<&'static [u8]>) -> (Client, thread::JoinHandle<Vec<String>>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let worker = thread::spawn(move || {
            replies
                .iter()
                .map(|reply| {
                    let (mut conn, _) = listener.accept().unwrap();
                    conn.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
                    let mut command = String::new();
                    BufReader::new(conn.try_clone().unwrap())
                        .read_line(&mut command)
                        .unwrap();
                    conn.write_all(reply).unwrap();
                    command
                })
                .collect()
        });
        (
            Client::new("127.0.0.1".into(), port, Duration::from_secs(1), 2).unwrap(),
            worker,
        )
    }
    #[test]
    fn sends_existing_tcp_protocol() {
        let (client, worker) = server(vec![b"CH0=3,CH1=90\r\n", b"OK\n", b"OK\n"]);
        assert_eq!(client.status().unwrap().get(&0), Some(&3));
        client.operate(Operation::Open, 1).unwrap();
        client.operate(Operation::Close, 0).unwrap();
        assert_eq!(
            worker.join().unwrap(),
            ["STATUS\n", "OPEN 1\n", "CLOSE 0\n"]
        );
    }
    #[test]
    fn retries_idempotent_command_after_lost_reply() {
        let (client, worker) = server(vec![b"", b"OK\n"]);
        client.operate(Operation::Open, 0).unwrap();
        assert_eq!(worker.join().unwrap(), ["OPEN 0\n", "OPEN 0\n"]);
    }
    #[test]
    fn toggle_is_never_retried_after_lost_reply() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let client = Client::new(
            "127.0.0.1".into(),
            listener.local_addr().unwrap().port(),
            Duration::from_millis(100),
            5,
        )
        .unwrap();
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut line = String::new();
            BufReader::new(&mut stream).read_line(&mut line).unwrap();
            drop(stream);
            thread::sleep(Duration::from_millis(250));
            listener.set_nonblocking(true).unwrap();
            assert_eq!(listener.accept().unwrap_err().kind(), ErrorKind::WouldBlock);
            line
        });
        assert!(
            client
                .operate(Operation::Toggle, 0)
                .unwrap_err()
                .to_string()
                .contains("outcome may be unknown")
        );
        assert_eq!(worker.join().unwrap(), "TOGGLE 0\n");
    }
    #[test]
    fn rejects_incomplete_malformed_and_error_replies() {
        for reply in [b"OK".as_slice(), b"ERR\n", b"\xff\n", b"\n"] {
            let (mut client, worker) = server(vec![reply]);
            client.retries = 1;
            assert!(client.operate(Operation::Close, 0).is_err());
            worker.join().unwrap();
        }
        let (client, worker) = server(vec![b"CH0=0,CH0=90\n"]);
        assert!(client.status().is_err());
        worker.join().unwrap();
    }
    #[test]
    fn limits_response_size_and_read_time() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let client = Client::new(
            "127.0.0.1".into(),
            listener.local_addr().unwrap().port(),
            Duration::from_millis(100),
            1,
        )
        .unwrap();
        let worker = thread::spawn(move || {
            let (_stream, _) = listener.accept().unwrap();
            thread::sleep(Duration::from_millis(250));
        });
        assert!(client.status().is_err());
        worker.join().unwrap();
        // A large unframed response is rejected before allocating unbounded memory.
        let bytes: &'static [u8] = &[b'x'; 4098];
        let (client, worker) = server(vec![bytes]);
        assert_eq!(client.status().unwrap_err().kind(), ErrorKind::InvalidData);
        worker.join().unwrap();
    }
    #[test]
    fn snapshot_supports_calibration_and_legacy_without_guessing() {
        let (client, worker) = server(vec![b"CH0=70/70/10/70/0\n"]);
        assert_eq!(client.snapshot().unwrap().channels[&0].name(), "Open");
        assert_eq!(worker.join().unwrap(), ["STATE\n"]);
        let (client, worker) = server(vec![b"UNKNOWN\n", b"CH0=0\n"]);
        assert_eq!(client.snapshot().unwrap().channels[&0].name(), "Unknown");
        assert_eq!(worker.join().unwrap(), ["STATE\n", "STATUS\n"]);
    }

    #[test]
    fn session_claim_renew_operate_and_release_use_opaque_token() {
        let info = b"{\"ok\":true,\"protocol\":2,\"device_id\":\"a0ff\",\"label\":\"Bay A\",\"lease_ms\":15000,\"channels\":[{\"id\":0,\"label\":\"CH00\",\"locked\":false}]}\n";
        let (client, worker) = server(vec![
            info,
            b"{\"ok\":true}\n",
            b"{\"ok\":true}\n",
            b"{\"ok\":true}\n",
            b"{\"ok\":true}\n",
        ]);
        assert_eq!(client.info().unwrap().label, "Bay A");
        let leased = client.claim(&[0]).unwrap();
        leased.renew().unwrap();
        leased.operate_many(Operation::Open, &[0]).unwrap();
        leased.release().unwrap();
        let commands = worker.join().unwrap();
        assert!(commands[0].starts_with("SESSION {\"op\":\"info\""));
        assert!(commands[1].contains("\"op\":\"claim\""));
        assert!(commands[2].contains("\"op\":\"renew\""));
        assert!(commands[3].contains("\"action\":\"open\""));
        assert!(commands[4].contains("\"op\":\"release\""));
        assert!(!format!("{leased:?}").contains("token"));
    }

    #[test]
    fn session_errors_and_input_are_not_silently_accepted() {
        let (client, worker) = server(vec![b"{\"ok\":false,\"error\":\"busy\"}\n"]);
        assert_eq!(
            client.claim(&[0]).unwrap_err().kind(),
            ErrorKind::WouldBlock
        );
        worker.join().unwrap();
        assert!(client.claim(&[]).is_err());
        assert!(client.claim(&[1, 1]).is_err());
        assert!(client.set_label("\n").is_err());
    }
}
