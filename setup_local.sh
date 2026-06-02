#!/bin/bash
# ─────────────────────────────────────────────────────────────
# AbejaVerde·EO — Script de configuración inicial local
# Ejecutar una sola vez después de clonar el repositorio
# Uso: bash setup_local.sh
# ─────────────────────────────────────────────────────────────

echo "🐝 AbejaVerde·EO — Setup inicial"
echo "================================="

# 1. Verificar Python
python_version=$(python3 --version 2>&1)
echo "✅ Python: $python_version"

# 2. Crear entorno virtual
if [ ! -d ".venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv .venv
    echo "✅ Entorno virtual creado"
else
    echo "✅ Entorno virtual ya existe"
fi

# 3. Activar e instalar dependencias
echo "📦 Instalando dependencias..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencias instaladas"

# 4. Crear .env si no existe
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Archivo .env creado desde .env.example"
    echo "    → Complete sus credenciales en .env antes de continuar"
else
    echo "✅ .env ya existe"
fi

# 5. Crear carpetas de datos que van en .gitignore
mkdir -p data/raw/copernicus/sentinel2
mkdir -p data/raw/copernicus/era5_land
mkdir -p data/raw/copernicus/sentinel3
mkdir -p data/raw/copernicus/land_phenology
mkdir -p data/raw/copernicus/water_bodies
mkdir -p data/raw/copernicus/global_surface_water
mkdir -p data/raw/ideam/estaciones
mkdir -p data/raw/iot/colmena_real
mkdir -p data/raw/iot/beep_base
mkdir -p data/raw/datos_gov_co/eva_apicola
mkdir -p data/raw/datos_gov_co/actividad_apicola
echo "✅ Carpetas de datos creadas"

echo ""
echo "🚀 Setup completo. Próximos pasos:"
echo "   1. Complete sus credenciales en .env"
echo "   2. Active el entorno: source .venv/bin/activate"
echo "   3. Pruebe el dashboard: streamlit run app/dashboard.py"
echo ""
echo "📖 Documentación: docs/AbejaVerde_EO_PlanTrabajo.md"
