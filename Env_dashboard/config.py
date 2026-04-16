# config.py
"""
Configuration globale de l'application
"""
import os

# Palettes de couleurs
COLOR_PALETTES = {
    'ndvi': {
        'palette': ['#8B0000', '#FF4500', '#FFA500', '#FFFFE0', '#90EE90', '#32CD32', '#006400'],
        'min': -1,
        'max': 1,
        'legend': [
            {"value": -1.0, "color": "#8B0000", "label": "Eau"},
            {"value": 0.0, "color": "#FFA500", "label": "Sol nu"},
            {"value": 0.4, "color": "#90EE90", "label": "Végétation"},
            {"value": 0.6, "color": "#32CD32", "label": "Forêt"},
            {"value": 1.0, "color": "#006400", "label": "Forêt dense"}
        ]
    },
    'ndwi': {
        'palette': ['#8B0000', '#FF4500', '#FFA500', '#FFFFE0', '#87CEEB', '#4682B4', '#00008B'],
        'min': -1,
        'max': 1,
        'legend': [
            {"value": -1.0, "color": "#8B0000", "label": "Très sec"},
            {"value": 0.0, "color": "#FFA500", "label": "Sec"},
            {"value": 0.2, "color": "#FFFFE0", "label": "Humide"},
            {"value": 0.4, "color": "#87CEEB", "label": "Eau"},
            {"value": 1.0, "color": "#00008B", "label": "Eau abondante"}
        ]
    },
    'lst': {
        'palette': ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', 
                    '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
        'min': 0,
        'max': 50,
        'legend': [
            {"value": 0, "color": "#313695", "label": "Très froid (<10°C)"},
            {"value": 10, "color": "#74add1", "label": "Frais (10-20°C)"},
            {"value": 20, "color": "#ffffbf", "label": "Tempéré (20-30°C)"},
            {"value": 30, "color": "#fdae61", "label": "Chaud (30-35°C)"},
            {"value": 35, "color": "#d73027", "label": "Très chaud (35-40°C)"},
            {"value": 40, "color": "#a50026", "label": "Extrême (>40°C)"}
        ]
    },
    'change': {
        'palette': ['#8B0000', '#FF4500', '#FFFFE0', '#90EE90', '#006400'],
        'min': -0.5,
        'max': 0.5,
        'legend': [
            {"value": -0.5, "color": "#8B0000", "label": "Dégradation"},
            {"value": 0.0, "color": "#FFFFE0", "label": "Stable"},
            {"value": 0.5, "color": "#006400", "label": "Amélioration"}
        ]
    },
    'classification_rf': {
        'palette': ['#FF6347', '#8B4513', '#DAA520', '#4169E1', '#228B22', '#FFD700', '#006400'],
        'min': 0,
        'max': 6,
        'legend': [
            {"value": 0, "color": "#FF6347", "label": "Buildings"},
            {"value": 1, "color": "#8B4513", "label": "Sol nu"},
            {"value": 2, "color": "#DAA520", "label": "Savane"},
            {"value": 3, "color": "#4169E1", "label": "Eau"},
            {"value": 4, "color": "#228B22", "label": "Forêt galerie"},
            {"value": 5, "color": "#FFD700", "label": "Culture"},
            {"value": 6, "color": "#006400", "label": "Forêt dense"}
        ]
    },
    'alerte_ndvi': {
        'palette': ['#4CAF50', '#FFC107', '#FF9800', '#F44336', '#808080'],
        'min': 1,
        'max': 5,
        'legend': [
            {"value": 1, "color": "#4CAF50", "label": "Normal"},
            {"value": 2, "color": "#FFC107", "label": "Vigilance"},
            {"value": 3, "color": "#FF9800", "label": "Alerte"},
            {"value": 4, "color": "#F44336", "label": "Alerte critique"},
            {"value": 5, "color": "#808080", "label": "Eau / Sol nu"}
        ]
    },
    # ========== VCI - SANS BLEU (eau masquée) ==========
    'vci': {
        'palette': ['#D73027', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9850'],
        'min': 0,
        'max': 100,
        'legend': [
            {"value": 0, "color": "#D73027", "label": "Stress sévère (0-20%)"},
            {"value": 20, "color": "#FDAE61", "label": "Stress modéré (20-40%)"},
            {"value": 40, "color": "#FFFFBF", "label": "Condition normale (40-60%)"},
            {"value": 60, "color": "#A6D96A", "label": "Bon (60-80%)"},
            {"value": 80, "color": "#1A9850", "label": "Très bon (80-100%)"}
        ]
    },
    # ========== VCI CLASS - SANS BLEU (eau masquée) ==========
    'vci_class': {
        'palette': ['#D73027', '#FDAE61', '#FFFFBF', '#A6D96A', '#1A9850'],
        'min': 1,
        'max': 5,
        'legend': [
            {"value": 1, "color": "#D73027", "label": "Stress sévère (0-20%)"},
            {"value": 2, "color": "#FDAE61", "label": "Stress modéré (20-40%)"},
            {"value": 3, "color": "#FFFFBF", "label": "Condition normale (40-60%)"},
            {"value": 4, "color": "#A6D96A", "label": "Bon (60-80%)"},
            {"value": 5, "color": "#1A9850", "label": "Très bon (80-100%)"}
        ]
    }
}

# Configuration des capteurs par indicateur
SENSORS_BY_INDICATOR = {
    "NDVI": {
        "Sentinel-2 (10m)": {
            "name": "Sentinel-2",
            "collection": "COPERNICUS/S2_SR_HARMONIZED",
            "bands": {"red": "B4", "nir": "B8", "green": "B3"},
            "resolution": 10,
            "cloud_filter": "CLOUDY_PIXEL_PERCENTAGE"
        },
        "Landsat 8/9 (30m)": {
            "name": "Landsat",
            "collection": "LANDSAT/LC08/C02/T1_L2",
            "bands": {"red": "SR_B4", "nir": "SR_B5", "green": "SR_B3"},
            "resolution": 30,
            "cloud_filter": "CLOUD_COVER"
        },
        "MODIS (250m)": {
            "name": "MODIS",
            "collection": "MODIS/061/MOD13Q1",
            "bands": {"ndvi": "NDVI", "evi": "EVI"},
            "resolution": 250,
            "cloud_filter": None
        }
    },
    "NDWI": {
        "Sentinel-2 (10m)": {
            "name": "Sentinel-2",
            "collection": "COPERNICUS/S2_SR_HARMONIZED",
            "bands": {"red": "B4", "nir": "B8", "green": "B3"},
            "resolution": 10,
            "cloud_filter": "CLOUDY_PIXEL_PERCENTAGE"
        },
        "Landsat 8/9 (30m)": {
            "name": "Landsat",
            "collection": "LANDSAT/LC08/C02/T1_L2",
            "bands": {"red": "SR_B4", "nir": "SR_B5", "green": "SR_B3"},
            "resolution": 30,
            "cloud_filter": "CLOUD_COVER"
        }
    },
    "LST": {
        "Landsat 8/9 (30m)": {
            "name": "Landsat",
            "collection": "LANDSAT/LC08/C02/T1_L2",
            "bands": {"thermal": "ST_B10"},
            "resolution": 30,
            "cloud_filter": "CLOUD_COVER"
        }
    },
    "VCI": {
        "MODIS (250m)": {
            "name": "MODIS",
            "collection": "MODIS/006/MOD13Q1",
            "bands": {"ndvi": "NDVI"},
            "resolution": 250,
            "cloud_filter": None
        }
    },
    "Classification RF": {
        "Sentinel-2 (10m)": {
            "name": "Sentinel-2",
            "collection": "COPERNICUS/S2_SR_HARMONIZED",
            "bands": {"b2": "B2", "b3": "B3", "b4": "B4", "b8": "B8"},
            "resolution": 10,
            "cloud_filter": "CLOUDY_PIXEL_PERCENTAGE"
        }
    },
    "Alerte NDVI": {
        "Sentinel-2 (10m)": {
            "name": "Sentinel-2",
            "collection": "COPERNICUS/S2_SR_HARMONIZED",
            "bands": {"red": "B4", "nir": "B8", "green": "B3"},
            "resolution": 10,
            "cloud_filter": "CLOUDY_PIXEL_PERCENTAGE"
        },
        "Landsat 8/9 (30m)": {
            "name": "Landsat",
            "collection": "LANDSAT/LC08/C02/T1_L2",
            "bands": {"red": "SR_B4", "nir": "SR_B5", "green": "SR_B3"},
            "resolution": 30,
            "cloud_filter": "CLOUD_COVER"
        }
    }
}

# Liste des indicateurs
INDICATORS = ["NDVI", "NDWI", "LST", "VCI", "Classification RF", "Alerte NDVI"]

# Années et mois
YEARS = list(range(2000, 2026))
MONTHS = ["Jan", "Fev", "Mar", "Avr", "Mai", "Juin", "Juil", "Aout", "Sep", "Oct", "Nov", "Dec"]

# Logo path
LOGO_PATH = os.path.join("asset", "logo.png")