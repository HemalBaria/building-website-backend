from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_URL = "https://propsearch.ae"


async def scrape_building(slug: str) -> dict:
    url = f"{BASE_URL}/dubai/{slug}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)

    developer = ""
    if "development by" in text.lower():
        idx = text.lower().index("development by")
        snippet = text[idx:idx+200]
        for line in snippet.split("\n"):
            if "development by" in line.lower():
                developer = line.split("development by")[-1].strip().rstrip(".")
                break

    location = ""
    for phrase in ["complex in", "tower in", "building in", "development in"]:
        if phrase in text.lower():
            idx = text.lower().index(phrase)
            snippet = text[idx:idx+100]
            location = snippet.split("in ")[-1].split(",")[0].split(".")[0].strip()
            break

    start_date = ""
    if "construction began in" in text.lower():
        idx = text.lower().index("construction began in")
        snippet = text[idx:idx+50]
        start_date = snippet.split("in ")[-1].split(".")[0].split("\n")[0].strip()

    handover_date = ""
    if "completed" in text.lower():
        for line in text.split("\n"):
            if "completed" in line.lower() and any(c.isdigit() for c in line):
                for p in line.split():
                    if p.isdigit() and len(p) == 4:
                        handover_date = p
                        break
                if handover_date:
                    break

    units = ""
    beds_found = []
    if "studio" in text.lower(): beds_found.append("Studio")
    if "1 bed" in text.lower() or "1-bed" in text.lower(): beds_found.append("1 BHK")
    if "2 bed" in text.lower() or "2-bed" in text.lower(): beds_found.append("2 BHK")
    if "3 bed" in text.lower() or "3-bed" in text.lower(): beds_found.append("3 BHK")
    if "4 bed" in text.lower() or "4-bed" in text.lower(): beds_found.append("4 BHK")
    units = ", ".join(beds_found)

    amenities = ""
    if "amenities" in text.lower():
        idx = text.lower().index("amenities")
        snippet = text[idx:idx+500].replace("\n", " ")
        for s in snippet.split("."):
            if "include" in s.lower() or "pool" in s.lower() or "gym" in s.lower():
                amenities = s.strip()
                break

    total_units = ""
    for pattern in ["total of", "contains", "comprising", "houses"]:
        if pattern in text.lower() and "unit" in text.lower():
            idx = text.lower().index(pattern)
            snippet = text[idx:idx+80]
            for word in snippet.split():
                cleaned = word.replace(",", "").replace(".", "")
                if cleaned.isdigit() and int(cleaned) > 1:
                    total_units = word
                    break
            if total_units:
                break
    if not total_units:
        import re
        match = re.search(r'(\d[\d,]*)\s*(?:units|apartments|residences)', text, re.IGNORECASE)
        if match:
            total_units = match.group(1)

    storeys = ""
    if "storey" in text.lower():
        for line in text.split("\n"):
            if "storey" in line.lower():
                storeys = line.strip()
                break

    photos = []
    # Try to get the main building image (usually the first large image or og:image)
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        photos.append(og_img["content"])
    else:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "static.propsearch.ae/photos" in src and slug in src.lower():
                photos.append(src)
                break
        if not photos:
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "static.propsearch.ae/photos" in src:
                    photos.append(src)
                    break

    return {
        "name": name,
        "developer": developer,
        "location": location,
        "start_date": start_date,
        "handover_date": handover_date,
        "units": units,
        "amenities": amenities,
        "total_units": total_units,
        "storeys": storeys,
        "photos": photos,
    }


@app.get("/api/building/{slug:path}")
async def get_building(slug: str):
    slug = slug.strip().lower().replace(" ", "-")
    return await scrape_building(slug)
