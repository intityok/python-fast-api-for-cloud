import hashlib
import re
import os
from typing import Dict
from urllib.parse import urlparse
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


class DigestAuth:
    """Digest authentication helper"""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @staticmethod
    def md5(data: str) -> str:
        """Generate MD5 hash"""
        return hashlib.md5(data.encode()).hexdigest()

    @staticmethod
    def parse_digest_challenge(www_authenticate: str) -> Dict[str, str]:
        """Parse WWW-Authenticate digest challenge"""
        params = {}
        pattern = r'(\w+)="([^"]+)"'
        matches = re.findall(pattern, www_authenticate)
        for key, value in matches:
            params[key] = value

        # Handle qop without quotes
        qop_match = re.search(r'qop=([^,\s]+)', www_authenticate)
        if qop_match and 'qop' not in params:
            params['qop'] = qop_match.group(1)

        return params

    def build_digest_header(self, method: str, uri: str, www_authenticate: str) -> str:
        """Build digest authorization header"""
        params = self.parse_digest_challenge(www_authenticate)

        realm = params.get('realm', '')
        nonce = params.get('nonce', '')
        qop = params.get('qop', 'auth')
        opaque = params.get('opaque', '')

        # Generate client nonce
        import random
        nc = "00000001"
        cnonce = self.md5(str(random.random() * 1e9))[:16]

        # Calculate response
        ha1 = self.md5(f"{self.username}:{realm}:{self.password}")
        ha2 = self.md5(f"{method}:{uri}")
        response = self.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")

        # Build authorization header
        auth_header = (
            f'Digest username="{self.username}", '
            f'realm="{realm}", '
            f'nonce="{nonce}", '
            f'uri="{uri}", '
            f'qop={qop}, '
            f'nc={nc}, '
            f'cnonce="{cnonce}", '
            f'response="{response}", '
            f'opaque="{opaque}"'
        )

        return auth_header


async def fetch_with_digest_auth(url: str, username: str, password: str) -> Dict:
    """Fetch data with digest authentication"""
    async with httpx.AsyncClient(verify=False) as client:
        # Step 1: Initial request to get digest challenge
        response = await client.get(url)

        if response.status_code != 401:
            raise HTTPException(status_code=500, detail="Expected 401 challenge from server")

        www_authenticate = response.headers.get("www-authenticate", "")
        if not www_authenticate:
            raise HTTPException(status_code=500, detail="No WWW-Authenticate header received")

        # Step 2: Build digest auth header and retry
        parsed_url = urlparse(url)
        uri = parsed_url.path
        if parsed_url.query:
            uri += f"?{parsed_url.query}"

        digest_auth = DigestAuth(username, password)
        auth_header = digest_auth.build_digest_header("GET", uri, www_authenticate)

        # Make authenticated request
        response = await client.get(url, headers={"Authorization": auth_header})

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch data: {response.text}")

        return parse_nvr_response(response.text)


def parse_nvr_response(text: str) -> Dict:
    """Parse NVR key=value format response into JSON"""
    lines = text.split('\n')
    result = {}

    for line in lines:
        line = line.strip()
        if '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()

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
