# Giants of Europe, Price of Performance  
**2024/25 Market-Value Analysis of Barcelona, Real Madrid, Liverpool, Arsenal & PSG**

## 📌 Project Overview
This project scrapes player statistics and market values from **FBref** and **Transfermarkt**, merges the data, and applies a custom ranking methodology.  
The final analysis explores the relationship between performance and market value across five European giants:  
- FC Barcelona  
- Real Madrid  
- Liverpool  
- Arsenal  
- PSG  


## Ranking Methodology

The ranking system is role-specific, ensuring players are only compared within their position group.
Performance scores are calculated using weighted Z-scores (measuring relative performance compared to others in the same role).

### Forwards (FWD)
- 40% Goals scored per 90 minutes
- 15% Non-penalty xG per 90
- 10% xG per 90
- 10% Assists per 90
- 10% Expected assists (xAG) per 90
- 5% Progressive carries per 90
- 10% Progressive passes received per 90
- Discipline penalty: –5% (yellow and red cards, with red cards weighted more heavily)

### Midfielders (MF)
- 25% Shot-creating actions per 90
- 20% Progressive passes per 90
- 15% Progressive carries per 90
- 5% Progressive passes received per 90
- 10% Assists per 90
- 10% Passes attempted per 90
- 10% Pass completion percentage
- 5% Tackles per 90
- 5% Interceptions per 90

### Defenders (DF)
- 20% Interceptions per 90
- 20% Tackles per 90
- 15% Blocks per 90
- 15% Clearances per 90
- 15% Aerial duels won per 90
- 10% Progressive passes received per 90
- Discipline penalty: –5% (same method as forwards)

### Goalkeepers (GK)
- 40% Save percentage
- 20% Clean sheet percentage
- 10% Crosses stopped %
- 10% Defensive actions outside penalty area
- 5% Average distance of defensive actions
- 10% Save percentage on penalties
- 5% Post-shot expected goals per shot on target (PSxG/SoT)



## Underrated Player Ranking

An "underrated" score is calculated as:

Performance Score ÷ Market Value (in euros)

This highlights players who deliver strong performances relative to their transfer value.


Eligibility conditions

A player is only considered for the underrated ranking if:

They have played at least 20 full 90s.
Their market value is available and greater than zero.
Their age is under 30.
They have a clearly identified role (FWD, MF, DF, GK).


## Key Findings

- Domestic vs Foreign Players: Clubs lean more toward domestic players rather than foreign players(English, Spanish and French respectively), like the English clubs : Liverpool and Arsenal have more English player compared to SPpanish clubs and French club.

- Age strongly influences market value: Market value peaks between the ages of 23 and 26, after which it declines steadily. Very young players (16–18) also tend to have lower values, reflecting limited experience.

- Position and market value are correlated: On average, forwards hold the highest market value, followed by midfielders and defenders, with goalkeepers typically valued the lowest.

- Fairness and defenders’ valuation: Defenders fairness do not affect their respective market value much. Also highly consistent and reliable defenders (e.g., Van Dijk, Saliba, Hakimi) do not reach the same market value levels as star forwards, showing a positional undervaluation bias in the transfer market.

- Goal contribution drives market value: A strong positive relationship exists between a player’s combined goals and assists (G+A) and their average market value, reinforcing attacking output as the most rewarded metric.

- Market inefficiencies: Some defenders and goalkeepers demonstrate excellent performance metrics but are comparatively undervalued, suggesting opportunities for identifying “underrated” players.



The analysis is visualized in Tableau and can be accessed from the below link:  
[Tableau Dashboard](https://public.tableau.com/app/profile/sourav.das3794/viz/FootballMarketValueAnalysis/Intro)

---

## 📜 License
This project is licensed under the [MIT License](LICENSE) © 2025 Sourav Das

