"""
AbejaVerde·EO — Módulo: copernicus_api
=======================================
Autenticación y descarga centralizada para Copernicus Data Space (CDSE)
y Copernicus Climate Data Store (CDS).

Todos los módulos de src/ingesta/ importan desde aquí:
    from src.ingesta.copernicus_api import CDSEClient, CDSClient

Servicios cubiertos:
    CDSE  — Copernicus Data Space Ecosystem
            Sentinel-2, Sentinel-1, Sentinel-3
            Procesamiento openEO en la nube
    CDS   — Copernicus Climate Data Store
            ERA5-Land, AgERA5

Credenciales en .env:
    CDSE_USER  — email registrado en dataspace.copernicus.eu
    CDSE_PASS  — contraseña CDSE
    CDS_KEY    — API key CDS (sin UID prefix)
"""

from __future__ import annotations

import os
import time
import zipfile
import logging
from pathlib import Path
from typing import Optional, Union
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
CDSE_STAC_URL  = "https://catalogue.dataspace.copernicus.eu/stac/search"
OPENEO_URL     = "https://openeo.dataspace.copernicus.eu"
CDS_URL        = "https://cds.climate.copernicus.eu/api"

TOKEN_EXPIRY_BUFFER = 60   # segundos antes de que expire — refrescar


# ── CLIENTE CDSE ──────────────────────────────────────────────────────────────

class CDSEClient:
    """
    Cliente para Copernicus Data Space Ecosystem.
    Gestiona autenticación OAuth2 y refresco automático de token.

    Uso:
        client = CDSEClient()
        client.autenticar()
        imagenes = client.buscar_imagenes(bbox, fecha_inicio, fecha_fin)
        df_ndvi  = client.calcular_ndvi_openeo(bbox, fecha_inicio, fecha_fin)
    """

    def __init__(
        self,
        usuario:    Optional[str] = None,
        contraseña: Optional[str] = None,
    ):
        self.usuario    = usuario    or os.getenv("CDSE_USER", "")
        self.contraseña = contraseña or os.getenv("CDSE_PASS", "")
        self._token:        Optional[str]   = None
        self._token_expira: Optional[float] = None
        self._conn_openeo                   = None

        if not self.usuario or not self.contraseña:
            logger.warning(
                "Credenciales CDSE no encontradas. "
                "Define CDSE_USER y CDSE_PASS en .env"
            )

    # ── Autenticación ─────────────────────────────────────────────────────────

    def autenticar(self) -> bool:
        """
        Obtiene token OAuth2. Retorna True si fue exitoso.
        El token se refresca automáticamente cuando está por vencer.
        """
        try:
            r = requests.post(
                CDSE_TOKEN_URL,
                data={
                    "client_id":  "cdse-public",
                    "grant_type": "password",
                    "username":   self.usuario,
                    "password":   self.contraseña,
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            self._token        = data["access_token"]
            expires_in         = data.get("expires_in", 600)
            self._token_expira = time.time() + expires_in
            logger.info("✅ Autenticado en Copernicus Data Space")
            return True
        except Exception as e:
            logger.error(f"❌ Error de autenticación CDSE: {e}")
            return False

    @property
    def token(self) -> Optional[str]:
        """Token válido — refresca si está por vencer."""
        if self._token is None:
            self.autenticar()
            return self._token
        if time.time() > (self._token_expira - TOKEN_EXPIRY_BUFFER):
            logger.debug("Token por vencer — refrescando...")
            self.autenticar()
        return self._token

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # ── Catálogo STAC ─────────────────────────────────────────────────────────

    def buscar_imagenes(
        self,
        bbox:           list[float],          # [lon_min, lat_min, lon_max, lat_max]
        fecha_inicio:   str,                   # "YYYY-MM-DD"
        fecha_fin:      str,
        coleccion:      str   = "SENTINEL-2",
        max_nubosidad:  float = 40.0,
        limite:         int   = 100,
    ) -> list[dict]:
        """
        Busca imágenes disponibles en el catálogo STAC de CDSE.

        Retorna lista de registros con: fecha, nubosidad, tile, id.
        """
        body = {
            "collections": [coleccion],
            "bbox":        bbox,
            "datetime":    f"{fecha_inicio}T00:00:00Z/{fecha_fin}T23:59:59Z",
            "limit":       limite,
        }
        try:
            r = requests.post(
                CDSE_STAC_URL,
                json    = body,
                headers = self.headers,
                timeout = 60,
            )
            r.raise_for_status()
            features = r.json().get("features", [])

            # Filtrar por nubosidad en Python (el filtro query de la API es inestable)
            features = [
                f for f in features
                if f["properties"].get("eo:cloud_cover", 100) < max_nubosidad
            ]

            registros = [
                {
                    "fecha":      p.get("datetime", "")[:10],
                    "nubosidad":  round(p.get("eo:cloud_cover", 0), 1),
                    "tile":       p.get("s2:mgrs_tile", ""),
                    "id":         f.get("id", ""),
                }
                for f in features
                for p in [f["properties"]]
            ]
            logger.info(
                f"📡 {len(registros)} imágenes {coleccion} "
                f"({fecha_inicio} → {fecha_fin}, < {max_nubosidad}% nubes)"
            )
            return registros

        except requests.exceptions.Timeout:
            logger.warning("⏱️  Timeout catálogo STAC — reintenta más tarde")
            return []
        except Exception as e:
            logger.error(f"❌ Error catálogo STAC: {e}")
            return []

    # ── openEO ────────────────────────────────────────────────────────────────

    def _conectar_openeo(self):
        """Conecta y autentica en openEO CDSE (lazy initialization)."""
        if self._conn_openeo is not None:
            return self._conn_openeo
        try:
            import openeo
            conn = openeo.connect(OPENEO_URL)
            conn.authenticate_oidc_resource_owner_password_credentials(
                client_id  = "cdse-public",
                username   = self.usuario,
                password   = self.contraseña,
            )
            self._conn_openeo = conn
            logger.info("✅ Conectado a openEO CDSE")
            return conn
        except ImportError:
            raise ImportError("Instala openeo: pip install openeo")
        except Exception as e:
            raise RuntimeError(f"Error conexión openEO: {e}")

    def calcular_ndvi_openeo(
        self,
        bbox:          list[float],
        fecha_inicio:  str,
        fecha_fin:     str,
        max_nubosidad: float = 40.0,
    ) -> list[dict]:
        """
        Calcula serie temporal NDVI sobre el área dada usando openEO.
        Procesa en los servidores de Copernicus — no descarga imágenes.

        Retorna lista de {fecha, ndvi}.
        """
        from shapely.geometry import mapping, box as shapely_box

        conn = self._conectar_openeo()
        bbox_dict = {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
            "crs":  "EPSG:4326",
        }
        logger.info("🛰  Calculando NDVI en servidores Copernicus...")

        cubo = conn.load_collection(
            "SENTINEL2_L2A",
            spatial_extent  = bbox_dict,
            temporal_extent = [fecha_inicio, fecha_fin],
            bands           = ["B04", "B08"],
            max_cloud_cover = max_nubosidad,
        )
        b04  = cubo.band("B04")
        b08  = cubo.band("B08")
        ndvi = (b08 - b04) / (b08 + b04)

        poligono = mapping(shapely_box(*bbox))
        ndvi_ts  = ndvi.aggregate_spatial(geometries=poligono, reducer="mean")

        resultado = ndvi_ts.execute()
        return self._parsear_resultado_openeo(resultado, variable="ndvi")

    def calcular_sar_openeo(
        self,
        bbox:         list[float],
        fecha_inicio: str,
        fecha_fin:    str,
    ) -> list[dict]:
        """
        Calcula serie temporal SAR (ratio VH/VV) usando openEO.
        Sentinel-1 — funciona en días nublados.

        Retorna lista de {fecha, sar_ratio}.
        """
        from shapely.geometry import mapping, box as shapely_box

        conn = self._conectar_openeo()
        bbox_dict = {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
            "crs":  "EPSG:4326",
        }
        logger.info("📡 Calculando SAR en servidores Copernicus...")

        s1 = conn.load_collection(
            "SENTINEL1_GRD",
            spatial_extent  = bbox_dict,
            temporal_extent = [fecha_inicio, fecha_fin],
            bands           = ["VH", "VV"],
        )
        ratio   = s1.band("VH") / s1.band("VV")
        poligono = mapping(shapely_box(*bbox))
        sar_ts   = ratio.aggregate_spatial(geometries=poligono, reducer="mean")

        resultado = sar_ts.execute()
        return self._parsear_resultado_openeo(resultado, variable="sar_ratio")

    @staticmethod
    def _parsear_resultado_openeo(resultado: dict, variable: str) -> list[dict]:
        """Parsea la respuesta de openEO a lista de {fecha, variable}."""
        registros = []
        for fecha_str, valores in resultado.items():
            try:
                val = valores
                while isinstance(val, (list, tuple)):
                    val = val[0]
                val_float = float(val)
                if -2.0 <= val_float <= 2.0:   # rango válido para NDVI y ratios
                    registros.append({
                        "fecha":  fecha_str[:10],
                        variable: round(val_float, 4),
                    })
            except Exception:
                continue
        logger.info(f"✅ {len(registros)} registros {variable} obtenidos")
        return registros


# ── CLIENTE CDS (ERA5) ────────────────────────────────────────────────────────

class CDSClient:
    """
    Cliente para Copernicus Climate Data Store.
    Descarga ERA5-Land, AgERA5 y otros datasets climáticos.

    Uso:
        client = CDSClient()
        df_clima = client.descargar_era5(bbox, años, meses, directorio)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CDS_KEY", "")
        if not self.api_key:
            logger.warning(
                "CDS_KEY no encontrada. "
                "Define CDS_KEY en .env (sin prefijo UID)"
            )

    def _cliente_cdsapi(self):
        """Crea cliente cdsapi con credenciales directas."""
        try:
            import cdsapi
            return cdsapi.Client(
                url   = CDS_URL,
                key   = self.api_key,
                quiet = False,
            )
        except ImportError:
            raise ImportError("Instala cdsapi: pip install cdsapi")

    def descargar_era5(
        self,
        bbox:        list[float],    # [lon_min, lat_min, lon_max, lat_max]
        años:        list[int],
        meses:       list[int],
        directorio:  Union[str, Path] = "data/raw/copernicus/era5_land",
        variables:   Optional[list[str]] = None,
    ) -> Path:
        """
        Descarga ERA5-Land mensual para el área y período dados.
        Retorna la ruta al archivo NetCDF extraído.

        Variables por defecto: temperatura 2m + precipitación total.
        """
        variables = variables or ["2m_temperature", "total_precipitation"]
        directorio = Path(directorio)
        directorio.mkdir(parents=True, exist_ok=True)

        archivo_zip = directorio / "era5_raw.nc"   # la API entrega zip aunque diga .nc

        c = self._cliente_cdsapi()
        logger.info(f"🌧  Descargando ERA5 ({años[0]}–{años[-1]})...")

        c.retrieve(
            "reanalysis-era5-single-levels-monthly-means",
            {
                "product_type": "monthly_averaged_reanalysis",
                "variable":     variables,
                "year":         [str(y) for y in años],
                "month":        [f"{m:02d}" for m in meses],
                "time":         "00:00",
                "area":         [
                    bbox[3] + 0.5,   # norte
                    bbox[0] - 0.5,   # oeste
                    bbox[1] - 0.5,   # sur
                    bbox[2] + 0.5,   # este
                ],
                "format": "netcdf",
            },
            str(archivo_zip),
        )

        # Descomprimir (la nueva API entrega un zip)
        return self._extraer_nc(archivo_zip, directorio)

    @staticmethod
    def _extraer_nc(archivo_zip: Path, directorio: Path) -> Path:
        """Extrae el NetCDF del zip entregado por la API CDS."""
        try:
            with zipfile.ZipFile(str(archivo_zip), "r") as z:
                nombres = z.namelist()
                logger.debug(f"   Archivos en zip: {nombres}")
                for nombre in nombres:
                    z.extract(nombre, str(directorio))
            # Retornar el primer .nc encontrado
            for nombre in nombres:
                if nombre.endswith(".nc"):
                    return directorio / nombre
        except zipfile.BadZipFile:
            # Algunas versiones de la API entregan NetCDF directamente
            logger.debug("   Archivo no es zip — asumiendo NetCDF directo")
        return archivo_zip

    def leer_era5(self, ruta_nc: Union[str, Path]) -> list[dict]:
        """
        Lee un NetCDF ERA5 y retorna lista de {fecha, temp_c, precip_mm}.
        """
        import datetime as dt
        try:
            import netCDF4 as nc
            import numpy as np
        except ImportError:
            raise ImportError("Instala netCDF4: pip install netCDF4")

        ruta_nc = Path(ruta_nc)
        ds      = nc.Dataset(str(ruta_nc))

        # La nueva API usa 'valid_time' en segundos desde epoch
        tiempos = ds["valid_time"][:]
        fechas  = [
            dt.datetime.utcfromtimestamp(int(t)).date()
            for t in tiempos
        ]

        registros = []
        for i, fecha in enumerate(fechas):
            rec = {"fecha": str(fecha)[:7]}   # YYYY-MM

            if "t2m" in ds.variables:
                rec["temp_c"] = round(float(ds["t2m"][i].mean()) - 273.15, 2)

            if "tp" in ds.variables:
                rec["precip_mm"] = round(float(ds["tp"][i].mean()) * 1000 * 30, 1)

            registros.append(rec)

        ds.close()
        logger.info(f"✅ ERA5 leído — {len(registros)} meses")
        return registros


# ── HELPERS GENERALES ─────────────────────────────────────────────────────────

def bbox_desde_coordenadas(
    lat: float,
    lon: float,
    radio_km: float = 3.0,
) -> list[float]:
    """
    Genera un bounding box cuadrado alrededor de un punto.
    Aproximación válida para latitudes colombianas (~4-12°N).

    1° latitud ≈ 111 km
    1° longitud ≈ 111 km × cos(lat) ≈ 110 km para Colombia

    Retorna [lon_min, lat_min, lon_max, lat_max].
    """
    delta = radio_km / 111.0
    return [
        round(lon - delta, 6),
        round(lat - delta, 6),
        round(lon + delta, 6),
        round(lat + delta, 6),
    ]


def resamplear_mensual(registros: list[dict], variable: str) -> list[dict]:
    """
    Agrupa registros diarios/cada-5-días en promedios mensuales.
    Útil para NDVI y SAR antes de alimentar el IRA.
    """
    from collections import defaultdict

    meses: dict = defaultdict(list)
    for r in registros:
        mes = r["fecha"][:7]   # YYYY-MM
        meses[mes].append(r[variable])

    return [
        {
            "fecha":   mes,
            variable:  round(sum(vals) / len(vals), 4),
        }
        for mes, vals in sorted(meses.items())
        if vals
    ]


# ── DEMO ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    print("═" * 55)
    print("  AbejaVerde·EO — copernicus_api")
    print("  Apiario San Juan de Rioseco, Cundinamarca")
    print("═" * 55)

    # Configuración del apiario piloto
    LAT, LON    = 4.875, -74.635
    RADIO_KM    = 3.0
    FECHA_INI   = "2024-01-01"
    FECHA_FIN   = "2025-05-29"

    bbox = bbox_desde_coordenadas(LAT, LON, RADIO_KM)
    print(f"\n📍 Apiario: {LAT}°N, {LON}°O")
    print(f"   Bounding box ({RADIO_KM} km): {bbox}")

    # ── 1. Buscar imágenes en catálogo ────────────────────────────────────────
    print("\n[1/3] Buscando imágenes Sentinel-2 en catálogo...")
    cdse = CDSEClient()
    if cdse.autenticar():
        imagenes = cdse.buscar_imagenes(
            bbox          = bbox,
            fecha_inicio  = FECHA_INI,
            fecha_fin     = FECHA_FIN,
            max_nubosidad = 40.0,
        )
        if imagenes:
            print(f"      {len(imagenes)} imágenes aptas (< 40% nubes)")
            print(f"      Primera: {imagenes[0]['fecha']}  "
                  f"Última: {imagenes[-1]['fecha']}")
        else:
            print("      Sin resultados — usando datos locales")

    # ── 2. Calcular NDVI via openEO ───────────────────────────────────────────
    print("\n[2/3] Calculando NDVI con openEO...")
    try:
        ndvi_serie = cdse.calcular_ndvi_openeo(bbox, FECHA_INI, FECHA_FIN)
        ndvi_mensual = resamplear_mensual(ndvi_serie, "ndvi")
        print(f"      {len(ndvi_mensual)} meses de NDVI")
        if ndvi_mensual:
            max_rec = max(ndvi_mensual, key=lambda x: x["ndvi"])
            min_rec = min(ndvi_mensual, key=lambda x: x["ndvi"])
            print(f"      Máximo: {max_rec['ndvi']} ({max_rec['fecha']})")
            print(f"      Mínimo: {min_rec['ndvi']} ({min_rec['fecha']})")
    except Exception as e:
        print(f"      ⚠️  {e}")

    # ── 3. Descargar ERA5 ─────────────────────────────────────────────────────
    print("\n[3/3] Descargando ERA5 (temperatura + precipitación)...")
    try:
        cds = CDSClient()
        ruta_nc = cds.descargar_era5(
            bbox   = bbox,
            años   = [2024, 2025],
            meses  = list(range(1, 13)),
        )
        clima = cds.leer_era5(ruta_nc)
        print(f"      {len(clima)} meses de datos climáticos")
    except Exception as e:
        print(f"      ⚠️  {e}")

    print("\n✅ copernicus_api listo para importar desde otros módulos")
