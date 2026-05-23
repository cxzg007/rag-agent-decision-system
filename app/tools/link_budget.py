import math
import re

from pydantic import BaseModel, Field


class LinkBudgetInput(BaseModel):
    request: str
    frequency_mhz: float = Field(default=2400.0, gt=0)
    distance_km: float = Field(default=1.0, gt=0)
    tx_power_dbm: float = 20.0
    tx_gain_dbi: float = 2.0
    rx_gain_dbi: float = 2.0
    receiver_sensitivity_dbm: float = -90.0
    system_loss_db: float = 3.0


class LinkBudgetOutput(BaseModel):
    frequency_mhz: float
    distance_km: float
    free_space_path_loss_db: float
    received_power_dbm: float
    link_margin_db: float
    quality: str
    assumptions: list[str]


async def link_budget_estimator(payload: LinkBudgetInput) -> LinkBudgetOutput:
    frequency = _extract_number(payload.request, ["mhz", "MHz"], payload.frequency_mhz)
    distance = _extract_number(payload.request, ["km", "公里"], payload.distance_km)
    tx_power = _extract_labeled_number(
        payload.request,
        ["发射功率", "tx power", "transmit power"],
        ["dbm", "dBm"],
        payload.tx_power_dbm,
        fallback_to_unit=True,
    )
    receiver_sensitivity = _extract_labeled_number(
        payload.request,
        ["接收灵敏度", "灵敏度", "receiver sensitivity"],
        ["dbm", "dBm"],
        payload.receiver_sensitivity_dbm,
        fallback_to_unit=False,
    )

    fspl = 32.44 + 20 * math.log10(distance) + 20 * math.log10(frequency)
    received = tx_power + payload.tx_gain_dbi + payload.rx_gain_dbi - fspl - payload.system_loss_db
    margin = received - receiver_sensitivity
    if margin >= 20:
        quality = "good"
    elif margin >= 10:
        quality = "usable"
    else:
        quality = "risky"
    return LinkBudgetOutput(
        frequency_mhz=round(frequency, 2),
        distance_km=round(distance, 2),
        free_space_path_loss_db=round(fspl, 2),
        received_power_dbm=round(received, 2),
        link_margin_db=round(margin, 2),
        quality=quality,
        assumptions=[
            "free-space path loss model",
            f"tx_gain={payload.tx_gain_dbi} dBi",
            f"rx_gain={payload.rx_gain_dbi} dBi",
            f"receiver_sensitivity={receiver_sensitivity} dBm",
            f"system_loss={payload.system_loss_db} dB",
        ],
    )


def _extract_number(text: str, units: list[str], default: float) -> float:
    for unit in units:
        match = re.search(rf"(\d+(?:\.\d+)?)\s*{re.escape(unit)}", text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return default


def _extract_labeled_number(
    text: str,
    labels: list[str],
    units: list[str],
    default: float,
    *,
    fallback_to_unit: bool,
) -> float:
    for label in labels:
        for unit in units:
            pattern = rf"{re.escape(label)}\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*{re.escape(unit)}"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
    if not fallback_to_unit:
        return default
    return _extract_number(text, units, default)
