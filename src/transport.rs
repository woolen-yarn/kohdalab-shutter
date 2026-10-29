use crate::protocol::{Operation, Snapshot, Status, parse_state, parse_status};
use std::{
    io::{self, Error, ErrorKind, Read, Write},
    net::{TcpStream, ToSocketAddrs},
    thread,
    time::{Duration, Instant},
};

#[derive(Clone, Debug)]
pub struct Client {
    pub host: String,
    pub port: u16,
    pub timeout: Duration,
    pub retries: u8,
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
        let command = operation.command(channel)?;
        let response = self.send(&command, operation != Operation::Toggle)?;
        if response != "OK" {
            return Err(Error::other(format!("Pico rejected {command}: {response}")));
        }
        Ok(())
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
}
