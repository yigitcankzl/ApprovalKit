"""
TravelOps Backend
=================
Standalone FastAPI app for the TravelOps travel booking dashboard.
Serves the frontend and calls ApprovalKit API for approval-gated bookings.
"""
import os
import sys
import json
import uuid
import hmac
import hashlib
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

APPROVALKIT_URL = os.getenv("APPROVALKIT_URL", "http://localhost:8000")
API_KEY = os.getenv("APPROVALKIT_API_KEY", "")
HMAC_SECRET = os.getenv("APPROVALKIT_HMAC_SECRET", "")

app = FastAPI(title="TravelOps Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Travel Data ───────────────────────────────────────────────────────────────

FLIGHTS = {
    "berlin": [
        {"id": "f1", "airline": "Lufthansa", "flight_no": "LH1834", "price": 420, "class": "economy", "duration": "2h 35m", "departure": "08:30"},
        {"id": "f2", "airline": "Turkish Airlines", "flight_no": "TK1721", "price": 680, "class": "economy", "duration": "3h 45m", "departure": "11:15"},
        {"id": "f3", "airline": "Lufthansa", "flight_no": "LH1834", "price": 1850, "class": "business", "duration": "2h 35m", "departure": "08:30"},
    ],
    "london": [
        {"id": "f4", "airline": "British Airways", "flight_no": "BA680", "price": 350, "class": "economy", "duration": "3h 50m", "departure": "07:00"},
        {"id": "f5", "airline": "British Airways", "flight_no": "BA680", "price": 1400, "class": "business", "duration": "3h 50m", "departure": "07:00"},
    ],
    "new york": [
        {"id": "f6", "airline": "Delta", "flight_no": "DL34", "price": 890, "class": "economy", "duration": "10h 20m", "departure": "22:00"},
        {"id": "f7", "airline": "Delta", "flight_no": "DL34", "price": 3200, "class": "business", "duration": "10h 20m", "departure": "22:00"},
    ],
    "san francisco": [
        {"id": "f8", "airline": "United", "flight_no": "UA90", "price": 950, "class": "economy", "duration": "13h 15m", "departure": "16:30"},
        {"id": "f9", "airline": "United", "flight_no": "UA90", "price": 3800, "class": "business", "duration": "13h 15m", "departure": "16:30"},
    ],
    "tokyo": [
        {"id": "f10", "airline": "ANA", "flight_no": "NH210", "price": 1100, "class": "economy", "duration": "12h 30m", "departure": "13:00"},
        {"id": "f11", "airline": "ANA", "flight_no": "NH210", "price": 4200, "class": "business", "duration": "12h 30m", "departure": "13:00"},
    ],
}

HOTELS = {
    "berlin": [
        {"id": "h1", "name": "Holiday Inn Berlin Centre", "price": 95, "stars": 3, "rating": 4.1},
        {"id": "h2", "name": "Motel One Alexanderplatz", "price": 120, "stars": 3, "rating": 4.3},
        {"id": "h3", "name": "Hotel Adlon Kempinski", "price": 380, "stars": 5, "rating": 4.8},
    ],
    "london": [
        {"id": "h4", "name": "Premier Inn London City", "price": 110, "stars": 3, "rating": 4.0},
        {"id": "h5", "name": "The Savoy", "price": 520, "stars": 5, "rating": 4.9},
    ],
    "new york": [
        {"id": "h6", "name": "Pod 51 Hotel", "price": 130, "stars": 3, "rating": 4.0},
        {"id": "h7", "name": "The Plaza", "price": 650, "stars": 5, "rating": 4.7},
    ],
    "san francisco": [
        {"id": "h8", "name": "HI San Francisco", "price": 85, "stars": 2, "rating": 3.8},
        {"id": "h9", "name": "The Ritz-Carlton", "price": 490, "stars": 5, "rating": 4.8},
    ],
    "tokyo": [
        {"id": "h10", "name": "APA Hotel Shinjuku", "price": 75, "stars": 3, "rating": 4.0},
        {"id": "h11", "name": "Park Hyatt Tokyo", "price": 580, "stars": 5, "rating": 4.9},
    ],
}

DESTINATIONS = [
    {"id": "berlin", "name": "Berlin", "country": "Germany", "visa": False},
    {"id": "london", "name": "London", "country": "UK", "visa": False},
    {"id": "new york", "name": "New York", "country": "USA", "visa": True},
    {"id": "san francisco", "name": "San Francisco", "country": "USA", "visa": True},
    {"id": "tokyo", "name": "Tokyo", "country": "Japan", "visa": True},
]


# ── ApprovalKit SDK (inline) ─────────────────────────────────────────────────

def _sign_request(body_json: str) -> dict:
    ts = str(int(time.time()))
    message = f"{ts}.{body_json}"
    sig = hmac.new(HMAC_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={ts}.{sig}",
        "Content-Type": "application/json",
    }


async def approvalkit_request(connection: str, action: str, params: dict) -> dict:
    """Send approval request to ApprovalKit API."""
    body = {
        "connection": connection,
        "action": action,
        "params": params,
        "user_id": "travelops-agent",
        "idempotency_key": f"tvl-{uuid.uuid4()}",
    }
    body_json = json.dumps(body)
    headers = _sign_request(body_json)

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{APPROVALKIT_URL}/api/v1/request", content=body_json, headers=headers)
        if r.status_code not in (200, 202):
            return {"status": "error", "detail": r.text}
        return r.json()


async def approvalkit_status(job_id: str) -> dict:
    """Poll job status (uses test endpoint — no HMAC needed)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{APPROVALKIT_URL}/api/v1/test-status/{job_id}")
        if r.status_code != 200:
            return {"status": "error"}
        return r.json()


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/destinations")
async def list_destinations():
    return DESTINATIONS


@app.get("/api/flights/{destination}")
async def search_flights(destination: str):
    return FLIGHTS.get(destination.lower(), [])


@app.get("/api/hotels/{destination}")
async def search_hotels(destination: str):
    return HOTELS.get(destination.lower(), [])


class BookingRequest(BaseModel):
    traveler: str
    destination: str
    purpose: str
    flight_id: str
    hotel_id: str
    nights: int = 3


class StepRequest(BaseModel):
    connection: str
    action: str
    params: dict


@app.post("/api/book")
async def book_trip(req: BookingRequest):
    """Initiate full trip booking — returns trip_id for status polling."""
    dest = req.destination.lower()
    flights = FLIGHTS.get(dest, [])
    hotels = HOTELS.get(dest, [])
    flight = next((f for f in flights if f["id"] == req.flight_id), None)
    hotel = next((h for h in hotels if h["id"] == req.hotel_id), None)

    if not flight or not hotel:
        raise HTTPException(status_code=400, detail="Invalid flight or hotel selection")

    hotel_total = hotel["price"] * req.nights
    dest_info = next((d for d in DESTINATIONS if d["id"] == dest), None)

    return {
        "trip_id": f"TVL-{uuid.uuid4().hex[:8].upper()}",
        "traveler": req.traveler,
        "destination": req.destination,
        "purpose": req.purpose,
        "flight": flight,
        "hotel": {**hotel, "nights": req.nights, "total": hotel_total},
        "insurance": {"name": "Basic Travel Cover", "price": 29, "coverage": "$50,000"},
        "visa_required": dest_info["visa"] if dest_info else False,
        "estimated_total": flight["price"] + hotel_total + 29,
    }


@app.post("/api/approve-step")
async def approve_step(req: StepRequest):
    """Send a single step to ApprovalKit for approval."""
    result = await approvalkit_request(req.connection, req.action, req.params)
    return result


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Poll ApprovalKit job status."""
    return await approvalkit_status(job_id)


@app.get("/api/health")
async def health():
    return {"status": "ok", "approvalkit": APPROVALKIT_URL}
