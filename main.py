import os
import re
from typing import Dict
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Data Adaptor API", description="API middleware for Grafana to fetch data from DSM, Mikrotik, and NVR")

# Configuration from environment variables
DSM_URL = os.getenv("DSM_URL", "https://drive.int.in.th")
DSM_USER = os.getenv("DSM_USER", "korkarn")
DSM_PASS = os.getenv("DSM_PASS", "INTit2025!")

MIKROTIK_2011_URL = os.getenv("MIKROTIK_2011_URL", "https://rb2011.int.in.th")
MIKROTIK_4011_URL = os.getenv("MIKROTIK_4011_URL", "https://rb4011.int.in.th")
MIKROTIK_USER = os.getenv("MIKROTIK_USER", "grafana")
MIKROTIK_PASS = os.getenv("MIKROTIK_PASS", "INTit2025!")

NVR_URL = os.getenv("NVR_URL", "http://int.in.th:37080")
NVR_USER = os.getenv("NVR_USER", "grafana")
NVR_PASS = os.getenv("NVR_PASS", "INTit2025!")


async def fetch_with_digest_auth(url: str, username: str, password: str) -> Dict:
    """Fetch data with digest authentication using httpx built-in DigestAuth"""
    async with httpx.AsyncClient(verify=False) as client:
        # httpx handles digest auth automatically!
        auth = httpx.DigestAuth(username, password)
        response = await client.get(url, auth=auth)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch data: {response.text}")

        return parse_nvr_response(response.text)


def parse_nvr_response(text: str) -> Dict:
    """Parse NVR key=value format response into nested JSON"""
    lines = text.split('\n')
    result = {}

    for line in lines:
        line = line.strip()
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()

            # Split the key by dots to create nested structure
            parts = key.split('.')
            current = result

            for i, part in enumerate(parts):
                # Check if this part has array notation like "AlarmOutChannels[0]"
                if '[' in part and ']' in part:
                    # Split into base name and indices (handle multiple like [0][1])
                    base = part[:part.index('[')]
                    indices_str = part[part.index('['):]

                    # Extract all array indices
                    indices = [int(idx) for idx in re.findall(r'\[(\d+)\]', indices_str)]

                    # Create the base array if it doesn't exist
                    if base not in current:
                        current[base] = []

                    # Navigate through nested arrays
                    temp = current[base]
                    for idx_pos, idx in enumerate(indices[:-1]):
                        # Ensure array is large enough
                        while len(temp) <= idx:
                            temp.append([])
                        if not isinstance(temp[idx], list):
                            temp[idx] = []
                        temp = temp[idx]

                    # Handle the last index
                    last_idx = indices[-1]
                    while len(temp) <= last_idx:
                        temp.append({} if i < len(parts) - 1 else None)

                    # If this is the last part, set the value
                    if i == len(parts) - 1:
                        temp[last_idx] = value
                    else:
                        # Navigate to the array element for further nesting
                        if not isinstance(temp[last_idx], dict):
                            temp[last_idx] = {}
                        current = temp[last_idx]
                else:
                    # Regular key (no array notation)
                    if i == len(parts) - 1:
                        # Last part - set the value
                        current[part] = value
                    else:
                        # Not the last part - create nested dict if needed
                        if part not in current:
                            current[part] = {}
                        elif not isinstance(current[part], dict):
                            # If it exists but isn't a dict, convert it
                            current[part] = {}
                        current = current[part]

    return result


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Data Adaptor API",
        "endpoints": [
            "/dsmwatchdog",
            "/2011watchdog",
            "/4011watchdog",
            "/nvrsummary",
            "/nvrslowspace",
            "/nvrhddfail",
            "/nvrhddexist",
            "/nvrrecordstatus"
        ]
    }


@app.get("/dsmwatchdog")
async def dsm_watchdog():
    """Get DSM system utilization data"""
    async with httpx.AsyncClient(verify=False) as client:
        # Step 1: Login to get session token
        login_url = f"{DSM_URL}/webapi/auth.cgi"
        login_params = {
            "api": "SYNO.API.Auth",
            "method": "login",
            "version": "6",
            "account": DSM_USER,
            "passwd": DSM_PASS,
            "session": "Core",
            "format": "cookie"
        }

        try:
            login_response = await client.get(login_url, params=login_params)
            login_data = login_response.json()

            if not login_data.get("success"):
                raise HTTPException(status_code=401, detail="DSM login failed")

            # Extract session ID
            sid = login_data["data"]["sid"]

            # Step 2: Get system utilization with session cookie
            util_url = f"{DSM_URL}/webapi/entry.cgi"
            util_params = {
                "api": "SYNO.Core.System.Utilization",
                "method": "get",
                "version": "1"
            }

            headers = {"Cookie": f"id={sid}"}
            util_response = await client.get(util_url, params=util_params, headers=headers)
            util_data = util_response.json()

            return JSONResponse(content=util_data)

        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.get("/2011watchdog")
async def mikrotik_2011_watchdog():
    """Get Mikrotik RB2011 system resource data"""
    async with httpx.AsyncClient(verify=False) as client:
        try:
            url = f"{MIKROTIK_2011_URL}/rest/system/resource"
            auth = (MIKROTIK_USER, MIKROTIK_PASS)

            response = await client.get(url, auth=auth)

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch Mikrotik data")

            return JSONResponse(content=response.json())

        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.get("/4011watchdog")
async def mikrotik_4011_watchdog():
    """Get Mikrotik RB4011 system resource data"""
    async with httpx.AsyncClient(verify=False) as client:
        try:
            url = f"{MIKROTIK_4011_URL}/rest/system/resource"
            auth = (MIKROTIK_USER, MIKROTIK_PASS)

            response = await client.get(url, auth=auth)

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch Mikrotik data")

            return JSONResponse(content=response.json())

        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.get("/nvrsummary")
async def nvr_summary():
    """Get NVR system info"""
    url = f"{NVR_URL}/cgi-bin/magicBox.cgi?action=getSystemInfo"
    return await fetch_with_digest_auth(url, NVR_USER, NVR_PASS)


@app.get("/nvrslowspace")
async def nvr_slow_space():
    """Get NVR low space configuration"""
    url = f"{NVR_URL}/cgi-bin/configManager.cgi?action=getConfig&name=StorageLowSpace"
    return await fetch_with_digest_auth(url, NVR_USER, NVR_PASS)


@app.get("/nvrhddfail")
async def nvr_hdd_fail():
    """Get NVR storage failure configuration"""
    url = f"{NVR_URL}/cgi-bin/configManager.cgi?action=getConfig&name=StorageFailure"
    return await fetch_with_digest_auth(url, NVR_USER, NVR_PASS)


@app.get("/nvrhddexist")
async def nvr_health():
    """Get NVR storage health"""
    url = f"{NVR_URL}/cgi-bin/configManager.cgi?action=getConfig&name=StorageNotExist"
    return await fetch_with_digest_auth(url, NVR_USER, NVR_PASS)


@app.get("/nvrrecordstatus")
async def nvr_record_status():
    """Get NVR recording status"""
    url = f"{NVR_URL}/cgi-bin/configManager.cgi?action=getConfig&name=Encode"
    return await fetch_with_digest_auth(url, NVR_USER, NVR_PASS)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
