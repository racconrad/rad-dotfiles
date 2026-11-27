pub mod catalogue;
pub mod entry;
pub mod launcher;

pub use catalogue::{catalogue_value, filter_search, resolve_search_action, SEARCH_TARGETS};
pub use entry::{app_dirs, cached_applications, normalize, scan_applications, AppEntry};
pub use launcher::{launch_app, watch_catalogue};
