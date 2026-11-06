//! Bounded asynchronous JSONL writer for host-side shutter provenance.
use serde_json::Value;
use std::{
    fs::{File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, SyncSender, TrySendError},
    time::Duration,
};

const QUEUE_CAPACITY: usize = 256;

enum Command {
    Entry(Value),
    Finish(Value, mpsc::Sender<Result<(), String>>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FinishStatus {
    Drained,
    TimedOut,
}

/// The GUI only calls `try_send`; file I/O and fsync happen on the writer.
pub struct OperationJournal {
    sender: SyncSender<Command>,
    errors: Receiver<String>,
    pub session_id: String,
    pub path: PathBuf,
    poisoned: bool,
}

impl OperationJournal {
    pub fn open(logs_dir: &Path) -> std::io::Result<Self> {
        std::fs::create_dir_all(logs_dir)?;
        let session_id = uuid::Uuid::new_v4().to_string();
        let path = logs_dir.join(format!("shutter-session-{session_id}.jsonl"));
        let file = OpenOptions::new()
            .create_new(true)
            .append(true)
            .open(&path)?;
        Ok(Self::from_file(file, path, session_id))
    }

    fn from_file(file: File, path: PathBuf, session_id: String) -> Self {
        let (sender, receiver) = mpsc::sync_channel(QUEUE_CAPACITY);
        let (error_sender, errors) = mpsc::channel();
        std::thread::spawn(move || writer(file, receiver, error_sender));
        Self {
            sender,
            errors,
            session_id,
            path,
            poisoned: false,
        }
    }

    /// Does not wait for disk I/O. A failure means provenance is incomplete.
    pub fn enqueue(&mut self, entry: Value) -> Result<(), String> {
        if self.poisoned {
            return Err("journal writer is unavailable; provenance is incomplete".into());
        }
        if let Some(error) = self.poll_error() {
            return Err(error);
        }
        match self.sender.try_send(Command::Entry(entry)) {
            Ok(()) => Ok(()),
            Err(TrySendError::Full(_)) => {
                Err("journal queue is full; provenance is incomplete".into())
            }
            Err(TrySendError::Disconnected(_)) => {
                self.poisoned = true;
                Err("journal writer stopped; provenance is incomplete".into())
            }
        }
    }

    pub fn poll_error(&mut self) -> Option<String> {
        match self.errors.try_recv() {
            Ok(error) => {
                self.poisoned = true;
                Some(error)
            }
            Err(_) => None,
        }
    }

    /// Request an ordered terminal record and wait only for this bounded exit
    /// handshake. Normal GUI controls never call this method.
    pub fn finish(&mut self, entry: Value, timeout: Duration) -> Result<FinishStatus, String> {
        if self.poisoned {
            return Err("journal writer is unavailable; provenance is incomplete".into());
        }
        if let Some(error) = self.poll_error() {
            return Err(error);
        }
        let (sender, receiver) = mpsc::channel();
        match self.sender.try_send(Command::Finish(entry, sender)) {
            Ok(()) => {}
            Err(TrySendError::Full(_)) => {
                return Err("journal queue is full; terminal record was not queued".into());
            }
            Err(TrySendError::Disconnected(_)) => {
                self.poisoned = true;
                return Err("journal writer stopped; terminal record was not queued".into());
            }
        }
        match receiver.recv_timeout(timeout) {
            Ok(Ok(())) => Ok(FinishStatus::Drained),
            Ok(Err(error)) => {
                self.poisoned = true;
                Err(error)
            }
            Err(mpsc::RecvTimeoutError::Timeout) => Ok(FinishStatus::TimedOut),
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                self.poisoned = true;
                Err("journal writer stopped before terminal record".into())
            }
        }
    }
}

fn writer(mut file: File, receiver: Receiver<Command>, errors: mpsc::Sender<String>) {
    while let Ok(command) = receiver.recv() {
        match command {
            Command::Entry(entry) => {
                // Serialize before touching the file, and stop permanently on the
                // first I/O failure so later records cannot disguise a gap.
                if let Err(error) = write_entry(&mut file, &entry) {
                    let _ = errors.send(format!("journal write failed: {error}"));
                    break;
                }
            }
            Command::Finish(entry, reply) => {
                let result = write_entry(&mut file, &entry)
                    .map_err(|error| format!("journal terminal write failed: {error}"));
                if let Err(error) = &result {
                    let _ = errors.send(error.clone());
                }
                let _ = reply.send(result);
                break;
            }
        }
    }
}

fn write_entry(file: &mut File, entry: &Value) -> std::io::Result<()> {
    let mut line = serde_json::to_vec(entry).map_err(std::io::Error::other)?;
    line.push(b'\n');
    file.write_all(&line)?;
    file.sync_data()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn finish_writes_terminal_record_after_prior_entries() {
        let directory = tempfile::tempdir().unwrap();
        let mut journal = OperationJournal::open(directory.path()).unwrap();
        let path = journal.path.clone();
        journal
            .enqueue(serde_json::json!({"event":"first"}))
            .unwrap();
        assert_eq!(
            journal
                .finish(
                    serde_json::json!({"event":"session_finished"}),
                    Duration::from_secs(1)
                )
                .unwrap(),
            FinishStatus::Drained
        );
        let entries: Vec<Value> = std::fs::read_to_string(path)
            .unwrap()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        assert_eq!(entries[0]["event"], "first");
        assert_eq!(entries[1]["event"], "session_finished");
    }

    #[test]
    fn disk_failure_poisoning_is_reported() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("read-only.jsonl");
        std::fs::write(&path, "").unwrap();
        let file = OpenOptions::new().read(true).open(&path).unwrap();
        let mut journal = OperationJournal::from_file(file, path, "test".into());
        journal
            .enqueue(serde_json::json!({"event":"write"}))
            .unwrap();
        let error = journal.errors.recv_timeout(Duration::from_secs(1)).unwrap();
        assert!(error.contains("journal write failed"));
        journal.poisoned = true;
        assert!(
            journal
                .enqueue(serde_json::json!({"event":"later"}))
                .is_err()
        );
    }

    #[test]
    fn blocked_writer_finish_is_bounded() {
        let (sender, receiver) = mpsc::sync_channel(QUEUE_CAPACITY);
        let (_error_sender, errors) = mpsc::channel();
        std::thread::spawn(move || {
            let command = receiver.recv();
            std::thread::sleep(Duration::from_secs(1));
            drop(command);
        });
        let mut journal = OperationJournal {
            sender,
            errors,
            session_id: "test".into(),
            path: PathBuf::from("test.jsonl"),
            poisoned: false,
        };
        let started = Instant::now();
        assert_eq!(
            journal
                .finish(
                    serde_json::json!({"event":"session_finished"}),
                    Duration::from_millis(20)
                )
                .unwrap(),
            FinishStatus::TimedOut
        );
        assert!(started.elapsed() < Duration::from_millis(250));
    }
}
