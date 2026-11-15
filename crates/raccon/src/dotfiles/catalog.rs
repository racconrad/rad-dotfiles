use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChoiceInfo {
    pub default: String,
    pub options: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleInfo {
    pub label: Option<String>,
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub packages: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Catalog {
    pub defaults: Vec<String>,
    pub choices: HashMap<String, ChoiceInfo>,
    pub modules: HashMap<String, ModuleInfo>,
}

impl Catalog {
    pub fn load_from_root(root: &Path) -> Result<Self, String> {
        let path = root.join("modules.json");
        let content = fs::read_to_string(&path)
            .map_err(|e| format!("Could not read modules.json: {}", e))?;
        serde_json::from_str(&content)
            .map_err(|e| format!("Invalid modules.json format: {}", e))
    }

    pub fn default_choices(&self) -> HashMap<String, String> {
        let mut map = HashMap::new();
        for (k, v) in &self.choices {
            map.insert(k.clone(), v.default.clone());
        }
        map
    }

    pub fn resolve_modules(
        &self,
        requested: &[String],
        choices: &HashMap<String, String>,
    ) -> Result<Vec<String>, String> {
        let mut result = Vec::new();
        let mut visiting = HashSet::new();

        fn visit(
            name: &str,
            catalog: &Catalog,
            choices: &HashMap<String, String>,
            result: &mut Vec<String>,
            visiting: &mut HashSet<String>,
        ) -> Result<(), String> {
            let actual_name = choices.get(name).map(|s| s.as_str()).unwrap_or(name);
            let module_info = catalog
                .modules
                .get(actual_name)
                .ok_or_else(|| format!("Unknown module: {}", actual_name))?;

            if result.iter().any(|m| m == actual_name) {
                return Ok(());
            }

            if visiting.contains(actual_name) {
                return Err(format!("Circular dependency in module: {}", actual_name));
            }

            visiting.insert(actual_name.to_string());

            for dep in &module_info.requires {
                visit(dep, catalog, choices, result, visiting)?;
            }

            visiting.remove(actual_name);
            result.push(actual_name.to_string());
            Ok(())
        }

        for name in requested {
            visit(name, self, choices, &mut result, &mut visiting)?;
        }

        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_modules_simple() {
        let mut modules = HashMap::new();
        modules.insert(
            "base".to_string(),
            ModuleInfo {
                label: None,
                requires: vec![],
                packages: vec![],
            },
        );
        modules.insert(
            "kitty".to_string(),
            ModuleInfo {
                label: None,
                requires: vec!["base".to_string()],
                packages: vec![],
            },
        );
        modules.insert(
            "wayfire".to_string(),
            ModuleInfo {
                label: None,
                requires: vec!["terminal".to_string()],
                packages: vec![],
            },
        );

        let mut choices = HashMap::new();
        choices.insert(
            "terminal".to_string(),
            ChoiceInfo {
                default: "kitty".to_string(),
                options: vec!["kitty".to_string()],
            },
        );

        let catalog = Catalog {
            defaults: vec!["wayfire".to_string()],
            choices,
            modules,
        };

        let user_choices = catalog.default_choices();
        let resolved = catalog
            .resolve_modules(&["wayfire".to_string()], &user_choices)
            .unwrap();

        assert_eq!(resolved, vec!["base", "kitty", "wayfire"]);
    }
}
