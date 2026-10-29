//! Opt-in loopback JSON-lines bridge for the GUI.
//!
//! This module never controls hardware.  It authenticates and bounds socket
//! work, then hands requests to the GUI thread through [`Request`].
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    net::{Ipv4Addr, TcpListener, TcpStream},
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

const MAX_REQUEST: usize = 64 * 1024;
const MAX_PEERS: usize = 4;
const QUEUE_CAPACITY: usize = 16;
const TIMEOUT: Duration = Duration::from_secs(2);

pub struct Request {
    pub body: Value,
    pub deadline: Instant,
    pub reply: mpsc::SyncSender<Value>,
}

pub struct Server {
    pub requests: mpsc::Receiver<Request>,
    pub descriptor: PathBuf,
    stopped: Arc<AtomicBool>,
}

impl Server {
    /// Start a private, loopback-only API endpoint and publish its descriptor.
    pub fn start(directory: Option<PathBuf>) -> Result<Self, String> {
        let directory = match directory {
            Some(path) => path,
            None => {
                let profile = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
                    .ok_or_else(|| {
                        "Cannot locate the user profile for GUI API discovery".to_owned()
                    })?;
                PathBuf::from(profile).join(".kohdalab").join("control")
            }
        };
        std::fs::create_dir_all(&directory).map_err(|e| format!("GUI API directory: {e}"))?;
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0))
            .map_err(|e| format!("GUI API listener: {e}"))?;
        listener.set_nonblocking(true).map_err(|e| e.to_string())?;
        let port = listener.local_addr().map_err(|e| e.to_string())?.port();
        let token = uuid::Uuid::new_v4().to_string();
        let instance_id = uuid::Uuid::new_v4().to_string();
        let descriptor =
            directory.join(format!("shutter-{}-{instance_id}.json", std::process::id()));
        let mut temporary =
            tempfile::NamedTempFile::new_in(&directory).map_err(|e| e.to_string())?;
        serde_json::to_writer(
            &mut temporary,
            &json!({
                "protocol": 2,
                "app": "kohdalab-shutter",
                "host": "127.0.0.1",
                "port": port,
                "address": format!("127.0.0.1:{port}"),
                "token": token,
                "instance_id": instance_id,
                "pid": std::process::id(),
            }),
        )
        .map_err(|e| e.to_string())?;
        temporary.flush().map_err(|e| e.to_string())?;
        // NamedTempFile uses mode 0600 on Unix and persist publishes only a
        // fully-written descriptor.
        temporary
            .persist_noclobber(&descriptor)
            .map_err(|e| e.to_string())?;

        let (sender, requests) = mpsc::sync_channel(QUEUE_CAPACITY);
        let stopped = Arc::new(AtomicBool::new(false));
        let stop = stopped.clone();
        let peers = Arc::new(AtomicUsize::new(0));
        thread::Builder::new()
            .name("shutter-api-listener".into())
            .spawn(move || {
                while !stop.load(Ordering::Acquire) {
                    match listener.accept() {
                        Ok((stream, peer)) if peer.ip().is_loopback() => {
                            if let Some(permit) = Permit::acquire(&peers) {
                                let sender = sender.clone();
                                let token = token.clone();
                                let _ = thread::Builder::new()
                                    .name("shutter-api-peer".into())
                                    .spawn(move || {
                                        let _permit = permit;
                                        let _ = serve(stream, &token, &sender);
                                    });
                            }
                        }
                        Ok(_) => {}
                        Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                            thread::sleep(Duration::from_millis(10));
                        }
                        Err(_) => break,
                    }
                }
            })
            .map_err(|error| {
                let _ = std::fs::remove_file(&descriptor);
                error.to_string()
            })?;
        Ok(Self {
            requests,
            descriptor,
            stopped,
        })
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        self.stopped.store(true, Ordering::Release);
        let _ = std::fs::remove_file(&self.descriptor);
    }
}

struct Permit(Arc<AtomicUsize>);
impl Permit {
    fn acquire(peers: &Arc<AtomicUsize>) -> Option<Self> {
        let mut count = peers.load(Ordering::Acquire);
        while count < MAX_PEERS {
            match peers.compare_exchange_weak(count, count + 1, Ordering::AcqRel, Ordering::Acquire)
            {
                Ok(_) => return Some(Self(peers.clone())),
                Err(current) => count = current,
            }
        }
        None
    }
}
impl Drop for Permit {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::AcqRel);
    }
}

fn envelope_error(code: &str, error: impl Into<String>) -> Value {
    json!({"ok": false, "error_code": code, "error": error.into()})
}

fn serve(
    mut stream: TcpStream,
    token: &str,
    sender: &mpsc::SyncSender<Request>,
) -> Result<(), String> {
    // Accepted descriptors may inherit O_NONBLOCK on macOS; workers use a
    // single absolute deadline instead so a slow trickle cannot extend it.
    stream.set_nonblocking(false).map_err(|e| e.to_string())?;
    let deadline = Instant::now() + TIMEOUT;
    let response = match read_line(&mut stream, deadline) {
        Err(error) => envelope_error(
            if error.contains("timed out") {
                "timeout"
            } else {
                "invalid_request"
            },
            error,
        ),
        Ok(line) => match serde_json::from_slice::<Value>(&line) {
            Err(_) => envelope_error("invalid_request", "Request must be a JSON object"),
            Ok(body) if body.get("token").and_then(Value::as_str) != Some(token) => {
                envelope_error("authentication", "GUI API authentication failed")
            }
            Ok(body) if !body.is_object() => {
                envelope_error("invalid_request", "Request must be a JSON object")
            }
            Ok(body) => {
                let (reply, receive) = mpsc::sync_channel(1);
                match sender.try_send(Request {
                    body,
                    deadline,
                    reply,
                }) {
                    Err(mpsc::TrySendError::Full(_)) => {
                        envelope_error("busy", "GUI request queue is full")
                    }
                    Err(mpsc::TrySendError::Disconnected(_)) => {
                        envelope_error("unavailable", "GUI API is stopping")
                    }
                    Ok(()) => match deadline.checked_duration_since(Instant::now()) {
                        Some(remaining) => receive
                            .recv_timeout(remaining)
                            .unwrap_or_else(|_| envelope_error("timeout", "GUI request timed out")),
                        None => envelope_error("timeout", "GUI request timed out"),
                    },
                }
            }
        },
    };
    stream
        .set_write_timeout(Some(TIMEOUT))
        .map_err(|e| e.to_string())?;
    serde_json::to_writer(&mut stream, &response).map_err(|e| e.to_string())?;
    stream.write_all(b"\n").map_err(|e| e.to_string())
}

fn read_line(stream: &mut TcpStream, deadline: Instant) -> Result<Vec<u8>, String> {
    let mut data = Vec::new();
    loop {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .ok_or_else(|| "Request read timed out".to_owned())?;
        stream
            .set_read_timeout(Some(remaining))
            .map_err(|e| e.to_string())?;
        let mut chunk = [0_u8; 4096];
        let count = stream.read(&mut chunk).map_err(|error| {
            if matches!(
                error.kind(),
                std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock
            ) {
                "Request read timed out".to_owned()
            } else {
                error.to_string()
            }
        })?;
        if count == 0 {
            return Err("Incomplete JSON request".into());
        }
        let slice = &chunk[..count];
        if let Some(index) = slice.iter().position(|byte| *byte == b'\n') {
            data.extend_from_slice(&slice[..index]);
            if data.len() > MAX_REQUEST {
                return Err("Request exceeds 64 KiB".into());
            }
            return Ok(data);
        }
        data.extend_from_slice(slice);
        if data.len() > MAX_REQUEST {
            return Err("Request exceeds 64 KiB".into());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};

    fn exchange(port: u16, body: Value) -> Value {
        let mut stream = TcpStream::connect((Ipv4Addr::LOCALHOST, port)).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(3)))
            .unwrap();
        writeln!(stream, "{body}").unwrap();
        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line).unwrap();
        serde_json::from_str(&line).unwrap()
    }
    #[test]
    fn authenticated_request_bypasses_idle_peer_and_drop_removes_descriptor() {
        let directory = tempfile::tempdir().unwrap();
        let server = Server::start(Some(directory.path().into())).unwrap();
        let descriptor = server.descriptor.clone();
        let declaration: Value =
            serde_json::from_slice(&std::fs::read(&descriptor).unwrap()).unwrap();
        let port = declaration["port"].as_u64().unwrap() as u16;
        let _idle = TcpStream::connect((Ipv4Addr::LOCALHOST, port)).unwrap();
        let response = exchange(port, json!({"token":"wrong","method":"status"}));
        assert_eq!(response["error_code"], "authentication");
        assert!(server.requests.try_recv().is_err());
        let token = declaration["token"].clone();
        let worker =
            thread::spawn(move || exchange(port, json!({"token":token,"method":"status"})));
        let request = server
            .requests
            .recv_timeout(Duration::from_secs(1))
            .unwrap();
        assert_eq!(request.body["method"], "status");
        request
            .reply
            .send(json!({"ok":true,"result":{"demo":true}}))
            .unwrap();
        assert_eq!(worker.join().unwrap()["ok"], true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                std::fs::metadata(&descriptor).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }
        drop(server);
        assert!(!descriptor.exists());
    }
    #[test]
    fn oversized_request_never_reaches_gui() {
        let directory = tempfile::tempdir().unwrap();
        let server = Server::start(Some(directory.path().into())).unwrap();
        let declaration: Value =
            serde_json::from_slice(&std::fs::read(&server.descriptor).unwrap()).unwrap();
        let port = declaration["port"].as_u64().unwrap() as u16;
        let mut stream = TcpStream::connect((Ipv4Addr::LOCALHOST, port)).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(3)))
            .unwrap();
        stream.write_all(&vec![b'x'; MAX_REQUEST + 1]).unwrap();
        let mut line = String::new();
        BufReader::new(stream).read_line(&mut line).unwrap();
        let response: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(response["error_code"], "invalid_request");
        assert!(server.requests.try_recv().is_err());
    }
}
