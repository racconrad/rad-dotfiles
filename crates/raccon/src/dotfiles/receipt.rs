use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::util::atomic::write_atomic_with_mode;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReceiptFileEntry {
    pub sha256: String,
    pub mode: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Receipt {
    pub schema: u32,
    pub name: String,
    pub version: String,
    pub modules: Vec<String>,
    pub choices: HashMap<String, String>,
    #[serde(default)]
    pub files: HashMap<String, ReceiptFileEntry>,
    #[serde(default)]
    pub installed_at: Option<String>,
}

impl Default for Receipt {
    fn default() -> Self {
        Self {
            schema: 1,
            name: "raccon-dots".to_string(),
            version: "0.3.0".to_string(),
            modules: Vec::new(),
            choices: HashMap::new(),
            files: HashMap::new(),
            installed_at: None,
        }
    }
}

pub fn read_receipt(home: &Path) -> Option<Receipt> {
    let path = home.join(".rdot");
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(receipt) = serde_json::from_str::<Receipt>(&content) {
            return Some(receipt);
        }
    }
    None
}

pub fn write_receipt(home: &Path, receipt: &Receipt) -> std::io::Result<()> {
    let content = serde_json::to_vec_pretty(receipt)?;
    write_atomic_with_mode(&home.join(".rdot"), &content, 0o644)
}
