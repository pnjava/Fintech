//! Vesting service implementing cliff and graded schedules.

use std::net::SocketAddr;

use axum::{routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Represents the supported vesting schedules.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum VestingSchedule {
    /// A cliff schedule vests 100% after the specified number of months.
    Cliff { cliff_months: u32 },
    /// A graded schedule vests linearly after a cliff across the remaining months.
    Graded { cliff_months: u32, total_months: u32 },
}

/// Input payload accepted by the HTTP endpoint.
#[derive(Debug, Deserialize)]
pub struct VestingRequest {
    /// Total amount subject to vesting.
    pub total_amount: f64,
    /// Months elapsed since the grant start date.
    pub months_elapsed: u32,
    /// Schedule configuration.
    pub schedule: VestingSchedule,
}

/// Response returned by the vesting endpoint.
#[derive(Debug, Serialize, PartialEq)]
pub struct VestingResponse {
    pub vested_fraction: f64,
    pub vested_amount: f64,
    pub remaining_amount: f64,
}

/// Error type surfaced by the vesting calculations.
#[derive(Debug, Error, PartialEq)]
pub enum VestingError {
    #[error("graded schedule requires total_months greater than cliff_months")]
    InvalidSchedule,
}

/// Compute the vested fraction for a schedule and elapsed months.
///
/// ```
/// use vesting::{calculate_vested_fraction, VestingSchedule};
///
/// let cliff = VestingSchedule::Cliff { cliff_months: 12 };
/// assert_eq!(calculate_vested_fraction(&cliff, 6).unwrap(), 0.0);
/// assert_eq!(calculate_vested_fraction(&cliff, 12).unwrap(), 1.0);
/// assert_eq!(calculate_vested_fraction(&cliff, 24).unwrap(), 1.0);
///
/// let graded = VestingSchedule::Graded { cliff_months: 6, total_months: 30 };
/// assert_eq!(calculate_vested_fraction(&graded, 0).unwrap(), 0.0);
/// assert_eq!(calculate_vested_fraction(&graded, 6).unwrap(), 0.0);
/// assert!((calculate_vested_fraction(&graded, 12).unwrap() - 0.25).abs() < f64::EPSILON);
/// assert_eq!(calculate_vested_fraction(&graded, 30).unwrap(), 1.0);
/// ```
pub fn calculate_vested_fraction(
    schedule: &VestingSchedule,
    months_elapsed: u32,
) -> Result<f64, VestingError> {
    match schedule {
        VestingSchedule::Cliff { cliff_months } => {
            if months_elapsed >= *cliff_months {
                Ok(1.0)
            } else {
                Ok(0.0)
            }
        }
        VestingSchedule::Graded {
            cliff_months,
            total_months,
        } => {
            if total_months <= cliff_months || *total_months == 0 {
                return Err(VestingError::InvalidSchedule);
            }
            if months_elapsed <= *cliff_months {
                return Ok(0.0);
            }
            let vested_months = months_elapsed.saturating_sub(*cliff_months);
            let denominator = total_months - cliff_months;
            let fraction = (vested_months as f64 / *denominator as f64).clamp(0.0, 1.0);
            Ok(fraction.min(1.0))
        }
    }
}

async fn calculate_handler(
    Json(request): Json<VestingRequest>,
) -> Result<Json<VestingResponse>, (axum::http::StatusCode, Json<serde_json::Value>)> {
    let fraction = calculate_vested_fraction(&request.schedule, request.months_elapsed)
        .map_err(|err| {
            (
                axum::http::StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": err.to_string() })),
            )
        })?;

    let vested_amount = request.total_amount * fraction;
    let remaining_amount = (request.total_amount - vested_amount).max(0.0);
    let response = VestingResponse {
        vested_fraction: fraction,
        vested_amount,
        remaining_amount,
    };

    Ok(Json(response))
}

/// Build the Axum router exposing the vesting endpoint.
pub fn router() -> Router {
    Router::new().route("/vesting/calculate", post(calculate_handler))
}

/// Start serving the vesting API on the provided address.
pub async fn serve(addr: SocketAddr) -> Result<(), axum::Error> {
    axum::Server::bind(&addr)
        .serve(router().into_make_service())
        .await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn graded_schedule_validation() {
        let schedule = VestingSchedule::Graded {
            cliff_months: 12,
            total_months: 12,
        };
        assert_eq!(
            calculate_vested_fraction(&schedule, 12).unwrap_err(),
            VestingError::InvalidSchedule
        );
    }

    #[tokio::test]
    async fn handler_returns_vesting_payload() {
        let request = VestingRequest {
            total_amount: 1000.0,
            months_elapsed: 9,
            schedule: VestingSchedule::Graded {
                cliff_months: 6,
                total_months: 24,
            },
        };

        let Json(response) = calculate_handler(Json(request)).await.unwrap();
        assert!((response.vested_fraction - 0.125).abs() < f64::EPSILON);
        assert!((response.vested_amount - 125.0).abs() < f64::EPSILON);
        assert!((response.remaining_amount - 875.0).abs() < f64::EPSILON);
    }
}
