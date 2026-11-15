use sha2::{Digest, Sha256};

pub fn token(value: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(value.as_bytes());
    let result = hasher.finalize();
    let hex: String = result.iter().map(|b| format!("{:02x}", b)).collect();
    hex[..24.min(hex.len())].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_length() {
        let tok = token("test");
        assert_eq!(tok.len(), 24);
        assert_eq!(tok, "9f86d081884c7d659a2feaa0");
    }
}
