# scrape_transfermarkt_all.py
# pip install selenium pandas

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time, subprocess, os
from pathlib import Path


CHROMEDRIVER_PATH = r"C:\Users\Lenovo\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"

CLUBS = [
    {
        "name": "Barcelona",
        "league": "La Liga",
        "url": "https://www.transfermarkt.co.uk/fc-barcelona/kader/verein/131/plus/1/galerie/0?saison_id=2024",
        "csv": "barcelonatransfermarket.csv",
    },
    {
        "name": "Real Madrid",
        "league": "La Liga",
        "url": "https://www.transfermarkt.co.uk/real-madrid/kader/verein/418/plus/1/galerie/0?saison_id=2024",
        "csv": "realmadridtransfermarket.csv",
    },
    {
        "name": "Liverpool",
        "league": "Premier League",
        "url": "https://www.transfermarkt.co.uk/fc-liverpool/kader/verein/31/plus/1/galerie/0?saison_id=2024",
        "csv": "liverpooltransfermarket.csv",
    },
    {
        "name": "Arsenal",
        "league": "Premier League",
        "url": "https://www.transfermarkt.co.uk/fc-arsenal/kader/verein/11/plus/1/galerie/0?saison_id=2024",
        "csv": "arsenaltransfermarket.csv",
    },
    {
        "name": "PSG",
        "league": "Ligue 1",
        "url": "https://www.transfermarkt.co.uk/paris-saint-germain/kader/verein/583/plus/1/galerie/0?saison_id=2024",
        "csv": "psgtransfermarket.csv",
    },
]


def resolve_project_root() -> Path:
    p = Path(__file__).resolve().parent
    # climb out of venv/Scripts if the script lives there
    while p.name.lower() in ("venv", "scripts"):
        p = p.parent
    return p

PROJECT_ROOT = resolve_project_root()
OUTPUT_DIR = PROJECT_ROOT / "outputs"



def make_driver():
    opts = Options()
    # opts.add_argument("--headless=new")  # uncomment for headless
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(executable_path=CHROMEDRIVER_PATH, log_output=subprocess.DEVNULL)
    return webdriver.Chrome(service=service, options=opts)

def accept_popup(driver):
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        clicked = False
        for frame in frames:
            driver.switch_to.frame(frame)
            try:
                btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept & continue')]"))
                )
                btn.click()
                clicked = True
                print("Popup accepted.")
                break
            except Exception:
                driver.switch_to.default_content()
                continue
        driver.switch_to.default_content()
        if not clicked:
            print("Popup not found — maybe already dismissed.")
    except Exception:
        print("No popup found.")

def scrape_table(driver, club_name: str, league_name: str) -> pd.DataFrame:
 
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.items")))
    rows = driver.find_elements(By.CSS_SELECTOR, "table.items tbody tr.odd, table.items tbody tr.even")

    data = []
    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")


        player_lines = [line.strip() for line in tds[1].text.split("\n") if line.strip()]
        player = player_lines[0] if player_lines else ""
        position = player_lines[1] if len(player_lines) > 1 else ""


        dob_age = tds[5].text.strip()
        height = tds[8].text.strip()
        foot = tds[9].text.strip()
        market_value = tds[12].text.strip()
        if market_value == "—":
            market_value = "N/A"

        data.append({
            "Player": player,
            "Position": position,
            "Date of birth / Age": dob_age,
            "Height": height,
            "Foot": foot,
            "Market value": market_value,
            "Club": club_name,
            "League": league_name
        })

    return pd.DataFrame(data)

def run_one(driver, club_conf: dict):
    print(f"\n--- Scraping {club_conf['name']} ---")
    driver.get(club_conf["url"])
    accept_popup(driver)
    df = scrape_table(driver, club_conf["name"], club_conf["league"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / club_conf["csv"]
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Extracted {len(df)} rows -> {out_path.resolve()}")

    try:
        print(df.head())
    except Exception:
        pass

def main():
    driver = make_driver()
    try:
        for club_conf in CLUBS:
            run_one(driver, club_conf)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
