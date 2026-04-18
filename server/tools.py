import asyncio
from datetime import datetime, timedelta
import httpx

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

DEFENSE_COMPANIES = {
    "US": ["Lockheed Martin", "Raytheon Technologies", "Boeing Defense", "Northrop Grumman", "General Dynamics", "L3Harris Technologies", "Leidos"],
    "GB": ["BAE Systems", "Rolls-Royce Defence", "QinetiQ Group", "Ultra Electronics", "Babcock International"],
    "FR": ["Dassault Aviation", "Thales Group", "Airbus Defence & Space", "MBDA", "Naval Group"],
    "DE": ["Rheinmetall", "Diehl Defence", "Krauss-Maffei Wegmann", "ThyssenKrupp Marine Systems", "Airbus Defence (DE)"],
    "RU": ["Rostec Corporation", "Almaz-Antey", "United Aircraft Corp.", "Tactical Missiles Corp.", "Kalashnikov Concern"],
    "CN": ["AVIC (Aviation Industry Corp.)", "CETC", "CASIC", "NORINCO", "China Shipbuilding Industry Corp."],
    "IL": ["Elbit Systems", "Rafael Advanced Defence", "IAI (Israel Aerospace)", "IMI Systems", "Orbit International"],
    "IN": ["HAL (Hindustan Aeronautics)", "BEL (Bharat Electronics)", "DRDO", "Mahindra Defence Systems", "Tata Advanced Systems"],
    "IT": ["Leonardo S.p.A.", "Fincantieri", "Avio Aero", "Elettronica S.p.A.", "MBDA Italy"],
    "SE": ["Saab AB", "Nammo Sweden", "FMV (Swedish Defence Materiel)"],
    "KR": ["Hanwha Aerospace", "Korea Aerospace Industries (KAI)", "LIG Nex1", "Hyundai Rotem", "Korean Air Aerospace"],
    "JP": ["Mitsubishi Heavy Industries", "Kawasaki Heavy Industries Defence", "Fujitsu Defence", "NEC Defence & Space", "IHI Aerospace"],
    "AU": ["Austal", "CEA Technologies", "Thales Australia", "BAE Systems Australia"],
    "CA": ["CAE Inc.", "Bombardier Defence", "L3Harris Canada", "General Dynamics Canada"],
    "TR": ["Aselsan", "Roketsan", "Turkish Aerospace (TAI)", "STM Defence", "Baykar (Bayraktar UAV)"],
    "BR": ["Embraer Defence & Security", "Avibras", "Taurus Armas", "Imbel"],
    "PK": ["Pakistan Ordnance Factories", "Heavy Industries Taxila", "NESCOM"],
    "SA": ["Saudi Arabian Military Industries (SAMI)", "Alsalam Aircraft", "Advanced Electronics Co."],
    "UA": ["Ukroboronprom", "Motor Sich", "Antonov Company"],
    "NO": ["Kongsberg Defence & Aerospace", "Nammo", "Nordic Shelter"],
    "CH": ["RUAG Defence", "Mowag (General Dynamics)", "Pilatus Aircraft"],
    "PL": ["PGZ (Polish Armaments Group)", "Mesko S.A.", "WZM"],
    "ES": ["Indra Sistemas", "Navantia", "Airbus Spain", "GMV"],
    "NL": ["Thales Netherlands", "Fokker Technologies"],
    "SG": ["ST Engineering", "Singapore Technologies Kinetics"],
    "ZA": ["Denel SOC", "Armscor", "Paramount Group", "Reutech"],
    "GR": ["Hellenic Aerospace Industry (HAI)", "ELVO S.A.", "Pyrkal"],
}

TECH_COMPANIES = {
    "US": ["Apple", "Microsoft", "Alphabet (Google)", "Amazon", "Meta", "NVIDIA", "Tesla", "Intel", "IBM", "Qualcomm", "Salesforce", "Oracle"],
    "CN": ["Alibaba", "Tencent", "Huawei", "ByteDance (TikTok)", "Baidu", "Xiaomi", "JD.com", "Meituan", "NetEase"],
    "KR": ["Samsung Electronics", "LG Electronics", "SK Hynix", "Kakao", "Naver", "Krafton", "Coupang"],
    "JP": ["Sony Group", "Toyota (mobility tech)", "Fujitsu", "NTT Group", "SoftBank", "Panasonic", "Hitachi", "NEC", "Canon"],
    "DE": ["SAP", "Siemens Digital Industries", "Deutsche Telekom", "Infineon Technologies", "Software AG", "TeamViewer"],
    "GB": ["Arm Holdings", "DeepMind (Alphabet)", "Sage Group", "Aveva Group", "Revolut", "Wise", "Deliveroo"],
    "IN": ["Infosys", "TCS (Tata Consultancy)", "Wipro", "HCL Technologies", "Tech Mahindra", "Flipkart (Walmart)", "Paytm", "Zomato"],
    "SE": ["Spotify", "Klarna", "Ericsson", "Mojang (Microsoft/Minecraft)", "King (Candy Crush)", "Truecaller"],
    "NL": ["ASML", "Booking.com", "Philips", "TomTom", "Adyen"],
    "FR": ["Capgemini", "Dassault Systèmes", "Atos", "OVHcloud", "Criteo", "BlaBlaCar", "Ledger"],
    "IL": ["Wix.com", "Check Point Software", "CyberArk", "Amdocs", "NICE Systems", "Mobileye (Intel)", "monday.com"],
    "TW": ["TSMC", "MediaTek", "ASUS", "Acer", "Foxconn (Hon Hai)", "Realtek"],
    "CA": ["Shopify", "OpenText", "Blackberry", "Constellation Software", "Nuvei"],
    "AU": ["Atlassian", "Canva", "Afterpay (Block)", "WiseTech Global", "SafetyCulture"],
    "SG": ["Sea Limited (Shopee/Garena)", "Grab Holdings", "Razer Inc.", "Creative Technology"],
    "IT": ["Engineering Ingegneria", "Reply S.p.A.", "Bending Spoons"],
    "BR": ["Totvs", "CI&T", "Nu Holdings (Nubank)", "Stone Co.", "iFood"],
    "RU": ["Yandex", "Kaspersky Lab", "1C Company", "EPAM Systems"],
    "UA": ["EPAM Systems", "Grammarly", "GitLab", "MacPaw", "Ajax Systems"],
    "CH": ["ABB", "Logitech", "Temenos", "Avaloq", "Scandit"],
    "FI": ["Nokia", "Rovio Entertainment (Angry Birds)", "Supercell"],
    "IE": ["Accenture (HQ)", "Stripe", "Intercom", "Workhuman"],
    "PL": ["CD Projekt (The Witcher)", "Allegro", "Comarch", "Asseco"],
    "ES": ["Amadeus IT Group", "Glovo", "Cabify", "Wallapop"],
    "ZA": ["Naspers/Prosus", "MTN Group", "Takealot (Amazon)"],
    "NG": ["Flutterwave", "Paystack (Stripe)", "Andela"],
    "MX": ["Clip", "Kavak", "Bitso", "Kueski"],
    "DK": ["Unity Technologies", "Trustpilot", "Chainalysis"],
}


async def _wb_indicator(client: httpx.AsyncClient, code: str, indicator: str) -> float | None:
    """Fetch a single World Bank indicator value (most recent available)."""
    try:
        r = await client.get(
            f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}",
            params={"format": "json", "mrv": 3},
            timeout=7.0,
        )
        if r.status_code != 200:
            return None
        payload = r.json()
        if len(payload) > 1 and payload[1]:
            for entry in payload[1]:
                if entry.get("value") is not None:
                    return round(entry["value"], 2)
        return None
    except Exception:
        return None


# ── Weather ───────────────────────────────────────────────────────────────────

async def _fetch_weather(city: str, country: str, date: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 10, "language": "en", "format": "json"},
            )
            geo.raise_for_status()
            results = geo.json().get("results", [])
            if not results:
                return {"error": f"City '{city}' not found"}

            loc = None
            if country:
                cn = country.strip().lower()
                for r in results:
                    if r.get("country", "").lower() == cn or r.get("country_code", "").lower() == cn:
                        loc = r
                        break
            loc = loc or results[0]

            lat, lon, tz = loc["latitude"], loc["longitude"], loc.get("timezone", "UTC")
            today    = datetime.now().date()
            req_date = datetime.strptime(date, "%Y-%m-%d").date()

            if req_date > today + timedelta(days=16):
                return {"error": "Forecast only available up to 16 days ahead"}

            base = (
                "https://archive-api.open-meteo.com/v1/archive"
                if req_date < today
                else "https://api.open-meteo.com/v1/forecast"
            )
            wr = await client.get(base, params={
                "latitude": lat, "longitude": lon,
                "start_date": date, "end_date": date,
                "daily": "temperature_2m_max,temperature_2m_min,windspeed_10m_max,"
                         "weathercode,precipitation_sum,sunrise,sunset",
                "timezone": tz,
            })
            wr.raise_for_status()
            d = wr.json()["daily"]

            code    = (d.get("weathercode") or [0])[0] or 0
            sunrise = (d.get("sunrise")     or [None])[0]
            sunset  = (d.get("sunset")      or [None])[0]

            return {
                "city":               loc["name"],
                "country":            loc.get("country", country),
                "latitude":           lat,
                "longitude":          lon,
                "date":               date,
                "temp_max_celsius":   d["temperature_2m_max"][0],
                "temp_min_celsius":   d["temperature_2m_min"][0],
                "wind_speed_max_kmh": (d.get("windspeed_10m_max") or [None])[0],
                "precipitation_mm":   (d.get("precipitation_sum") or [None])[0],
                "sunrise": sunrise.split("T")[-1] if sunrise and "T" in sunrise else sunrise,
                "sunset":  sunset.split("T")[-1]  if sunset  and "T" in sunset  else sunset,
                "weather_code":       code,
                "description":        WMO_CODES.get(code, "Unknown"),
                "is_forecast":        req_date >= today,
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Country ───────────────────────────────────────────────────────────────────

async def _fetch_country(name: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"https://restcountries.com/v3.1/name/{name}")
            if r.status_code == 404:
                return {"error": "Country not found"}
            r.raise_for_status()
            c = r.json()[0]
            cca2 = c.get("cca2", "")

            base = {
                "common_name":  c["name"]["common"],
                "official_name": c["name"]["official"],
                "capital":      c.get("capital", ["N/A"])[0],
                "population":   c.get("population"),
                "region":       c.get("region"),
                "subregion":    c.get("subregion"),
                "languages":    list(c.get("languages", {}).values()),
                "currencies":   [v["name"] for v in c.get("currencies", {}).values()],
                "flag_emoji":   c.get("flag"),
                "area_km2":     c.get("area"),
                "timezones":    c.get("timezones", []),
                "country_code": cca2,
            }

            # World Bank indicators in parallel (best-effort)
            if cca2:
                mil, gdppc, hitech = await asyncio.gather(
                    _wb_indicator(client, cca2, "MS.MIL.XPND.GD.ZS"),
                    _wb_indicator(client, cca2, "NY.GDP.PCAP.CD"),
                    _wb_indicator(client, cca2, "TX.VAL.TECH.MF.ZS"),
                )
                base["gdp_per_capita_usd"]     = gdppc
                base["military_spend_pct_gdp"] = mil
                base["hitech_exports_pct"]     = hitech

            base["defense_companies"] = DEFENSE_COMPANIES.get(cca2, [])
            base["tech_companies"]    = TECH_COMPANIES.get(cca2, [])

            return base
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Crypto (spot) ─────────────────────────────────────────────────────────────

async def _fetch_crypto(coin_id: str, vs_currency: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": vs_currency,
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                },
            )
            if r.status_code == 429:
                return {"error": "CoinGecko rate limit reached — wait 60 seconds and try again"}
            r.raise_for_status()
            data = r.json().get(coin_id.lower())
            if not data:
                return {"error": f"Coin '{coin_id}' not found on CoinGecko"}
            return {
                "coin":              coin_id,
                "currency":          vs_currency,
                "price":             data.get(vs_currency),
                "market_cap":        data.get(f"{vs_currency}_market_cap"),
                "24h_volume":        data.get(f"{vs_currency}_24h_vol"),
                "24h_change_percent": data.get(f"{vs_currency}_24h_change"),
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Crypto (historical chart) ─────────────────────────────────────────────────

async def _fetch_crypto_history(coin_id: str, vs_currency: str, days: int) -> dict:
    days = max(1, min(days, 365))
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
                params={"vs_currency": vs_currency, "days": days, "interval": "daily"},
            )
            if r.status_code == 429:
                return {"error": "CoinGecko rate limited — wait 60 seconds"}
            if r.status_code == 404:
                return {"error": f"Coin '{coin_id}' not found on CoinGecko"}
            r.raise_for_status()

            data    = r.json()
            prices  = data.get("prices", [])
            volumes = data.get("total_volumes", [])

            if not prices:
                return {"error": "No price data returned"}

            series = [
                {
                    "date":   datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                    "price":  round(price, 4),
                    "volume": round(volumes[i][1], 0) if i < len(volumes) else None,
                }
                for i, (ts, price) in enumerate(prices)
            ]

            first, last = series[0]["price"], series[-1]["price"]
            high = max(s["price"] for s in series)
            low  = min(s["price"] for s in series)
            chg  = ((last - first) / first * 100) if first else 0

            return {
                "coin":           coin_id,
                "currency":       vs_currency,
                "days":           days,
                "current_price":  last,
                "start_price":    first,
                "period_high":    high,
                "period_low":     low,
                "change_percent": round(chg, 2),
                "series":         series,
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── IP Geolocation ────────────────────────────────────────────────────────────

async def _fetch_ip(ip: str) -> dict:
    try:
        url = "http://ip-api.com/json/" if ip.strip().lower() == "self" else f"http://ip-api.com/json/{ip}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            if data.get("status") == "fail":
                return {"error": data.get("message", "IP lookup failed")}
            return {
                "ip":           data.get("query"),
                "city":         data.get("city"),
                "region":       data.get("regionName"),
                "country":      data.get("country"),
                "country_code": data.get("countryCode"),
                "isp":          data.get("isp"),
                "org":          data.get("org"),
                "latitude":     data.get("lat"),
                "longitude":    data.get("lon"),
                "timezone":     data.get("timezone"),
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Hacker News ───────────────────────────────────────────────────────────────

async def _fetch_news(count: int) -> list:
    count = max(1, min(count, 30))
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            r.raise_for_status()
            ids = r.json()[:count]

            async def fetch_item(item_id):
                try:
                    res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
                    res.raise_for_status()
                    d = res.json()
                    return {
                        "id":       d.get("id"),
                        "title":    d.get("title"),
                        "url":      d.get("url", f"https://news.ycombinator.com/item?id={d.get('id')}"),
                        "score":    d.get("score"),
                        "by":       d.get("by"),
                        "comments": d.get("descendants", 0),
                        "time_unix": d.get("time"),
                    }
                except Exception:
                    return None

            items = await asyncio.gather(*[fetch_item(i) for i in ids])
            return [item for item in items if item is not None]
    except httpx.RequestError as e:
        return [{"error": str(e)}]
    except Exception as e:
        return [{"error": str(e)}]


# ── GitHub ────────────────────────────────────────────────────────────────────

async def _fetch_github(owner: str, repo: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            repo_r, readme_r = await asyncio.gather(
                client.get(
                    f"https://api.github.com/repos/{owner}/{repo}",
                    headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                ),
                client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/readme",
                    headers={"Accept": "application/vnd.github.raw+json", "X-GitHub-Api-Version": "2022-11-28"},
                ),
            )

            if repo_r.status_code == 404:
                return {"error": f"Repository '{owner}/{repo}' not found"}
            if repo_r.status_code == 403:
                return {"error": "GitHub rate limit exceeded — try again later"}
            repo_r.raise_for_status()
            d = repo_r.json()

            # Extract first 3 non-empty lines of README as snippet
            readme_snippet = None
            if readme_r.status_code == 200:
                lines = [l.strip() for l in readme_r.text.splitlines() if l.strip() and not l.strip().startswith("!")]
                readme_snippet = " ".join(lines[:3])[:400] if lines else None

            return {
                "name":           d["name"],
                "full_name":      d["full_name"],
                "description":    d.get("description"),
                "readme_snippet": readme_snippet,
                "stars":          d["stargazers_count"],
                "forks":          d["forks_count"],
                "watchers":       d["watchers_count"],
                "open_issues":    d["open_issues_count"],
                "language":       d.get("language"),
                "license":        d.get("license", {}).get("name") if d.get("license") else None,
                "topics":         d.get("topics", []),
                "default_branch": d["default_branch"],
                "homepage":       d.get("homepage"),
                "html_url":       d["html_url"],
                "created_at":     d["created_at"],
                "updated_at":     d["updated_at"],
                "size_kb":        d.get("size"),
                "is_fork":        d.get("fork", False),
                "has_wiki":       d.get("has_wiki", False),
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Exchange Rates ────────────────────────────────────────────────────────────

async def _fetch_exchange_rates(base: str = "USD") -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"https://open.er-api.com/v6/latest/{base.upper()}")
            r.raise_for_status()
            data = r.json()
            if data.get("result") == "error":
                return {"error": data.get("error-type", "Invalid base currency")}

            rates = data.get("rates", {})
            major = [
                "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR", "BRL",
                "MXN", "KRW", "SGD", "HKD", "NOK", "SEK", "DKK", "NZD", "ZAR", "TRY",
                "AED", "SAR", "THB", "IDR", "MYR", "PHP", "PKR", "RUB", "EGP", "NGN",
            ]
            major_rates = {c: rates[c] for c in major if c in rates and c != base.upper()}

            return {
                "base":             base.upper(),
                "updated":          data.get("time_last_update_utc", ""),
                "major_rates":      major_rates,
                "total_currencies": len(rates),
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


# ── Stock Data ────────────────────────────────────────────────────────────────

async def _fetch_stock(symbol: str, period: str = "1mo") -> dict:
    valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"}
    if period not in valid_periods:
        period = "1mo"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}",
                params={"interval": "1d", "range": period},
                headers={"User-Agent": "Mozilla/5.0 (compatible; MCPExplorer/1.0)"},
            )
            if r.status_code == 404:
                return {"error": f"Symbol '{symbol}' not found on Yahoo Finance"}
            r.raise_for_status()
            data  = r.json()
            chart = data.get("chart", {})
            err   = chart.get("error")
            if err:
                return {"error": err.get("description", "Yahoo Finance error")}

            result_list = chart.get("result")
            if not result_list:
                return {"error": "No data returned from Yahoo Finance"}

            meta       = result_list[0]["meta"]
            timestamps = result_list[0].get("timestamp", [])
            quotes     = result_list[0].get("indicators", {}).get("quote", [{}])[0]

            closes  = quotes.get("close",  [])
            highs   = quotes.get("high",   [])
            lows    = quotes.get("low",    [])
            volumes = quotes.get("volume", [])

            series = []
            for i, ts in enumerate(timestamps):
                close = closes[i] if i < len(closes) else None
                if close is not None:
                    series.append({
                        "date":   datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                        "close":  round(close, 2),
                        "high":   round(highs[i],   2) if i < len(highs)   and highs[i]   else None,
                        "low":    round(lows[i],    2) if i < len(lows)    and lows[i]    else None,
                        "volume": volumes[i]              if i < len(volumes) and volumes[i] else None,
                    })

            current = meta.get("regularMarketPrice")
            prev    = meta.get("previousClose") or meta.get("chartPreviousClose")
            change  = ((current - prev) / prev * 100) if current and prev and prev != 0 else None

            return {
                "symbol":         meta.get("symbol", symbol.upper()),
                "name":           meta.get("shortName") or meta.get("longName") or symbol.upper(),
                "exchange":       meta.get("exchangeName", ""),
                "currency":       meta.get("currency", "USD"),
                "current_price":  current,
                "previous_close": prev,
                "change_percent": round(change, 2) if change is not None else None,
                "week52_high":    meta.get("fiftyTwoWeekHigh"),
                "week52_low":     meta.get("fiftyTwoWeekLow"),
                "market_state":   meta.get("marketState", ""),
                "period":         period,
                "series":         series,
                "data_points":    len(series),
            }
    except httpx.RequestError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
