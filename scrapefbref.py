# pip install selenium beautifulsoup4 pandas lxml

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup, Comment
import pandas as pd
import time, re, os
from collections import defaultdict

CLUBS = {
    "Barcelona": "https://fbref.com/en/squads/206d90db/2024-2025/all_comps/Barcelona-Stats-All-Competitions",
    "Real Madrid": "https://fbref.com/en/squads/53a2f082/2024-2025/all_comps/Real-Madrid-Stats-All-Competitions",
    "Liverpool": "https://fbref.com/en/squads/822bd0ba/2024-2025/all_comps/Liverpool-Stats-All-Competitions",
    "Arsenal": "https://fbref.com/en/squads/18bb7c10/2024-2025/all_comps/Arsenal-Stats-All-Competitions",
    "PSG": "https://fbref.com/en/squads/e2d8892c/2024-2025/all_comps/Paris-Saint-Germain-Stats-All-Competitions",
}
OUTPUT_DIR = "outputs"
CHROMEDRIVER_PATH = r"C:\Users\Lenovo\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"


opts = Options()

opts.add_argument("--log-level=3")
opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
opts.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
service = Service(executable_path=CHROMEDRIVER_PATH)


def find_table_from_page_source(html, table_id):
    """Return <table> either directly or from FBref's comment wrapper."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=table_id)
    if table:
        return table
    wrapper = soup.find("div", id=f"all_{table_id}")
    if not wrapper:
        return None
    for child in wrapper.children:
        if isinstance(child, Comment) and "table" in child:
            inner = BeautifulSoup(child, "lxml")
            table = inner.find("table", id=table_id)
            if table:
                return table
    return None

def classify_role(pos_text: str) -> str | None:
    """Map position text to 'midfielder' | 'defender' | 'goalkeeper' | None (attackers)."""
    if not pos_text:
        return None
    t = pos_text.strip().lower()
    if any(k in t for k in ["gk", "goalkeeper"]):
        return "goalkeeper"
    if any(k in t for k in ["df", "defender", "back", "centre-back", "center-back", "left-back", "right-back", "cb", "lb", "rb"]):
        return "defender"
    if any(k in t for k in ["mf", "midfield", "attacking midfield", "central midfield", "defensive midfield", "cm", "am", "dm"]):
        return "midfielder"
    return None

def _norm_label(s: str) -> str:
    s = s.lower().replace("–", "-").replace("’", "'").replace("per 90", "").replace("%", " percent")
    return re.sub(r"[^a-z0-9]+", "", s)


DEFENDER_LABELS = {
    "df_progressive_passes_rec_90": {"progressivepassesrec", "progressivepassesreceived"},
    "df_tackles_90": {"tackles"},
    "df_interceptions_90": {"interceptions"},
    "df_blocks_90": {"blocks"},
    "df_clearances_90": {"clearances"},
    "df_aerials_won_90": {"aerialswon"},
}
MIDFIELDER_LABELS = {
    "mf_shot_creating_actions_90": {"shotcreatingactions"},
    "mf_passes_attempted_90": {"passesattempted"},
    "mf_pass_completion_pct": {"passcompletionpercent", "passcompletion"},
    "mf_progressive_passes_90": {"progressivepasses"},
    "mf_progressive_carries_90": {"progressivecarries"},
    "mf_progressive_passes_rec_90": {"progressivepassesrec", "progressivepassesreceived"},
    "mf_tackles_90": {"tackles"},
    "mf_interceptions_90": {"interceptions"},
    "mf_blocks_90": {"blocks"},
    "mf_clearances_90": {"clearances"},
    "mf_aerials_won_90": {"aerialswon"},
}
GOALKEEPER_LABELS = {
    "gk_save_percentage": {"savepercentage", "savepercent"},
    "gk_psxg_per_sot": {"psxgsot"},
    "gk_save_pct_penalty_kicks": {"savepercentpenaltykicks", "savepenaltykicks"},
    "gk_clean_sheet_percentage": {"cleansheetpercentage"},
    "gk_crosses_stopped_pct": {"crossesstoppedpercent"},
    "gk_def_actions_outside_pen_area": {"defactionsoutsidepenarea"},
    "gk_avg_distance_of_def_actions": {"avgdistanceofdefactions"},
}

def parse_scouting_per90(profile_html: str, desired_map: dict[str, set[str]]) -> dict:
    """Parse Scouting Report tables on a player page; return Per-90 dict for desired labels."""
    soup = BeautifulSoup(profile_html, "lxml")
    out = {col: "" for col in desired_map.keys()}
    tables = soup.select("table.stats_table")
    for tb in tables:
        thead = tb.find("thead")
        if not thead:
            continue
        head_cols = [th.get_text(strip=True).lower() for th in thead.find_all("th")]
        if not any("per 90" in c for c in head_cols) or not any("percentile" in c for c in head_cols):
            continue
        tbody = tb.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            stat_th = tr.find("th")
            tds = tr.find_all("td")
            if not stat_th or len(tds) < 1:
                continue
            label = _norm_label(stat_th.get_text(strip=True))
            per90 = tds[0].get_text(strip=True)  # first td is Per 90
            for out_col, synset in desired_map.items():
                if label in synset and not out[out_col]:
                    out[out_col] = per90
        if all(out[v] != "" for v in out):
            break
    return out

def maybe_to_numeric(s: pd.Series) -> pd.Series:
    if s.dtype != object:
        return s
    cleaned = (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.strip()
    )
    converted = pd.to_numeric(cleaned, errors="coerce")
    return converted if converted.notna().mean() >= 0.6 else s

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def scrape_fbref_club(driver: webdriver.Chrome, club_name: str, club_url: str) -> pd.DataFrame:
    base_url = "https://fbref.com"
    driver.get(club_url)


    try:
        consent = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//*[self::button or self::a][contains(translate(normalize-space(.),"
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]"
            ))
        )
        consent.click()
        time.sleep(0.4)
    except Exception:
        pass


    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[@id='stats_standard_combined' or @id='all_stats_standard_combined']")
        )
    )
    table = find_table_from_page_source(driver.page_source, "stats_standard_combined")
    if table is None:
        raise RuntimeError(f"Could not locate the 'stats_standard_combined' table for {club_name}.")


    thead_rows = table.find("thead").find_all("tr")
    header_cells = thead_rows[-1].find_all(["th", "td"])
    headers = [hc.get_text(strip=True) for hc in header_cells]
    counts = defaultdict(int)
    uniq_headers = []
    for h in headers:
        n = counts[h]
        uniq_headers.append(f"{h}_{n}" if n > 0 else h)
        counts[h] += 1

    rows = []
    achievements_list = []

    extra_cols = {
        # defenders
        "df_progressive_passes_rec_90": [], "df_tackles_90": [], "df_interceptions_90": [],
        "df_blocks_90": [], "df_clearances_90": [], "df_aerials_won_90": [],
        # midfielders
        "mf_shot_creating_actions_90": [], "mf_passes_attempted_90": [], "mf_pass_completion_pct": [],
        "mf_progressive_passes_90": [], "mf_progressive_carries_90": [], "mf_progressive_passes_rec_90": [],
        "mf_tackles_90": [], "mf_interceptions_90": [], "mf_blocks_90": [], "mf_clearances_90": [], "mf_aerials_won_90": [],
        # goalkeepers
        "gk_save_percentage": [], "gk_psxg_per_sot": [], "gk_save_pct_penalty_kicks": [],
        "gk_clean_sheet_percentage": [], "gk_crosses_stopped_pct": [], "gk_def_actions_outside_pen_area": [],
        "gk_avg_distance_of_def_actions": [],
    }

    tbody = table.find("tbody")
    profile_cache_html = {}

    for tr in tbody.find_all("tr"):
        if "class" in tr.attrs and "thead" in tr["class"]:
            continue
        first = tr.find("th")
        if not first:
            continue


        player_link_tag = first.find("a", href=True)
        player_name = first.get_text(strip=True)
        player_url = base_url + player_link_tag["href"] if player_link_tag else ""
        pos_cell = tr.find("td", {"data-stat": "position"})
        pos_text = pos_cell.get_text(strip=True) if pos_cell else ""
        role = classify_role(pos_text)

        cells = [player_name] + [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < len(uniq_headers):
            cells += [""] * (len(uniq_headers) - len(cells))
        rows.append(cells[:len(uniq_headers)])


        trophies = []
        role_data = {k: "" for k in extra_cols}

        if player_url:
            if player_url in profile_cache_html:
                profile_html = profile_cache_html[player_url]
            else:
                driver.get(player_url)
                try:
                    WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                except Exception:
                    pass
                profile_html = driver.page_source
                profile_cache_html[player_url] = profile_html

            psoup = BeautifulSoup(profile_html, "lxml")
            bling_ul = psoup.find("ul", id="bling")
            if bling_ul:
                trophies = [li.get_text(strip=True) for li in bling_ul.find_all("li", class_="important poptip")]

            if role == "defender":
                stats = parse_scouting_per90(profile_html, DEFENDER_LABELS)
                for k in DEFENDER_LABELS: role_data[k] = stats.get(k, "")
            elif role == "midfielder":
                stats = parse_scouting_per90(profile_html, MIDFIELDER_LABELS)
                for k in MIDFIELDER_LABELS: role_data[k] = stats.get(k, "")
            elif role == "goalkeeper":
                stats = parse_scouting_per90(profile_html, GOALKEEPER_LABELS)
                for k in GOALKEEPER_LABELS: role_data[k] = stats.get(k, "")

        achievements_list.append(", ".join(trophies))
        for k in extra_cols: extra_cols[k].append(role_data.get(k, ""))

        time.sleep(0.25)

    df = pd.DataFrame(rows, columns=uniq_headers)
    df["achievements"] = achievements_list
    for k, v in extra_cols.items():
        df[k] = v

 
    df.columns = [c.strip().replace(" ", "_").lower() for c in df.columns]
    df = df.apply(maybe_to_numeric)

 
    drop_cols = ["pos", "starts", "matches"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    rename_map = {
        "90s": "90s Played",
        "crdy": "Yellow Cards",
        "crdr": "Red Cards",
        "prgc": "Progressive Carries",
        "prgp": "Progressive Passes",
        "prgr": "Progressive Passes Received",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})

    # Handle duplicate names (append ' 90s' to later duplicates)
    seen, new_cols = {}, []
    for col in df.columns:
        if col not in seen:
            seen[col] = 0
            new_cols.append(col)
        else:
            seen[col] += 1
            new_cols.append(f"{col} 90s")
    df.columns = new_cols

    return df

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_window_size(1600, 1000)

    try:
        for club, url in CLUBS.items():
            print(f"\n--- Scraping {club} ---")
            df = scrape_fbref_club(driver, club, url)
            out_name = f"{slugify(club)}_fbref.csv"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"Saved {len(df)} rows → {out_path}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
