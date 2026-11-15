use std::collections::HashMap;
use std::path::Path;

use crate::dotfiles::catalog::Catalog;
use crate::dotfiles::installer::{apply_plan, build_plan};
use crate::dotfiles::receipt::read_receipt;

pub fn update_modules(
    root: &Path,
    home: &Path,
    selected_modules: Option<Vec<String>>,
    dry_run: bool,
) -> Result<(), String> {
    let receipt = read_receipt(home)
        .ok_or_else(|| "No installation receipt found. Run 'raccon install' first.".to_string())?;

    let _catalog = Catalog::load_from_root(root)?;

    let target_modules = match selected_modules {
        Some(mods) => {
            let installed: std::collections::HashSet<_> = receipt.modules.iter().collect();
            for m in &mods {
                if !installed.contains(m) {
                    return Err(format!("Module '{}' is not recorded in the receipt.", m));
                }
            }
            mods
        }
        None => receipt.modules.clone(),
    };

    let choices: HashMap<String, String> = receipt.choices.clone();
    let plan = build_plan(root, home, &target_modules, &choices)?;

    println!("Updating {} module(s): {:?}", target_modules.len(), target_modules);
    apply_plan(home, &plan, &receipt.modules, &choices, dry_run)?;

    Ok(())
}
