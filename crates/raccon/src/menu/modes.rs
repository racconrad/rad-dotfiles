use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerMode {
    pub id: &'static str,
    pub name: &'static str,
    pub icon: &'static str,
    pub description: &'static str,
}

pub const MODES: &[PowerMode] = &[
    PowerMode {
        id: "auto",
        name: "Automatic",
        icon: "applications-engineering-symbolic",
        description: "Follows battery and charger state.",
    },
    PowerMode {
        id: "performance",
        name: "Power saver",
        icon: "battery-low-symbolic",
        description: "Minimal effects; widgets hidden and animated wallpapers paused.",
    },
    PowerMode {
        id: "balanced",
        name: "Balanced",
        icon: "power-profile-balanced-symbolic",
        description: "Full desktop with brief transitions and light blur; no continuous widget effects.",
    },
    PowerMode {
        id: "complete",
        name: "Full",
        icon: "weather-clear-symbolic",
        description: "All your widgets, animations and original effects.",
    },
    PowerMode {
        id: "working",
        name: "Working",
        icon: "format-text-code-symbolic",
        description: "Agent work: no idle lock or suspend, no animations; balanced power.",
    },
];

pub fn modes_json() -> String {
    serde_json::to_string(MODES).unwrap_or_else(|_| "[]".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_modes_count_and_keys() {
        assert_eq!(MODES.len(), 5);
        let ids: Vec<&str> = MODES.iter().map(|m| m.id).collect();
        assert_eq!(ids, vec!["auto", "performance", "balanced", "complete", "working"]);
        let json_str = modes_json();
        assert!(json_str.contains("Automatic"));
        assert!(json_str.contains("applications-engineering-symbolic"));
    }
}

