//! Vesting domain logic crate placeholder.

/// Returns a welcome message for the vesting crate.
pub fn welcome() -> &'static str {
    "Vesting module coming soon"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn welcome_message() {
        assert_eq!(welcome(), "Vesting module coming soon");
    }
}
