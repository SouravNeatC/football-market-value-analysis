import pandas as pd
import numpy as np
from pathlib import Path

# -------- Settings --------
MIN_90S = 20# eligibility floor
IN_PATH  = Path("all_squads.csv")
OUT_PATH = Path("all_squads_ranked.csv")

# -------- Load & numeric coercion --------
df = pd.read_csv(IN_PATH)

for col in df.columns:
    if df[col].dtype == object:
        # try to coerce numeric-looking strings (strip % first)
        coerced = pd.to_numeric(df[col].astype(str).str.replace('%', '', regex=False), errors='coerce')
        # prefer numeric where available, keep original otherwise (avoids FutureWarning)
        if coerced.notna().any():
            df[col] = coerced.combine_first(df[col])

# ensure 90s is numeric
df["90s Played"] = pd.to_numeric(df["90s Played"], errors="coerce")

# -------- Role classification from Position text --------
def map_role(pos: str) -> str | None:
    if not isinstance(pos, str):
        return None
    p = pos.lower()
    if "goalkeeper" in p:
        return "GK"
    if any(k in p for k in ["centre-back", "right-back", "left-back"]):
        return "DF"
    if any(k in p for k in ["attacking midfield", "defensive midfield", "central midfield"]):
        return "MF"
    if any(k in p for k in ["left winger", "centre-forward", 'right winger']):
        return "FWD"
    return None

df["role"] = df["Position"].apply(map_role)

# -------- Per-90 fallbacks for progressions --------
def safe_div(num, den):
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return np.where(den > 0, num / den, np.nan)

def as_series(arr):
    return pd.Series(arr, index=df.index, dtype="float64")

df["prog_carries_90_any"] = np.nan
df["prog_passes_rec_90_any"] = np.nan

# prefer role-specific per 90 when present
df["prog_carries_90_any"] = df["prog_carries_90_any"].combine_first(pd.to_numeric(df.get("mf_progressive_carries_90"), errors="coerce"))
df["prog_passes_rec_90_any"] = df["prog_passes_rec_90_any"].combine_first(pd.to_numeric(df.get("mf_progressive_passes_rec_90"), errors="coerce"))
df["prog_passes_rec_90_any"] = df["prog_passes_rec_90_any"].combine_first(pd.to_numeric(df.get("df_progressive_passes_rec_90"), errors="coerce"))

# fallback from season totals ÷ 90s (wrap arrays as Series before combine_first/fill)
df["prog_carries_90_any"] = df["prog_carries_90_any"].combine_first(
    as_series(safe_div(df.get("Progressive Carries"), df["90s Played"]))
)
df["prog_passes_rec_90_any"] = df["prog_passes_rec_90_any"].combine_first(
    as_series(safe_div(df.get("Progressive Passes Received"), df["90s Played"]))
)

# progressive passes per 90 (MF-specific available; otherwise from totals)
df["prog_passes_90_any"] = pd.to_numeric(df.get("mf_progressive_passes_90"), errors="coerce")
df["prog_passes_90_any"] = df["prog_passes_90_any"].combine_first(
    as_series(safe_div(df.get("Progressive Passes"), df["90s Played"]))
)

# Discipline per 90
df["yc_90"] = as_series(safe_div(df.get("Yellow Cards"), df["90s Played"]))
df["rc_90"] = as_series(safe_div(df.get("Red Cards"), df["90s Played"]))

# -------- Z-score helper (within role) --------
def z_by_role(s, role_series):
    s = pd.to_numeric(s, errors="coerce")
    out = pd.Series(index=s.index, dtype="float64")
    for r in ["FWD", "MF", "DF", "GK"]:
        mask = (role_series == r) & (df["90s Played"] >= MIN_90S)
        mu = s[mask].mean()
        sd = s[mask].std(ddof=0)
        out.loc[mask] = (s.loc[mask] - mu) / sd if sd and not np.isclose(sd, 0) else 0.0
    return out.fillna(0.0)

# -------- Build each role's score --------
# Forwards
fwd_score = (
    0.40 * z_by_role(df["Goals scored per 90 minutes"], df["role"]) +
    0.15 * z_by_role(df["npxg per 90 minutes"], df["role"]) +
    0.10 * z_by_role(df["xg per 90 minutes"], df["role"]) +
    0.10 * z_by_role(df["Assists per 90 minutes"], df["role"]) +
    0.10 * z_by_role(df["xag per 90 minutes"], df["role"]) +
    0.05 * z_by_role(df["prog_carries_90_any"], df["role"]) +
    0.10 * z_by_role(df["prog_passes_rec_90_any"], df["role"]) -
    0.05 * z_by_role(0.7*df["yc_90"] + 1.3*df["rc_90"], df["role"])
)

# Midfielders
mf_score = (
    0.25 * z_by_role(df["mf_shot_creating_actions_90"], df["role"]) +
    0.20 * z_by_role(df["prog_passes_90_any"], df["role"]) +
    0.15 * z_by_role(df["prog_carries_90_any"], df["role"]) +
    0.05 * z_by_role(df["prog_passes_rec_90_any"], df["role"]) +
    0.10 * z_by_role(df["Assists per 90 minutes"], df["role"]) +
    0.10 * z_by_role(df["mf_passes_attempted_90"], df["role"]) +
    0.10 * z_by_role(df["mf_pass_completion_pct"], df["role"]) +
    0.05 * z_by_role(df["mf_tackles_90"], df["role"]) +
    0.05 * z_by_role(df["mf_interceptions_90"], df["role"])
)

# Defenders
df_score = (
    0.20 * z_by_role(df["df_interceptions_90"], df["role"]) +
    0.20 * z_by_role(df["df_tackles_90"], df["role"]) +
    0.15 * z_by_role(df["df_blocks_90"], df["role"]) +
    0.15 * z_by_role(df["df_clearances_90"], df["role"]) +
    0.15 * z_by_role(df["df_aerials_won_90"], df["role"]) +
    0.10 * z_by_role(df["df_progressive_passes_rec_90"], df["role"]) -
    0.05 * z_by_role(0.7*df["yc_90"] + 1.3*df["rc_90"], df["role"])
)

# Goalkeepers
gk_score = (
    0.40 * z_by_role(df["gk_save_percentage"], df["role"]) +
    0.20 * z_by_role(df["gk_clean_sheet_percentage"], df["role"]) +
    0.10 * z_by_role(df["gk_crosses_stopped_pct"], df["role"]) +
    0.10 * z_by_role(df["gk_def_actions_outside_pen_area"], df["role"]) +
    0.05 * z_by_role(df["gk_avg_distance_of_def_actions"], df["role"]) +
    0.10 * z_by_role(df["gk_save_pct_penalty_kicks"], df["role"]) +
    0.05 * z_by_role(df["gk_psxg_per_sot"], df["role"])
)

# assign per-role score and ranks (1 = best)
df["fwd_score"] = np.where(df["role"]=="FWD", fwd_score, np.nan)
df["mf_score"]  = np.where(df["role"]=="MF",  mf_score,  np.nan)
df["df_score"]  = np.where(df["role"]=="DF",  df_score,  np.nan)
df["gk_score"]  = np.where(df["role"]=="GK",  gk_score,  np.nan)

def rank_within_role(score_col):
    return df.groupby("role")[score_col].rank(method="dense", ascending=False)

df["fwd_rank"] = np.where(df["role"]=="FWD", rank_within_role("fwd_score"), np.nan)
df["mf_rank"]  = np.where(df["role"]=="MF",  rank_within_role("mf_score"),  np.nan)
df["df_rank"]  = np.where(df["role"]=="DF",  rank_within_role("df_score"),  np.nan)
df["gk_rank"]  = np.where(df["role"]=="GK",  rank_within_role("gk_score"),  np.nan)

df.loc[(df["90s Played"].isna()) | (df["90s Played"] < MIN_90S),
       ["fwd_rank","mf_rank","df_rank","gk_rank"]] = np.nan

# ------- Market value parsing + "underrated" scores and ranks -------

def _parse_market_value_to_eur(x):
    """
    Accepts values like '€50m', '€750k', '50,000,000', 50000000, or NaN.
    Returns numeric euros (float) or NaN.
    """
    if pd.isna(x):
        return np.nan
    s = str(x).strip().lower()
    for ch in ["€", "$", "£", ",", " "]:
        s = s.replace(ch, "")

    mult = 1.0
    if s.endswith("m"):
        mult = 1_000_000.0
        s = s[:-1]
    elif s.endswith("k"):
        mult = 1_000.0
        s = s[:-1]

    try:
        base = float("".join(ch for ch in s if (ch.isdigit() or ch == ".")))
        return base * mult
    except ValueError:
        return np.nan

# Try common market value column names
_market_value_candidates = [
    "market_value_eur", "Market value", "Market Value", "market value",
    "TM_Market_Value", "tm_market_value", "value", "Value", "mv"
]
mv_col = next((c for c in _market_value_candidates if c in df.columns), None)
if mv_col is None:
    raise KeyError(
        "No market value column found. Add one of: "
        + ", ".join(_market_value_candidates)
    )

# Normalize to numeric euros
if pd.api.types.is_numeric_dtype(df[mv_col]):
    df["_market_value_eur"] = pd.to_numeric(df[mv_col], errors="coerce")
else:
    df["_market_value_eur"] = df[mv_col].apply(_parse_market_value_to_eur)

# Require positive market value; otherwise NaN to avoid div-by-zero
df.loc[~(df["_market_value_eur"] > 0), "_market_value_eur"] = np.nan

# Underrated = role score / market value (higher = more value per €)
df["fwd_underrated"] = np.where(df["role"] == "FWD", df["fwd_score"] / df["_market_value_eur"], np.nan)
df["mf_underrated"]  = np.where(df["role"] == "MF",  df["mf_score"]  / df["_market_value_eur"], np.nan)
df["df_underrated"]  = np.where(df["role"] == "DF",  df["df_score"]  / df["_market_value_eur"], np.nan)
df["gk_underrated"]  = np.where(df["role"] == "GK",  df["gk_score"]  / df["_market_value_eur"], np.nan)

# Rank within role (1 = most underrated)
def _rank_role(col):
    return df.groupby("role")[col].rank(method="dense", ascending=False)

df["fwd_underrated_rank"] = np.where(df["role"]=="FWD", _rank_role("fwd_underrated"), np.nan)
df["mf_underrated_rank"]  = np.where(df["role"]=="MF",  _rank_role("mf_underrated"),  np.nan)
df["df_underrated_rank"]  = np.where(df["role"]=="DF",  _rank_role("df_underrated"),  np.nan)
df["gk_underrated_rank"]  = np.where(df["role"]=="GK",  _rank_role("gk_underrated"),  np.nan)

# Apply the same eligibility mask used for role ranks, plus require market value present
elig_mask = (~df["90s Played"].isna()) & (df["90s Played"] >= MIN_90S) & (~df["_market_value_eur"].isna())
underr_cols = ["fwd_underrated_rank","mf_underrated_rank","df_underrated_rank","gk_underrated_rank"]
df.loc[~elig_mask, underr_cols] = np.nan



# Save
df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print("Saved:", OUT_PATH)

top_players = pd.concat([
    df.loc[df["fwd_rank"] == 1, :],
    df.loc[df["mf_rank"] == 1, :],
    df.loc[df["df_rank"] == 1, :],
    df.loc[df["gk_rank"] == 1, :]
])

#print("Top players by role:")
for role in ["FWD", "MF", "DF", "GK"]:
   print(f"\nTop {role}:\n", top_players[top_players["role"] == role][["player", "Club", "fwd_rank", "mf_rank", "df_rank", "gk_rank"]])




for role, col in [("FWD","fwd_underrated_rank"), ("MF","mf_underrated_rank"),
                  ("DF","df_underrated_rank"), ("GK","gk_underrated_rank")]:
    subset = df[(df["role"]==role) & (~df[col].isna())].nsmallest(10, col)
    cols_to_show = [c for c in ["player","Player","Name","Squad","Club", col] if c in subset.columns]
    print(f"\nMost underrated Top 10 — {role}:\n", subset[cols_to_show])
