//! Shared GUI ownership and bounded, idempotent action receipts.
use serde_json::{Value, json};
use std::{
    collections::{HashMap, HashSet, VecDeque},
    time::{Duration, Instant},
};

pub const LEASE_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_RECEIPTS: usize = 64;
const MAX_IDS: usize = 4096;

#[derive(Debug, Clone)]
pub struct ApiError {
    pub code: &'static str,
    pub message: String,
}
impl ApiError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}
pub fn response(result: Result<Value, ApiError>) -> Value {
    match result {
        Ok(value) => json!({"ok":true,"result":value,"data":value}),
        Err(error) => json!({"ok":false,"error_code":error.code,"error":error.message}),
    }
}
struct Owner {
    client: String,
    lease: String,
    label: String,
    seen: Instant,
}
#[derive(Default)]
pub struct Control {
    owner: Option<Owner>,
    revoked: HashSet<String>,
    jobs: VecDeque<Value>,
    fingerprints: HashMap<String, String>,
    used: HashSet<String>,
}
impl Control {
    pub fn owned(&self) -> bool {
        self.owner.is_some()
    }
    pub fn label(&self) -> Option<&str> {
        self.owner.as_ref().map(|owner| owner.label.as_str())
    }
    pub fn expire(&mut self) -> bool {
        if self
            .owner
            .as_ref()
            .is_some_and(|owner| owner.seen.elapsed() > LEASE_TIMEOUT)
        {
            self.revoke();
            true
        } else {
            false
        }
    }
    pub fn revoke(&mut self) {
        if let Some(owner) = self.owner.take() {
            self.revoked.insert(owner.client);
        }
    }
    pub fn acquire(&mut self, body: &Value, busy: bool) -> Result<Value, ApiError> {
        let client = string(body, "client")?;
        if uuid::Uuid::parse_str(client).is_err() {
            return Err(ApiError::new("invalid_request", "client must be a UUID"));
        }
        if self.revoked.contains(client) {
            return Err(ApiError::new(
                "ownership_lost",
                "Client revoked or expired; create a new client",
            ));
        }
        if let Some(owner) = &mut self.owner {
            if owner.client != client {
                return Err(ApiError::new("busy", "Another client owns GUI control"));
            }
            owner.seen = Instant::now();
            return Ok(json!({"lease":owner.lease,"expires_in":10,"policy":"hold_last_state"}));
        }
        if busy {
            return Err(ApiError::new("busy", "Wait for the current GUI operation"));
        }
        if self.revoked.len() >= MAX_IDS {
            return Err(ApiError::new(
                "capacity",
                "Restart GUI before admitting more clients",
            ));
        }
        let lease = uuid::Uuid::new_v4().to_string();
        self.owner = Some(Owner {
            client: client.into(),
            lease: lease.clone(),
            label: body["label"]
                .as_str()
                .unwrap_or("Python")
                .chars()
                .take(64)
                .collect(),
            seen: Instant::now(),
        });
        Ok(json!({"lease":lease,"expires_in":10,"policy":"hold_last_state"}))
    }
    pub fn authorize(&mut self, body: &Value) -> Result<(), ApiError> {
        self.expire();
        let Some(owner) = &mut self.owner else {
            return Err(ApiError::new("ownership_lost", "Acquire GUI control first"));
        };
        if body["client"].as_str() != Some(owner.client.as_str())
            || body["lease"].as_str() != Some(owner.lease.as_str())
        {
            return Err(ApiError::new(
                "ownership_lost",
                "Control lease is missing, expired, or revoked",
            ));
        }
        owner.seen = Instant::now();
        Ok(())
    }
    pub fn release(&mut self, body: &Value) -> Result<Value, ApiError> {
        self.authorize(body)?;
        self.owner = None;
        Ok(json!({"released":true,"policy":"hold_last_state"}))
    }
    pub fn cached(&self, body: &Value, method: &str) -> Result<Option<Value>, ApiError> {
        let id = string(body, "request_id")?;
        if uuid::Uuid::parse_str(id).is_err() {
            return Err(ApiError::new(
                "invalid_request",
                "request_id must be a UUID",
            ));
        }
        if !self.used.contains(id) {
            return Ok(None);
        }
        let Some(previous) = self.fingerprints.get(id) else {
            return Err(ApiError::new(
                "expired_job",
                "Receipt expired; this request ID cannot be reused",
            ));
        };
        if previous != &fingerprint(body, method) {
            return Err(ApiError::new(
                "request_id_conflict",
                "request_id was already used with different parameters",
            ));
        }
        self.result(id).map(Some)
    }
    pub fn begin(&mut self, body: &Value, method: &str) -> Result<Value, ApiError> {
        if let Some(receipt) = self.cached(body, method)? {
            return Ok(receipt);
        }
        if self.used.len() >= MAX_IDS {
            return Err(ApiError::new(
                "capacity",
                "Action ID capacity reached; restart GUI",
            ));
        }
        let id = string(body, "request_id")?.to_owned();
        if self.jobs.len() >= MAX_RECEIPTS
            && let Some(job) = self.jobs.pop_front()
            && let Some(id) = job["id"].as_str()
        {
            self.fingerprints.remove(id);
        }
        let receipt = json!({"id":id,"kind":method,"status":"running","result":null,"error":null,"error_code":null});
        self.used.insert(id.clone());
        self.fingerprints.insert(id, fingerprint(body, method));
        self.jobs.push_back(receipt.clone());
        Ok(receipt)
    }
    pub fn complete(&mut self, id: &str, result: Result<Value, ApiError>) {
        if let Some(job) = self.jobs.iter_mut().find(|job| job["id"] == id) {
            match result {
                Ok(value) => {
                    job["status"] = json!("completed");
                    job["result"] = value;
                }
                Err(error) => {
                    job["status"] = json!("error");
                    job["error_code"] = json!(error.code);
                    job["error"] = json!(error.message);
                }
            }
        }
    }
    pub fn result(&self, id: &str) -> Result<Value, ApiError> {
        self.jobs
            .iter()
            .find(|job| job["id"] == id)
            .cloned()
            .ok_or_else(|| ApiError::new("unknown_job", "Unknown or expired job"))
    }
}
pub fn string<'a>(body: &'a Value, key: &str) -> Result<&'a str, ApiError> {
    body[key]
        .as_str()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            ApiError::new(
                "invalid_request",
                format!("{key} must be a non-empty string"),
            )
        })
}
fn fingerprint(body: &Value, method: &str) -> String {
    let mut copy = body.clone();
    if let Some(map) = copy.as_object_mut() {
        for key in ["token", "lease", "action", "method", "request_id"] {
            map.remove(key);
        }
        map.insert("method".into(), json!(method));
    }
    copy.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    fn body() -> Value {
        json!({"client":uuid::Uuid::new_v4().to_string(),"request_id":uuid::Uuid::new_v4().to_string(),"channel":0})
    }
    #[test]
    fn exclusive_control_heartbeat_release_and_revoke() {
        let mut control = Control::default();
        let mut a = body();
        let b = body();
        a["lease"] = control.acquire(&a, false).unwrap()["lease"].clone();
        assert!(control.acquire(&b, false).is_err());
        assert!(control.authorize(&b).is_err());
        control.authorize(&a).unwrap();
        control.release(&a).unwrap();
        a["lease"] = control.acquire(&a, false).unwrap()["lease"].clone();
        control.owner.as_mut().unwrap().seen = Instant::now() - Duration::from_secs(11);
        assert!(control.expire());
        assert!(!control.owned());
        assert!(control.acquire(&a, false).is_err());
        assert!(control.acquire(&b, true).is_err());
        assert!(control.acquire(&b, false).is_ok());
    }
    #[test]
    fn request_ids_do_not_repeat_toggle_and_conflicts_are_rejected() {
        let mut control = Control::default();
        let mut request = body();
        let receipt = control.begin(&request, "toggle").unwrap();
        assert_eq!(
            control.cached(&request, "toggle").unwrap().unwrap(),
            receipt
        );
        request["channel"] = json!(1);
        assert_eq!(
            control.cached(&request, "toggle").unwrap_err().code,
            "request_id_conflict"
        );
        control.complete(
            receipt["id"].as_str().unwrap(),
            Ok(json!({"accepted":true})),
        );
        assert_eq!(
            control.result(receipt["id"].as_str().unwrap()).unwrap()["status"],
            "completed"
        );
    }
    #[test]
    fn evicted_receipts_cannot_execute_again() {
        let mut control = Control::default();
        let request = body();
        control.begin(&request, "toggle").unwrap();
        for _ in 0..MAX_RECEIPTS {
            control.begin(&body(), "open").unwrap();
        }
        assert_eq!(
            control.cached(&request, "toggle").unwrap_err().code,
            "expired_job"
        );
    }
}
