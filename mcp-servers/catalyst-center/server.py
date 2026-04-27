"""
MCP Server — Cisco Catalyst Center
Integração real com Cisco Catalyst Center via REST API.

Ferramentas disponíveis:
  - catalyst_fetch_devices      : Lista dispositivos de rede (switches, roteadores, APs)
  - catalyst_fetch_sites        : Hierarquia de sites (área, building, andar)
  - catalyst_fetch_interfaces   : Interfaces de um dispositivo específico
  - catalyst_get_clients_list   : Clientes conectados à rede
  - catalyst_get_client_by_mac  : Detalhes de um cliente pelo MAC address
  - catalyst_get_clients_count  : Contagem de clientes conectados
  - catalyst_get_network_health : Saúde geral da rede por categoria

Autenticação: POST /dna/system/api/v1/auth/token (HTTP Basic) → Token renovado automaticamente.
Fallback automático para mock quando CATALYST_CENTER_HOST não configurado.
"""
import os
import time
import base64
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from tenacity import (
    retry, stop_after_attempt, wait_fixed,
    retry_if_exception_type, before_sleep_log,
)

# ─── Configuração ─────────────────────────────────────────────────────────────

# Aceita tanto CATALYST_CENTER_* (padrão deste projeto) quanto CCC_* (richbibby/catalyst-center-mcp)
CCC_HOST     = (os.getenv("CATALYST_CENTER_HOST") or os.getenv("CCC_HOST", "")).rstrip("/")
CCC_USER     = os.getenv("CATALYST_CENTER_USER") or os.getenv("CCC_USER", "")
CCC_PASSWORD = os.getenv("CATALYST_CENTER_PASSWORD") or os.getenv("CCC_PWD", "")
CCC_TIMEOUT  = int(os.getenv("CATALYST_CENTER_TIMEOUT", "15"))
SSL_VERIFY   = os.getenv("SSL_VERIFY", "true").lower() != "false"

MOCK_MODE = not bool(CCC_HOST)

log = logging.getLogger("mcp-catalyst")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ─── Cliente Catalyst Center ──────────────────────────────────────────────────

class CatalystCenterClient:
    """
    Cliente HTTP assíncrono para a REST API do Cisco Catalyst Center.
    Gerencia token de autenticação com renovação automática.
    O token expira em ~60 min — renovamos após 50 min por segurança.
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_created: float = 0.0
        self._token_ttl: int = 3000  # 50 min em segundos
        self._client = httpx.AsyncClient(
            timeout=CCC_TIMEOUT,
            verify=SSL_VERIFY,
            headers={"Content-Type": "application/json"},
        )

    async def _ensure_token(self) -> str:
        now = time.time()
        if self._token and (now - self._token_created) < self._token_ttl:
            return self._token

        log.info("catalyst.auth: obtendo novo token")
        creds = base64.b64encode(f"{CCC_USER}:{CCC_PASSWORD}".encode()).decode()
        resp = await self._client.post(
            f"{CCC_HOST}/dna/system/api/v1/auth/token",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        self._token = resp.json()["Token"]
        self._token_created = now
        log.info("catalyst.auth: token obtido com sucesso")
        return self._token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.HTTPError),
        before_sleep=before_sleep_log(log, logging.WARNING),
    )
    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        token = await self._ensure_token()
        t0 = time.monotonic()
        resp = await self._client.get(
            f"{CCC_HOST}{path}",
            headers={"X-Auth-Token": token, "Content-Type": "application/json"},
            params=params or {},
        )
        latency_ms = (time.monotonic() - t0) * 1000
        log.info(f"catalyst.get path={path} latency={latency_ms:.0f}ms status={resp.status_code}")

        # Token expirado durante a chamada — limpar e retentar
        if resp.status_code == 401:
            self._token = None
            resp.raise_for_status()

        resp.raise_for_status()
        return resp.json()

    async def get_device_count(self) -> int:
        data = await self.get("/dna/intent/api/v1/network-device/count")
        return int(data.get("response", 0))

    async def close(self):
        await self._client.aclose()


_catalyst = CatalystCenterClient()


# ─── App ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MOCK_MODE:
        try:
            count = await _catalyst.get_device_count()
            log.info(f"catalyst.startup: conectado — {count} dispositivos gerenciados")
        except Exception as e:
            log.warning(f"catalyst.startup: aviso — não foi possível verificar conexão: {e}")
    else:
        log.info("catalyst.startup: modo MOCK ativo (CATALYST_CENTER_HOST não configurado)")
    yield
    await _catalyst.close()


app = FastAPI(title="MCP Cisco Catalyst Center", version="1.0.0", lifespan=lifespan)


# ─── Tool: fetch_devices ──────────────────────────────────────────────────────

class FetchDevicesInput(BaseModel):
    hostname: Optional[str] = None
    family: Optional[str] = None          # "Switches and Hubs" | "Routers" | "Wireless Controller"
    management_ip: Optional[str] = None
    reachability_status: Optional[str] = None   # "Reachable" | "Unreachable"
    limit: int = 50


@app.post("/tools/catalyst_fetch_devices")
async def fetch_devices(body: FetchDevicesInput):
    """
    Lista dispositivos de rede gerenciados pelo Catalyst Center.
    Filtre por hostname, família (Switches, Routers, Wireless), IP ou status de acessibilidade.
    """
    if MOCK_MODE:
        return _mock_devices(body.family, body.reachability_status)

    try:
        params: dict = {"limit": body.limit, "offset": 1}
        if body.hostname:
            params["hostname"] = body.hostname
        if body.family:
            params["family"] = body.family
        if body.management_ip:
            params["managementIpAddress"] = body.management_ip
        if body.reachability_status:
            params["reachabilityStatus"] = body.reachability_status

        data = await _catalyst.get("/dna/intent/api/v1/network-device", params)
        devices = data.get("response", [])

        result = []
        for d in devices:
            result.append({
                "id":                    d.get("id"),
                "hostname":              d.get("hostname"),
                "managementIpAddress":   d.get("managementIpAddress"),
                "platformId":            d.get("platformId"),
                "family":                d.get("family"),
                "series":                d.get("series"),
                "softwareVersion":       d.get("softwareVersion"),
                "reachabilityStatus":    d.get("reachabilityStatus"),
                "reachabilityFailureReason": d.get("reachabilityFailureReason"),
                "role":                  d.get("role"),
                "upTime":                d.get("upTime"),
                "lastUpdated":           d.get("lastUpdated"),
                "serialNumber":          d.get("serialNumber"),
                "locationName":          d.get("locationName"),
                "errorCode":             d.get("errorCode"),
                "errorDescription":      d.get("errorDescription"),
            })

        unreachable = sum(1 for d in result if d["reachabilityStatus"] == "Unreachable")
        return {
            "count": len(result),
            "unreachable_count": unreachable,
            "devices": result,
        }
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_fetch_devices"}


# ─── Tool: fetch_sites ────────────────────────────────────────────────────────

class FetchSitesInput(BaseModel):
    name: Optional[str] = None   # filtro parcial por nome

@app.post("/tools/catalyst_fetch_sites")
async def fetch_sites(body: FetchSitesInput):
    """
    Lista a hierarquia de sites do Catalyst Center (Global > Área > Building > Andar).
    Útil para entender a topologia lógica da rede.
    """
    if MOCK_MODE:
        return _mock_sites()

    try:
        params: dict = {}
        if body.name:
            params["name"] = body.name

        data = await _catalyst.get("/dna/intent/api/v1/site", params)
        sites = data.get("response", [])

        result = []
        for s in sites:
            additional = s.get("additionalInfo", [])
            site_type = None
            for info in additional:
                if info.get("nameSpace") == "Location":
                    site_type = info.get("attributes", {}).get("type")
                    break

            result.append({
                "id":            s.get("id"),
                "name":          s.get("name"),
                "siteHierarchy": s.get("siteHierarchy"),
                "siteType":      site_type,
                "parentId":      s.get("parentId"),
            })

        return {"count": len(result), "sites": result}
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_fetch_sites"}


# ─── Tool: fetch_interfaces ───────────────────────────────────────────────────

class FetchInterfacesInput(BaseModel):
    device_id: Optional[str] = None    # ID interno do Catalyst Center
    hostname: Optional[str] = None     # Resolvido para device_id se não informado


@app.post("/tools/catalyst_fetch_interfaces")
async def fetch_interfaces(body: FetchInterfacesInput):
    """
    Busca interfaces de um dispositivo de rede.
    Informe device_id (ID do Catalyst Center) ou hostname para resolução automática.
    Retorna status, velocidade, VLAN, IP e descrição de cada interface.
    """
    if MOCK_MODE:
        return _mock_interfaces(body.hostname or body.device_id or "sw-mock-01")

    try:
        device_id = body.device_id
        hostname_used = body.hostname

        if not device_id and body.hostname:
            data = await _catalyst.get("/dna/intent/api/v1/network-device",
                                       {"hostname": body.hostname})
            devices = data.get("response", [])
            if not devices:
                return {"error": f"Dispositivo não encontrado: {body.hostname}"}
            device_id = devices[0]["id"]
            hostname_used = devices[0].get("hostname", body.hostname)

        if not device_id:
            return {"error": "Informe device_id ou hostname"}

        data = await _catalyst.get(f"/dna/intent/api/v1/interface/network-device/{device_id}")
        interfaces = data.get("response", [])

        result = []
        for iface in interfaces:
            result.append({
                "portName":          iface.get("portName"),
                "status":            iface.get("status"),
                "adminStatus":       iface.get("adminStatus"),
                "operationalStatus": iface.get("operationalStatus"),
                "interfaceType":     iface.get("interfaceType"),
                "speed":             iface.get("speed"),
                "duplex":            iface.get("duplex"),
                "ipv4Address":       iface.get("ipv4Address"),
                "ipv4Mask":          iface.get("ipv4Mask"),
                "macAddress":        iface.get("macAddress"),
                "vlanId":            iface.get("vlanId"),
                "voiceVlan":         iface.get("voiceVlan"),
                "description":       iface.get("description"),
                "mediaType":         iface.get("mediaType"),
            })

        down_count = sum(1 for i in result if i.get("operationalStatus") == "DOWN"
                         and i.get("adminStatus") == "UP")
        return {
            "count": len(result),
            "down_admin_up_count": down_count,
            "device_id": device_id,
            "hostname": hostname_used,
            "interfaces": result,
        }
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_fetch_interfaces"}


# ─── Tool: get_clients_list ───────────────────────────────────────────────────

class GetClientsListInput(BaseModel):
    start_time: Optional[int] = None         # epoch ms; padrão: 5 min atrás
    end_time: Optional[int] = None           # epoch ms; padrão: agora
    limit: int = 50
    connection_status: Optional[str] = None  # "CONNECTED" | "DISCONNECTED"
    host_type: Optional[str] = None          # "WIRELESS" | "WIRED"


@app.post("/tools/catalyst_get_clients_list")
async def get_clients_list(body: GetClientsListInput):
    """
    Lista clientes conectados à rede (dispositivos finais — PCs, phones, IoT, etc.).
    Filtre por tipo de conexão (wireless/wired) ou status.
    """
    if MOCK_MODE:
        return _mock_clients()

    try:
        now_ms = int(time.time() * 1000)
        params: dict = {
            "startTime": body.start_time or (now_ms - 5 * 60 * 1000),
            "endTime":   body.end_time or now_ms,
        }

        data = await _catalyst.get("/dna/intent/api/v1/client/detail", params)
        response = data.get("response", {})

        # API retorna dict com listas por tipo
        clients_raw: list = []
        if isinstance(response, list):
            clients_raw = response
        elif isinstance(response, dict):
            # Formato alternativo: {CLIENT_LIST: [...]}
            for v in response.values():
                if isinstance(v, list):
                    clients_raw.extend(v)

        result = []
        for c in clients_raw:
            if body.connection_status and c.get("connectionStatus") != body.connection_status:
                continue
            if body.host_type and c.get("hostType") != body.host_type:
                continue
            result.append({
                "hostName":         c.get("hostName"),
                "hostOs":           c.get("hostOs"),
                "hostType":         c.get("hostType"),
                "hostMac":          c.get("hostMac"),
                "ipv4":             c.get("hostIpV4"),
                "vlanId":           c.get("vlanId"),
                "ssid":             c.get("ssid"),
                "frequency":        c.get("frequency"),
                "channel":          c.get("channel"),
                "connectedDevice":  c.get("clientConnection"),
                "connectionStatus": c.get("connectionStatus"),
                "healthScore":      c.get("healthScore"),
                "rssi":             c.get("rssi"),
                "snr":              c.get("snr"),
                "location":         c.get("location"),
            })
            if len(result) >= body.limit:
                break

        return {"count": len(result), "clients": result}
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_get_clients_list"}


# ─── Tool: get_client_by_mac ─────────────────────────────────────────────────

class GetClientByMacInput(BaseModel):
    mac_address: str   # formato: xx:xx:xx:xx:xx:xx


@app.post("/tools/catalyst_get_client_by_mac")
async def get_client_by_mac(body: GetClientByMacInput):
    """
    Busca detalhes completos de um dispositivo cliente pelo MAC address.
    Retorna localização na rede, SSID, saúde, sinal, switch/AP conectado, etc.
    """
    if MOCK_MODE:
        return _mock_client_detail(body.mac_address)

    try:
        now_ms = int(time.time() * 1000)
        data = await _catalyst.get("/dna/intent/api/v1/client/detail", {
            "timestamp":  now_ms,
            "macAddress": body.mac_address,
        })
        detail = data.get("detail", data.get("response", {}))
        topology = data.get("topology", {})

        return {
            "mac_address": body.mac_address,
            "detail":      detail,
            "topology":    topology,
        }
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_get_client_by_mac"}


# ─── Tool: get_clients_count ─────────────────────────────────────────────────

class GetClientsCountInput(BaseModel):
    start_time: Optional[int] = None   # epoch ms
    end_time: Optional[int] = None     # epoch ms


@app.post("/tools/catalyst_get_clients_count")
async def get_clients_count(body: GetClientsCountInput):
    """
    Retorna o total de clientes conectados à rede no período especificado.
    """
    if MOCK_MODE:
        return {"total_clients": 47, "mode": "mock"}

    try:
        now_ms = int(time.time() * 1000)
        data = await _catalyst.get("/dna/intent/api/v1/client/count", {
            "startTime": body.start_time or (now_ms - 5 * 60 * 1000),
            "endTime":   body.end_time or now_ms,
        })
        return {"total_clients": data.get("response", 0)}
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_get_clients_count"}


# ─── Tool: get_network_health ─────────────────────────────────────────────────

class GetNetworkHealthInput(BaseModel):
    epoch_time: Optional[int] = None   # epoch ms; padrão: agora


@app.post("/tools/catalyst_get_network_health")
async def get_network_health(body: GetNetworkHealthInput):
    """
    Retorna o score de saúde geral da rede por categoria de dispositivo
    (Switches, Roteadores, APs, Clientes).
    Fundamental para triagem rápida: identifica categorias com problemas.
    """
    if MOCK_MODE:
        return _mock_network_health()

    try:
        now_ms = int(time.time() * 1000)
        data = await _catalyst.get("/dna/intent/api/v1/network-health", {
            "timestamp": body.epoch_time or now_ms,
        })
        health_list = data.get("response", [])

        # Normalizar e calcular resumo
        categories = []
        for h in health_list:
            total = h.get("totalCount", 0)
            good  = h.get("goodCount", 0)
            bad   = h.get("badCount", 0)
            fair  = h.get("fairCount", 0)
            categories.append({
                "category":    h.get("category"),
                "totalCount":  total,
                "goodCount":   good,
                "badCount":    bad,
                "fairCount":   fair,
                "noDataCount": h.get("noDataCount", 0),
                "healthScore": h.get("healthScore"),
                "status": "CRITICAL" if bad > 0 else "WARNING" if fair > 0 else "OK",
            })

        overall_score = None
        if categories:
            scores = [c["healthScore"] for c in categories if c["healthScore"] is not None]
            overall_score = round(sum(scores) / len(scores), 1) if scores else None

        return {
            "overall_health_score": overall_score,
            "categories": categories,
            "measured_at": data.get("measuredBy"),
        }
    except Exception as e:
        return {"error": str(e), "tool": "catalyst_get_network_health"}


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    if MOCK_MODE:
        return {
            "status":  "ok",
            "mode":    "mock",
            "message": "Configure CATALYST_CENTER_HOST para modo real",
        }
    try:
        t0 = time.monotonic()
        count = await _catalyst.get_device_count()
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "status":     "ok",
            "mode":       "real",
            "host":       CCC_HOST,
            "devices":    count,
            "latency_ms": round(latency_ms, 1),
        }
    except Exception as e:
        return {"status": "down", "error": str(e), "mode": "real"}


# ─── Mock data ────────────────────────────────────────────────────────────────

def _mock_devices(family: Optional[str] = None, reachability: Optional[str] = None):
    devices = [
        {
            "id": "mock-sw-01", "hostname": "C9300-CORE-01",
            "managementIpAddress": "10.1.0.1", "platformId": "C9300-48P",
            "family": "Switches and Hubs", "series": "Cisco Catalyst 9300 Series Switches",
            "softwareVersion": "17.9.4", "reachabilityStatus": "Reachable",
            "role": "ACCESS", "upTime": "120 days, 3:45:12.00", "locationName": "HQ/Floor1",
        },
        {
            "id": "mock-sw-02", "hostname": "C9300-DIST-01",
            "managementIpAddress": "10.1.0.4", "platformId": "C9300-48UXM",
            "family": "Switches and Hubs", "series": "Cisco Catalyst 9300 Series Switches",
            "softwareVersion": "17.9.4", "reachabilityStatus": "Unreachable",
            "reachabilityFailureReason": "SNMP timeout",
            "role": "DISTRIBUTION", "upTime": None, "locationName": "HQ/Floor2",
        },
        {
            "id": "mock-rt-01", "hostname": "ISR4351-WAN-01",
            "managementIpAddress": "10.1.0.2", "platformId": "ISR4351",
            "family": "Routers", "series": "Cisco ISR 4000 Series",
            "softwareVersion": "17.6.5", "reachabilityStatus": "Reachable",
            "role": "BORDER ROUTER", "upTime": "365 days, 0:00:01.00", "locationName": "HQ/Datacenter",
        },
        {
            "id": "mock-wlc-01", "hostname": "C9800-WLC-01",
            "managementIpAddress": "10.1.0.3", "platformId": "C9800-80",
            "family": "Wireless Controller", "series": "Cisco Catalyst 9800 Series",
            "softwareVersion": "17.9.4", "reachabilityStatus": "Reachable",
            "role": "ACCESS", "upTime": "45 days, 12:00:00.00", "locationName": "HQ/Floor1",
        },
    ]

    if family:
        devices = [d for d in devices if family.lower() in d["family"].lower()]
    if reachability:
        devices = [d for d in devices if d["reachabilityStatus"] == reachability]

    unreachable = sum(1 for d in devices if d["reachabilityStatus"] == "Unreachable")
    return {"count": len(devices), "unreachable_count": unreachable, "devices": devices}


def _mock_sites():
    return {
        "count": 5,
        "sites": [
            {"id": "site-1", "name": "Global",      "siteHierarchy": "Global",               "siteType": "area"},
            {"id": "site-2", "name": "HQ",           "siteHierarchy": "Global/HQ",            "siteType": "area"},
            {"id": "site-3", "name": "Datacenter",   "siteHierarchy": "Global/HQ/Datacenter", "siteType": "building"},
            {"id": "site-4", "name": "Floor1",       "siteHierarchy": "Global/HQ/Floor1",     "siteType": "floor"},
            {"id": "site-5", "name": "Branch-SP",    "siteHierarchy": "Global/Branch-SP",     "siteType": "area"},
        ],
    }


def _mock_interfaces(device: str):
    return {
        "count": 4,
        "device_id": device,
        "hostname": device,
        "down_admin_up_count": 1,
        "interfaces": [
            {
                "portName": "GigabitEthernet1/0/1", "status": "connected",
                "adminStatus": "UP", "operationalStatus": "UP",
                "speed": "1000000", "duplex": "FullDuplex",
                "vlanId": "10", "description": "Uplink to Distribution",
            },
            {
                "portName": "GigabitEthernet1/0/2", "status": "notconnect",
                "adminStatus": "UP", "operationalStatus": "DOWN",
                "speed": "1000000", "duplex": "Auto",
                "description": "PC-john",
            },
            {
                "portName": "GigabitEthernet1/0/24", "status": "connected",
                "adminStatus": "UP", "operationalStatus": "UP",
                "speed": "1000000", "duplex": "FullDuplex",
                "vlanId": "20", "description": "AP-Floor1-01",
            },
            {
                "portName": "Vlan10", "status": "connected",
                "adminStatus": "UP", "operationalStatus": "UP",
                "interfaceType": "Virtual",
                "ipv4Address": "192.168.10.1", "ipv4Mask": "255.255.255.0",
            },
        ],
    }


def _mock_clients():
    return {
        "count": 4,
        "clients": [
            {
                "hostName": "workstation-01", "hostOs": "Windows 11", "hostType": "WIRELESS",
                "hostMac": "aa:bb:cc:dd:ee:01", "ipv4": "192.168.10.101",
                "ssid": "CORP_WIFI", "frequency": "5.0 GHz", "channel": "36",
                "healthScore": 8, "rssi": -55, "snr": 35,
                "connectedDevice": "C9800-WLC-01", "connectionStatus": "CONNECTED",
            },
            {
                "hostName": "laptop-maria", "hostOs": "macOS", "hostType": "WIRELESS",
                "hostMac": "aa:bb:cc:dd:ee:02", "ipv4": "192.168.10.102",
                "ssid": "CORP_WIFI", "frequency": "5.0 GHz", "channel": "36",
                "healthScore": 6, "rssi": -72, "snr": 18,
                "connectedDevice": "C9800-WLC-01", "connectionStatus": "CONNECTED",
            },
            {
                "hostName": "printer-floor1", "hostType": "WIRED",
                "hostMac": "aa:bb:cc:dd:ee:03", "ipv4": "192.168.20.10",
                "vlanId": "20", "healthScore": 10,
                "connectedDevice": "C9300-CORE-01", "connectionStatus": "CONNECTED",
            },
            {
                "hostName": "voip-phone-john", "hostOs": "Cisco IP Phone", "hostType": "WIRED",
                "hostMac": "aa:bb:cc:dd:ee:04", "ipv4": "192.168.30.5",
                "vlanId": "30", "healthScore": 9,
                "connectedDevice": "C9300-CORE-01", "connectionStatus": "CONNECTED",
            },
        ],
    }


def _mock_client_detail(mac: str):
    return {
        "mac_address": mac,
        "detail": {
            "hostName": "workstation-mock",
            "hostOs": "Windows 11",
            "hostType": "WIRELESS",
            "hostMac": mac,
            "hostIpV4": "192.168.10.99",
            "ssid": "CORP_WIFI",
            "frequency": "5.0 GHz",
            "channel": "36",
            "connectionStatus": "CONNECTED",
            "healthScore": 7,
            "rssi": -62,
            "snr": 28,
            "clientConnection": "C9800-WLC-01",
            "location": "Global/HQ/Floor1",
            "vlanId": "10",
        },
        "topology": {},
    }


def _mock_network_health():
    return {
        "overall_health_score": 91.5,
        "categories": [
            {
                "category": "Switches and Hubs", "totalCount": 15, "goodCount": 13,
                "badCount": 1, "fairCount": 1, "noDataCount": 0,
                "healthScore": 87, "status": "CRITICAL",
            },
            {
                "category": "Routers", "totalCount": 4, "goodCount": 4,
                "badCount": 0, "fairCount": 0, "noDataCount": 0,
                "healthScore": 100, "status": "OK",
            },
            {
                "category": "Wireless", "totalCount": 8, "goodCount": 7,
                "badCount": 0, "fairCount": 1, "noDataCount": 0,
                "healthScore": 93, "status": "WARNING",
            },
            {
                "category": "AP", "totalCount": 24, "goodCount": 22,
                "badCount": 0, "fairCount": 2, "noDataCount": 0,
                "healthScore": 96, "status": "WARNING",
            },
        ],
        "measured_at": "MOCK",
    }
