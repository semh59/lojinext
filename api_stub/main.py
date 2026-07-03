"""Deterministic local stub server for external HTTP boundaries.

0-mock epiği Kategori B: Mapbox/OpenRoute/Open-Meteo/Telegram/Groq'un
gerçek API şekillerini taklit eden, GERÇEK bir HTTP sunucusu (in-process
mock değil). Testler gerçek `httpx` ile buraya bağlanır — app'in
`*_API_BASE_URL` settings alanları test/CI'da bu servisin adresine
işaret eder (bkz. app/config.py), path yapısı gerçek API'lerle BİREBİR
aynı (client kodu değişmeden çalışsın diye) — sadece host değişir.

Bilinçli olarak sabit/deterministik: her istek için aynı canned
response döner (rota/coğrafya gerçekçi ama sabit), böylece testler
flaky olmaz. Hata-enjeksiyonu ihtiyacı olan testler (timeout/5xx) için
`?simulate=timeout` / `?simulate=error` / `?simulate=notfound` query
param'ı her endpoint'te desteklenir — bu da gerçek bir HTTP davranışı,
mock değil.
"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="LojiNext API Stub", docs_url=None, redoc_url=None)


async def _maybe_simulate(request: Request) -> JSONResponse | None:
    mode = request.query_params.get("simulate")
    if mode == "timeout":
        await asyncio.sleep(30)
    if mode == "error":
        return JSONResponse(status_code=500, content={"error": "simulated_error"})
    if mode == "notfound":
        return JSONResponse(status_code=404, content={"error": "simulated_not_found"})
    return None


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Mapbox Directions — MAPBOX_API_BASE_URL already includes this full prefix;
# client appends only the trailing "/{lon1},{lat1};{lon2},{lat2}".
# ---------------------------------------------------------------------------
@app.get("/directions/v5/mapbox/driving-traffic/{coords}")
async def mapbox_directions(coords: str, request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    # Sentinel-coordinate scenarios: when the client can't forward an extra
    # ?simulate= query param (its own params dict is hardcoded), the
    # coordinates themselves select the scenario — a real, deterministic
    # HTTP behavior (same technique as e.g. Stripe's test card numbers),
    # not an in-process mock. Format: "0,0;0,<scenario>".
    if coords.startswith("0.0,0.0;0.0,"):
        scenario = coords.rsplit(",", 1)[-1]
        if scenario == "401.0":
            return JSONResponse(status_code=401, content={"message": "Unauthorized"})
        if scenario == "422.0":
            return JSONResponse(status_code=422, content={"message": "Invalid Input"})
        if scenario == "200.0":
            return JSONResponse({"routes": []})
        if scenario == "408.0":
            await asyncio.sleep(30)

    # Deterministic ~450km route, mixed motorway/primary road classification.
    geometry = {
        "type": "LineString",
        "coordinates": [[29.0, 41.0], [30.5, 40.5], [32.85, 39.93]],
    }
    return JSONResponse(
        {
            "routes": [
                {
                    "geometry": geometry,
                    "distance": 450000.0,
                    "duration": 19800.0,
                    "legs": [
                        {
                            "steps": [
                                {
                                    "intersections": [
                                        {
                                            "geometry_index": 0,
                                            "mapbox_streets_v8": {"class": "motorway"},
                                        }
                                    ]
                                },
                                {
                                    "intersections": [
                                        {
                                            "geometry_index": 1,
                                            "mapbox_streets_v8": {"class": "primary"},
                                        }
                                    ]
                                },
                            ],
                            "annotation": {
                                "distance": [225000.0, 225000.0],
                                "duration": [9900.0, 9900.0],
                                "maxspeed": [
                                    {"speed": 120, "unit": "km/h"},
                                    {"speed": 50, "unit": "km/h"},
                                ],
                            },
                        }
                    ],
                }
            ],
            "code": "Ok",
        }
    )


# ---------------------------------------------------------------------------
# OpenRoute Directions — OPENROUTE_API_BASE_URL = "{host}/v2"; client appends
# "/directions/{profile}/json".
# ---------------------------------------------------------------------------
@app.post("/v2/directions/{profile}/json")
async def openroute_directions(profile: str, request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    # Sentinel-coordinate scenarios (POST body, not URL — see the Mapbox
    # endpoint's docstring for why this technique is used instead of
    # ?simulate=). Format: coordinates=[[0,0],[0,<scenario>]].
    try:
        body = await request.json()
        coords = body.get("coordinates") or []
        if len(coords) == 2 and coords[0] == [0, 0] and isinstance(coords[1], list):
            scenario = coords[1][0]
            if scenario == 403:
                return JSONResponse(status_code=403, content={"error": {"code": 2010}})
            if scenario == 404:
                return JSONResponse(status_code=404, content={"error": {"code": 2004}})
            if scenario == 429:
                return JSONResponse(status_code=429, content={"error": {"code": 2009}})
            if scenario == 500:
                return JSONResponse(status_code=500, content={"error": {"code": 9999}})
            if scenario == 200:
                return JSONResponse({"routes": []})
            if scenario == 408:
                await asyncio.sleep(30)
            if scenario == 777:
                # Geometry already decoded as a GeoJSON coordinate list.
                return JSONResponse(
                    {
                        "routes": [
                            {
                                "summary": {
                                    "distance": 80000.0,
                                    "duration": 3000.0,
                                    "ascent": 200.0,
                                    "descent": 180.0,
                                },
                                "geometry": [
                                    [29.0, 40.0],
                                    [30.0, 39.5],
                                    [32.0, 39.0],
                                ],
                                "extras": {"steepness": {}},
                            }
                        ]
                    }
                )
    except Exception:
        pass

    return JSONResponse(
        {
            "routes": [
                {
                    "summary": {
                        "distance": 450000.0,
                        "duration": 19800.0,
                        "ascent": 620.0,
                        "descent": 580.0,
                    },
                    "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
                    # "values" (not "summary") is the real ORS extra_info shape
                    # RouteAnalyzer._parse_extra_segments actually reads —
                    # [[start_idx, end_idx, code]] over the 3-point decoded
                    # polyline above. Lets tests exercise the real segment
                    # classification path instead of the empty-extras fallback.
                    "extras": {
                        "steepness": {"values": [[0, 2, 0]]},
                        "waytype": {"values": [[0, 2, 1]]},
                        "waycategory": {"values": [[0, 2, 1]]},
                        "surface": {"values": [[0, 2, 1]]},
                    },
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# OpenRoute Directions (GeoJSON) — app/services/route_service.py's own ORS
# client (a separate class from OpenRouteClient/OpenRouteService) requests
# "/directions/{profile}/geojson" (features/properties shape, not
# routes/summary). Sentinel: coordinates=[[0,0],[0,999]] → anomalous
# elevation (ascent 5000m) so RouteValidator's self-heal/hybrid path
# engages — same sentinel-coordinate technique as the other endpoints.
# ---------------------------------------------------------------------------
@app.post("/v2/directions/{profile}/geojson")
async def openroute_directions_geojson(profile: str, request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    try:
        body = await request.json()
        coords = body.get("coordinates") or []
        if len(coords) == 2 and coords[0] == [0, 0] and coords[1] == [0, 500]:
            return JSONResponse(status_code=500, content={"error": {"code": 9999}})
        if len(coords) == 2 and coords[0] == [0, 0] and coords[1] == [0, 401]:
            return JSONResponse(status_code=401, content={"error": {"code": 2001}})
        if len(coords) == 2 and coords[0] == [0, 0] and coords[1] == [0, 403]:
            # Real client behavior: on 403 it retries once with the
            # driving-car profile at the SAME coordinates — this sentinel
            # returns 403 regardless of profile, reproducing the real
            # "both profiles forbidden" scenario without a mock.
            return JSONResponse(status_code=403, content={"error": {"code": 2010}})
        if len(coords) == 2 and coords[0] == [0, 0] and coords[1] == [0, 999]:
            return JSONResponse(
                {
                    "features": [
                        {
                            "properties": {
                                "summary": {"distance": 100000, "duration": 4800},
                                "ascent": 5000.0,
                                "descent": 0.0,
                                "extras": {
                                    "waycategory": {"values": [[0, 1, 1]]},
                                    "waytype": {"values": [[0, 1, 1]]},
                                    "steepness": {"values": [[0, 1, 1]]},
                                },
                            },
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[28.0, 41.0, 0], [32.0, 39.0, 0]],
                            },
                        }
                    ]
                }
            )
        # Multi-segment scenario (0,0)->(0,777): 11-point geometry split into
        # a motorway leg (waycategory 1) and a secondary leg (waycategory 3)
        # so RouteAnalyzer.analyze_segments has real segment-range data to
        # classify instead of a single flat leg.
        if len(coords) == 2 and coords[0] == [0, 0] and coords[1] == [0, 777]:
            return JSONResponse(
                {
                    "features": [
                        {
                            "properties": {
                                "summary": {"distance": 100000, "duration": 3600},
                                "ascent": 500,
                                "descent": 500,
                                "extras": {
                                    "waycategory": {
                                        "values": [[0, 5, 1], [5, 10, 4]],
                                    },
                                    "steepness": {
                                        "values": [
                                            [0, 3, 0],
                                            [3, 5, 2],
                                            [5, 8, 0],
                                            [8, 10, -2],
                                        ],
                                    },
                                },
                            },
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [29.0 + i * 0.01, 40.0 - i * 0.01, 0]
                                    for i in range(11)
                                ],
                            },
                        }
                    ]
                }
            )
    except Exception:
        pass

    return JSONResponse(
        {
            "features": [
                {
                    "properties": {
                        "summary": {"distance": 100000, "duration": 4800},
                        "ascent": 300.0,
                        "descent": 280.0,
                        "extras": {
                            "waycategory": {"values": [[0, 1, 1]]},
                            "waytype": {"values": [[0, 1, 1]]},
                            "steepness": {"values": [[0, 1, 0]]},
                        },
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[28.0, 41.0, 0], [32.0, 39.0, 0]],
                    },
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# OpenRoute Geocode — lives at the host root, not under /v2 (see
# OpenRouteClient.geocode_url derivation).
# ---------------------------------------------------------------------------
@app.get("/geocode/search")
async def openroute_geocode(request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    text = request.query_params.get("text", "")
    # Sentinel-text scenarios — geocode's query params are a fixed dict
    # (text/size/boundary.country), so the search text itself carries the
    # scenario when a test needs one (real HTTP behavior, not a mock).
    if text == "__EMPTY__":
        return JSONResponse({"features": []})
    if text == "__ERROR401__":
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    if text == "__MULTI_ONE_BAD__":
        return JSONResponse(
            {
                "features": [
                    {"geometry": {"coordinates": []}, "properties": {"label": "Bad"}},
                    {
                        "geometry": {"coordinates": [29.0, 41.0]},
                        "properties": {"name": "Istanbul"},
                    },
                ]
            }
        )
    return JSONResponse(
        {
            "features": [
                {
                    "geometry": {"coordinates": [32.85, 39.93]},
                    "properties": {"label": text or "Ankara, Türkiye"},
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# Open-Meteo Elevation — OPEN_METEO_API_BASE_URL = "{host}/v1/elevation";
# client GETs the base_url directly (no suffix).
# ---------------------------------------------------------------------------
@app.get("/v1/elevation")
async def open_meteo_elevation(request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    lats = request.query_params.get("latitude", "")
    count = len([p for p in lats.split(",") if p]) if lats else 0
    # Deterministic gentle-hill profile: 300m base + 50m per point, capped.
    elevations = [300.0 + min(i * 50.0, 400.0) for i in range(count)]
    return JSONResponse({"elevation": elevations})


# ---------------------------------------------------------------------------
# Telegram Bot API — TELEGRAM_API_BASE_URL = "{host}"; client appends
# "/bot{token}/sendMessage".
# ---------------------------------------------------------------------------
@app.post("/bot{token}/sendMessage")
async def telegram_send_message(token: str, request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    body = await request.json()
    return JSONResponse(
        {
            "ok": True,
            "result": {
                "message_id": 1,
                "chat": {"id": body.get("chat_id", 0)},
                "text": body.get("text", ""),
                "date": 0,
            },
        }
    )


# ---------------------------------------------------------------------------
# Groq / OpenAI-compatible — GROQ_API_BASE_URL = "{host}/openai/v1"; SDK
# appends "/chat/completions".
# ---------------------------------------------------------------------------
@app.post("/openai/v1/chat/completions")
async def groq_chat_completions(request: Request):
    sim = await _maybe_simulate(request)
    if sim is not None:
        return sim

    return JSONResponse(
        {
            "id": "chatcmpl-stub",
            "object": "chat.completion",
            "created": 0,
            "model": "llama-3.3-70b-versatile",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Bu bir test yanıtıdır.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    )
