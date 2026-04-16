# app.py
"""
Application principale - Tableau de bord environnemental
"""
import streamlit as st
import requests
import socket
import pandas as pd
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import ee
import folium
from streamlit_folium import folium_static
import os
from datetime import datetime
import tempfile
import warnings

# Ignorer les warnings de dépréciation
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Import des modules
from config import (
    COLOR_PALETTES, SENSORS_BY_INDICATOR, INDICATORS, 
    YEARS, MONTHS, LOGO_PATH
)
from utils import (
    load_engine, get_geotiff_url, calculate_change,
    calculate_indicator,
    calculate_stats, compute_timeseries, compute_seasonal,
    plot_timeseries, plot_seasonal,
    export_csv_data,
    coords_to_ee_polygon, format_area,
    get_satellite_image
)
from utils.export import export_pdf
from components import create_sidebar, create_map
from utils.ndvi import NDVIIndicator
from utils.random_forest_classifier import RandomForestClassifier
from utils.ndvi_alert import NDVIAlert
from utils.vci import VCIIndicator
from utils.lst import LSTIndicator

# ==================== VÉRIFICATION DE CONNEXION INTERNET ====================
def check_internet_connection(timeout=5):
    try:
        hosts = ["8.8.8.8", "1.1.1.1", "google.com", "earthengine.google.com"]
        for host in hosts:
            try:
                socket.setdefaulttimeout(timeout)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, 443))
                return True
            except (socket.timeout, socket.error):
                continue
        try:
            response = requests.get("https://earthengine.google.com", timeout=timeout)
            if response.status_code == 200:
                return True
        except (requests.ConnectionError, requests.Timeout):
            pass
        return False
    except Exception:
        return False

if 'connection_ok' not in st.session_state:
    st.session_state.connection_ok = check_internet_connection()

if not st.session_state.connection_ok:
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <div style="text-align:center; padding:50px;">
        <h1>🌐 Pas de connexion internet</h1>
        <p>Veuillez vous connecter à internet et rafraîchir la page.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# ==================== EN-TÊTE AVEC LOGO AGRANDI ====================
col_logo, col_title = st.columns([1, 5])

with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.markdown("<div style='font-size: 60px; text-align: center;'>🌿</div>", unsafe_allow_html=True)

with col_title:
    st.markdown("""
    <div style="text-align: left;">
        <h1 style="color: #2E7D32; margin-bottom: 0;">GreenMonitor</h1>
        <h3 style="color: #555; margin-top: 0;">Tableau de bord de surveillance environnementale</h3>
        <p style="color: #777; font-size: 14px;">
            Suivi NDVI • NDWI • LST • VCI • Classification du sol • Alertes précoces • Export PDF
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# --------------------------
# Initialisation Earth Engine
# --------------------------
with st.spinner("🔄 Initialisation de Google Earth Engine..."):
    try:
        engine = load_engine()
        if engine is None or engine is False:
            st.error("""
            ❌ Impossible de charger Google Earth Engine
            
            **Solution :**
            1. Ouvrez un terminal
            2. Exécutez : `earthengine authenticate --force`
            3. Redémarrez l'application
            """)
            st.stop()
    except Exception as e:
        st.error(f"❌ Erreur Earth Engine: {str(e)[:200]}")
        st.stop()

# Session state
if 'polygon_coords' not in st.session_state:
    st.session_state.polygon_coords = None
if 'shapefile_name' not in st.session_state:
    st.session_state.shapefile_name = None
if 'polygon_bounds' not in st.session_state:
    st.session_state.polygon_bounds = None
if 'ee_polygon' not in st.session_state:
    st.session_state.ee_polygon = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'selected_indicator' not in st.session_state:
    st.session_state.selected_indicator = INDICATORS[0]
if 'selected_sensor' not in st.session_state:
    st.session_state.selected_sensor = list(SENSORS_BY_INDICATOR[INDICATORS[0]].keys())[0]
if 'show_results' not in st.session_state:
    st.session_state.show_results = False
if 'result_image' not in st.session_state:
    st.session_state.result_image = None
if 'result_image_name' not in st.session_state:
    st.session_state.result_image_name = None
if 'geotiff_url' not in st.session_state:
    st.session_state.geotiff_url = None
if 'timeseries_data' not in st.session_state:
    st.session_state.timeseries_data = None
if 'seasonal_data' not in st.session_state:
    st.session_state.seasonal_data = None
if 'fig_timeseries' not in st.session_state:
    st.session_state.fig_timeseries = None
if 'fig_seasonal' not in st.session_state:
    st.session_state.fig_seasonal = None
if 'classification_done' not in st.session_state:
    st.session_state.classification_done = False
if 'rf_classifier' not in st.session_state:
    st.session_state.rf_classifier = None
if 'classified_image' not in st.session_state:
    st.session_state.classified_image = None
if 'rf_scale' not in st.session_state:
    st.session_state.rf_scale = 30

# ==================== FONCTION POUR AJOUTER UNE LÉGENDE À LA CARTE ====================

def add_legend_to_map(map_object, indicator_name):
    """
    Ajoute une légende à la carte Folium
    
    Args:
        map_object: Carte Folium
        indicator_name: Nom de l'indicateur (NDVI, NDWI, LST, VCI, Alerte NDVI, Classification RF)
    """
    
    if indicator_name == "NDVI":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 11px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    max-width: 250px;">
            <strong style="font-size: 14px;">🌿 NDVI</strong><br><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #006837; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Très forte (>0.6)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #A6D96A; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Forte (0.5-0.6)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #FEE08B; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Modérée (0.4-0.5)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #FDAE61; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Moyenne (0.3-0.4)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #D73027; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Faible (0.2-0.3)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #B2182B; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Très faible (0-0.2)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #8B0000; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Très faible (Eau/Sol nu)</span>
        </div>
        '''
    
    elif indicator_name == "NDWI":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 12px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            <strong style="font-size: 14px;">💧 NDWI</strong><br><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #2166AC; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Eau (0.5-1)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #92C5DE; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Humidité modérée (0-0.5)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #F4A582; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Sécheresse (-0.5-0)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #B2182B; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Très sec (<-0.5)</span>
        </div>
        '''
    
    elif indicator_name == "LST":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 12px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            <strong style="font-size: 14px;">🌡️ LST</strong><br><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #1A9850; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Froid (10-20°C)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #FFFFBF; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Tempéré (20-30°C)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #D73027; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Chaud (30-40°C)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #67001F; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Très chaud (>40°C)</span>
        </div>
        '''
    
    elif indicator_name == "VCI":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 11px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    max-width: 220px;">
            <strong style="font-size: 14px;">🌾 VCI</strong><br><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #1A9850; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">🌲 Très bon (>80%)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #A6D96A; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">🟢 Bon (60-80%)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #FFFFBF; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">🟡 Normal (40-60%)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #FDAE61; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">🟠 Stress modéré (20-40%)</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #D73027; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">🔴 Stress sévère (0-20%)</span>
        </div>
        '''
    
    elif indicator_name == "Alerte NDVI":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 12px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            <strong style="font-size: 14px;">🚨 Alertes NDVI</strong><br><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #4CAF50; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Normal (NDVI > 0.5)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #FFC107; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Vigilance (0.3-0.5)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #FF9800; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Alerte (0.2-0.3)</span><br>
            <span style="display: inline-block; width: 18px; height: 18px; background-color: #F44336; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Alerte critique (NDVI < 0.2)</span>
        </div>
        '''
    
    elif indicator_name == "Classification RF":
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 12px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 11px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    max-width: 220px;">
            <strong style="font-size: 14px;">🌲 Classification RF</strong><br><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #1B5E20; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Forêt dense</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #2E7D32; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Forêt galerie</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #388E3C; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Woodland</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #8BC34A; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Savane arbustive</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #FFC107; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Cultures/Jachères</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #9E9E9E; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Urbain/Sol nu</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #4CAF50; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Plantation</span><br>
            <span style="display: inline-block; width: 16px; height: 16px; background-color: #2196F3; border-radius: 3px;"></span>
            <span style="margin-left: 6px;">Eau</span>
        </div>
        '''
    
    else:
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 30px; 
                    right: 30px; 
                    z-index: 1000; 
                    background-color: white; 
                    padding: 10px;
                    border-radius: 8px;
                    border: 2px solid #ccc;
                    font-family: Arial;
                    font-size: 12px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
            <strong>📊 Légende</strong>
        </div>
        '''
    
    map_object.get_root().html.add_child(folium.Element(legend_html))
    return map_object


# ==================== FONCTIONS POUR AFFICHER LES LÉGENDES DANS STREAMLIT ====================

def display_ndvi_legend():
    """Affiche la légende NDVI dans Streamlit"""
    st.markdown("### 🌿 Légende NDVI (Très forte → Très faible)")
    
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #006837; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">>0.6</span><br>
            <span style="font-size: 8px;">Très forte</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #A6D96A; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0.5-0.6</span><br>
            <span style="font-size: 8px;">Forte</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FEE08B; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0.4-0.5</span><br>
            <span style="font-size: 8px;">Modérée</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FDAE61; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0.3-0.4</span><br>
            <span style="font-size: 8px;">Moyenne</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #D73027; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0.2-0.3</span><br>
            <span style="font-size: 8px;">Faible</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #B2182B; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0.1-0.2</span><br>
            <span style="font-size: 8px;">Très faible</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col7:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #8B0000; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0-0.1</span><br>
            <span style="font-size: 8px;">Très faible</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #4A0000; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">{"<"}0</span><br>
            <span style="font-size: 8px;">Eau</span>
        </div>
        """, unsafe_allow_html=True)


def display_ndwi_legend():
    """Affiche la légende NDWI dans Streamlit"""
    st.markdown("### 💧 Légende NDWI")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #2166AC; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">0.5-1</span><br>
            <span style="font-size: 9px;">Eau</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #92C5DE; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">0-0.5</span><br>
            <span style="font-size: 9px;">Humidité modérée</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #F4A582; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">-0.5-0</span><br>
            <span style="font-size: 9px;">Sécheresse</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #B2182B; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">{"<"}-0.5</span><br>
            <span style="font-size: 9px;">Très sec</span>
        </div>
        """, unsafe_allow_html=True)


def display_lst_legend():
    """Affiche la légende LST dans Streamlit"""
    st.markdown("### 🌡️ Légende LST (Température de surface)")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #1A9850; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">10-20°C</span><br>
            <span style="font-size: 9px;">Froid</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FFFFBF; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">20-30°C</span><br>
            <span style="font-size: 9px;">Tempéré</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #D73027; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">30-40°C</span><br>
            <span style="font-size: 9px;">Chaud</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #67001F; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">>40°C</span><br>
            <span style="font-size: 9px;">Très chaud</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #2166AC; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">{"<"}10°C</span><br>
            <span style="font-size: 9px;">Gel</span>
        </div>
        """, unsafe_allow_html=True)


def display_vci_legend():
    """Affiche la légende VCI dans Streamlit (sans eau)"""
    st.markdown("### 🌾 Légende VCI (Vegetation Condition Index)")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #1A9850; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">>80%</span><br>
            <span style="font-size: 8px;">Très bon</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #A6D96A; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">60-80%</span><br>
            <span style="font-size: 8px;">Bon</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FFFFBF; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">40-60%</span><br>
            <span style="font-size: 8px;">Normal</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FDAE61; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">20-40%</span><br>
            <span style="font-size: 8px;">Stress modéré</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #D73027; width: 22px; height: 18px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 9px;">0-20%</span><br>
            <span style="font-size: 8px;">Stress sévère</span>
        </div>
        """, unsafe_allow_html=True)


def display_alert_ndvi_legend():
    """Affiche la légende Alerte NDVI dans Streamlit"""
    st.markdown("### 🚨 Légende Alertes NDVI")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #4CAF50; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Normal</span><br>
            <span style="font-size: 9px;">NDVI > 0.5</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FFC107; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Vigilance</span><br>
            <span style="font-size: 9px;">NDVI 0.3-0.5</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FF9800; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Alerte</span><br>
            <span style="font-size: 9px;">NDVI 0.2-0.3</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #F44336; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Alerte critique</span><br>
            <span style="font-size: 9px;">NDVI < 0.2</span>
        </div>
        """, unsafe_allow_html=True)


def display_rf_legend():
    """Affiche la légende Classification RF dans Streamlit"""
    st.markdown("### 🌲 Légende Classification Random Forest")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #1B5E20; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Forêt dense</span>
        </div>
        <div style="text-align:center; margin-top: 5px;">
            <div style="background: #2E7D32; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Forêt galerie</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #388E3C; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Woodland</span>
        </div>
        <div style="text-align:center; margin-top: 5px;">
            <div style="background: #8BC34A; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Savane arbustive</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #FFC107; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Cultures/Jachères</span>
        </div>
        <div style="text-align:center; margin-top: 5px;">
            <div style="background: #9E9E9E; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Urbain/Sol nu</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div style="text-align:center;">
            <div style="background: #4CAF50; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Plantation</span>
        </div>
        <div style="text-align:center; margin-top: 5px;">
            <div style="background: #2196F3; width: 25px; height: 20px; margin: 0 auto; border-radius: 3px;"></div>
            <span style="font-size: 10px;">Eau</span>
        </div>
        """, unsafe_allow_html=True)


# ==================== SIDEBAR ====================
sidebar_params = create_sidebar(
    COLOR_PALETTES, INDICATORS, YEARS, MONTHS, SENSORS_BY_INDICATOR, LOGO_PATH
)

lat = sidebar_params['lat']
lon = sidebar_params['lon']
selected_indicator = sidebar_params['selected_indicator']
selected_sensor = sidebar_params['selected_sensor']
sensor_config = sidebar_params['sensor_config']
analysis_type = sidebar_params['analysis_type']
year = sidebar_params['year']
month = sidebar_params['month']
enable_comparison = sidebar_params['enable_comparison']
compare_year = sidebar_params['compare_year']
analysis_scale = sidebar_params['analysis_scale']
cloud_threshold = sidebar_params['cloud_threshold']
export_geotiff = sidebar_params['export_geotiff']
show_timeseries = sidebar_params['show_timeseries']
ts_start = sidebar_params['ts_start']
ts_end = sidebar_params['ts_end']
show_seasonal = sidebar_params['show_seasonal']
submit = sidebar_params['submit']

# --------------------------
# Créer la carte (avec une seule OpenStreetMap)
# --------------------------
m = create_map(st.session_state, lat, lon)
# Ajouter une légende par défaut
m = add_legend_to_map(m, "NDVI")

# --------------------------
# ANALYSE - LE TRAITEMENT SE LANCE ICI
# --------------------------
if submit:
    if not st.session_state.polygon_coords:
        st.error("Veuillez d'abord charger un shapefile")
    else:
        with st.spinner("Analyse en cours..."):
            try:
                if not st.session_state.ee_polygon:
                    st.session_state.ee_polygon = coords_to_ee_polygon(st.session_state.polygon_coords)
                
                if st.session_state.ee_polygon:
                    area = st.session_state.ee_polygon.area().getInfo()
                    annual = (analysis_type == "Annuelle")
                    
                    if analysis_type == "Annuelle":
                        period_display = f"{year}"
                    else:
                        month_name = MONTHS[month - 1]
                        period_display = f"{month_name} {year}"
                    
                    # ==================== LST (Land Surface Temperature) ====================
                    if selected_indicator == "LST":
                        with st.spinner("Calcul de la température de surface (LST)..."):
                            lst_indicator = LSTIndicator(COLOR_PALETTES['lst'])
                            
                            img, _ = get_satellite_image(st.session_state.ee_polygon, sensor_config, year, month, annual, cloud_threshold)
                            
                            if img is None:
                                st.error("Aucune image Landsat disponible")
                            else:
                                result = calculate_indicator(img, sensor_config, "LST")
                                
                                if result:
                                    palette = COLOR_PALETTES['lst']
                                    date_label = f"{year}" if annual else f"{year}-{month:02d}"
                                    vis = {'min': palette['min'], 'max': palette['max'], 'palette': palette['palette']}
                                    
                                    map_id = result.getMapId(vis)
                                    folium.TileLayer(
                                        tiles=map_id['tile_fetcher'].url_format,
                                        attr='Google Earth Engine',
                                        name=f"LST ({date_label})",
                                        overlay=True,
                                        show=True
                                    ).add_to(m)
                                    
                                    m = add_legend_to_map(m, "LST")
                                    
                                    stats = calculate_stats(result, st.session_state.ee_polygon, scale=analysis_scale)
                                    
                                    mean_val = stats.get('LST_mean', 0) or stats.get('LST', 0) if stats else 0
                                    std_val = stats.get('LST_stdDev', 0) if stats else 0
                                    min_val = stats.get('LST_min', 0) if stats else 0
                                    max_val = stats.get('LST_max', 0) if stats else 0
                                    
                                    if show_timeseries and ts_start:
                                        timeseries_years, timeseries_vals = compute_timeseries(
                                            st.session_state.ee_polygon, "LST", sensor_config, ts_start, ts_end, cloud_threshold
                                        )
                                        if timeseries_vals and any(v is not None for v in timeseries_vals):
                                            st.session_state.timeseries_data = pd.DataFrame({"Annee": timeseries_years, "Valeur": timeseries_vals})
                                            st.session_state.fig_timeseries = plot_timeseries(timeseries_years, timeseries_vals, "LST (°C)", "LST")
                                    
                                    if show_seasonal:
                                        seasonal_months, month_names, seasonal_vals = compute_seasonal(
                                            st.session_state.ee_polygon, "LST", sensor_config, year, cloud_threshold
                                        )
                                        if seasonal_vals and any(v is not None for v in seasonal_vals):
                                            st.session_state.seasonal_data = pd.DataFrame({"Mois": seasonal_months, "Nom": month_names, "Valeur": seasonal_vals})
                                            st.session_state.fig_seasonal = plot_seasonal(seasonal_months, month_names, seasonal_vals, "LST (°C)", "LST", year)
                                    
                                    st.session_state.analysis_results = {
                                        'indicator': 'LST', 'date': period_display, 'area': format_area(area),
                                        'sensor': selected_sensor, 'cloud_threshold': cloud_threshold,
                                        'mean': mean_val, 'std': std_val, 'min': min_val, 'max': max_val
                                    }
                                    st.session_state.analysis_done = True
                                    st.session_state.show_results = True
                                    
                                    if mean_val > 40:
                                        st.error(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - 🌡️ Extrême")
                                    elif mean_val > 35:
                                        st.warning(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - 🔥 Très chaud")
                                    elif mean_val > 30:
                                        st.warning(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - ☀️ Chaud")
                                    elif mean_val > 20:
                                        st.info(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - 🌤️ Tempéré")
                                    elif mean_val > 10:
                                        st.info(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - 🍃 Frais")
                                    else:
                                        st.success(f"✅ LST calculé! Température moyenne: {mean_val:.1f}°C - ❄️ Froid")
                                else:
                                    st.error("❌ Erreur lors du calcul de la LST")
                    
                    # ==================== VCI (Vegetation Condition Index) ====================
                    elif selected_indicator == "VCI":
                        with st.spinner("Calcul du VCI en cours..."):
                            vci_indicator = VCIIndicator(COLOR_PALETTES['vci'])
                            
                            current_year = year
                            if current_year < 2000:
                                st.warning("Les données MODIS sont disponibles à partir de 2000. Utilisation de l'année 2000.")
                                current_year = 2000
                            
                            if analysis_type == "Annuelle":
                                target_start = f"{current_year}-01-01"
                                target_end = f"{current_year}-12-31"
                            else:
                                target_start = f"{current_year}-{month:02d}-01"
                                if month == 12:
                                    target_end = f"{current_year+1}-01-01"
                                else:
                                    target_end = f"{current_year}-{month+1:02d}-01"
                            
                            hist_end = f"{current_year-1}-12-31"
                            hist_start = f"{max(2000, current_year-6)}-01-01"
                            
                            vci, vci_class, ndvi_min, ndvi_max, current_ndvi = vci_indicator.calculate_vci(
                                aoi=st.session_state.ee_polygon,
                                target_start=target_start,
                                target_end=target_end,
                                hist_start=hist_start,
                                hist_end=hist_end
                            )
                            
                            if vci is not None:
                                # Calque VCI continu (valeurs 0-100) - masqué par défaut
                                vis_vci = {'min': 0, 'max': 100, 'palette': COLOR_PALETTES['vci']['palette']}
                                map_id = vci.getMapId(vis_vci)
                                folium.TileLayer(
                                    tiles=map_id['tile_fetcher'].url_format,
                                    attr='Google Earth Engine',
                                    name=f"VCI ({period_display})",
                                    overlay=True,
                                    show=False
                                ).add_to(m)
                                
                                # Calque VCI classé (1-5) - AFFICHÉ PAR DÉFAUT
                                vis_class = {
                                    'min': 1,
                                    'max': 5,
                                    'palette': COLOR_PALETTES['vci_class']['palette']
                                }
                                map_id_class = vci_class.getMapId(vis_class)
                                folium.TileLayer(
                                    tiles=map_id_class['tile_fetcher'].url_format,
                                    attr='Google Earth Engine',
                                    name=f"Classes VCI ({period_display})",
                                    overlay=True,
                                    show=True
                                ).add_to(m)
                                
                                m = add_legend_to_map(m, "VCI")
                                
                                stats = calculate_stats(vci, st.session_state.ee_polygon, scale=analysis_scale)
                                mean_val = stats.get('VCI_mean', 0) if stats else 0
                                std_val = stats.get('VCI_stdDev', 0) if stats else 0
                                min_val = stats.get('VCI_min', 0) if stats else 0
                                max_val = stats.get('VCI_max', 0) if stats else 0
                                
                                st.session_state.analysis_results = {
                                    'indicator': 'VCI', 'date': period_display, 'area': format_area(area),
                                    'sensor': selected_sensor, 'cloud_threshold': cloud_threshold,
                                    'mean': mean_val, 'std': std_val, 'min': min_val, 'max': max_val
                                }
                                st.session_state.analysis_done = True
                                st.session_state.show_results = True
                                
                                if mean_val > 80:
                                    st.success(f"✅ VCI calculé! Valeur: {mean_val:.1f}% - Végétation très saine")
                                elif mean_val > 60:
                                    st.success(f"✅ VCI calculé! Valeur: {mean_val:.1f}% - Végétation saine")
                                elif mean_val > 40:
                                    st.info(f"✅ VCI calculé! Valeur: {mean_val:.1f}% - Condition normale")
                                elif mean_val > 20:
                                    st.warning(f"✅ VCI calculé! Valeur: {mean_val:.1f}% - Stress modéré")
                                else:
                                    st.error(f"✅ VCI calculé! Valeur: {mean_val:.1f}% - Stress sévère")
                            else:
                                st.error("❌ Erreur lors du calcul du VCI")
                    
                    # ==================== INDICATEURS STANDARDS (NDVI, NDWI) ====================
                    elif selected_indicator in ["NDVI", "NDWI"]:
                        img, _ = get_satellite_image(st.session_state.ee_polygon, sensor_config, year, month, annual, cloud_threshold)
                        
                        if img is None:
                            st.error("Aucune image disponible")
                        else:
                            result = calculate_indicator(img, sensor_config, selected_indicator)
                            
                            if result:
                                palette = COLOR_PALETTES[selected_indicator.lower()]
                                date_label = f"{year}" if annual else f"{year}-{month:02d}"
                                vis = {'min': palette['min'], 'max': palette['max'], 'palette': palette['palette']}
                                
                                map_id = result.getMapId(vis)
                                folium.TileLayer(
                                    tiles=map_id['tile_fetcher'].url_format,
                                    attr='Google Earth Engine',
                                    name=f"{selected_indicator} ({date_label})",
                                    overlay=True,
                                    show=True
                                ).add_to(m)
                                
                                m = add_legend_to_map(m, selected_indicator)
                                
                                stats = calculate_stats(result, st.session_state.ee_polygon, scale=analysis_scale)
                                
                                mean_val = 0
                                std_val = 0
                                min_val = 0
                                max_val = 0
                                
                                if stats:
                                    if selected_indicator == "NDVI":
                                        mean_val = stats.get('NDVI_mean', 0) or stats.get('NDVI', 0)
                                        std_val = stats.get('NDVI_stdDev', 0)
                                        min_val = stats.get('NDVI_min', 0)
                                        max_val = stats.get('NDVI_max', 0)
                                    else:
                                        mean_val = stats.get('NDWI_mean', 0) or stats.get('NDWI', 0)
                                        std_val = stats.get('NDWI_stdDev', 0)
                                        min_val = stats.get('NDWI_min', 0)
                                        max_val = stats.get('NDWI_max', 0)
                                
                                if show_timeseries and ts_start:
                                    timeseries_years, timeseries_vals = compute_timeseries(
                                        st.session_state.ee_polygon, selected_indicator, sensor_config, ts_start, ts_end, cloud_threshold
                                    )
                                    if timeseries_vals and any(v is not None for v in timeseries_vals):
                                        st.session_state.timeseries_data = pd.DataFrame({"Annee": timeseries_years, "Valeur": timeseries_vals})
                                        st.session_state.fig_timeseries = plot_timeseries(timeseries_years, timeseries_vals, selected_indicator, selected_indicator)
                                
                                if show_seasonal:
                                    seasonal_months, month_names, seasonal_vals = compute_seasonal(
                                        st.session_state.ee_polygon, selected_indicator, sensor_config, year, cloud_threshold
                                    )
                                    if seasonal_vals and any(v is not None for v in seasonal_vals):
                                        st.session_state.seasonal_data = pd.DataFrame({"Mois": seasonal_months, "Nom": month_names, "Valeur": seasonal_vals})
                                        st.session_state.fig_seasonal = plot_seasonal(seasonal_months, month_names, seasonal_vals, selected_indicator, selected_indicator, year)
                                
                                st.session_state.analysis_results = {
                                    'indicator': selected_indicator, 'date': period_display, 'area': format_area(area),
                                    'sensor': selected_sensor, 'cloud_threshold': cloud_threshold,
                                    'mean': mean_val, 'std': std_val, 'min': min_val, 'max': max_val
                                }
                                st.session_state.analysis_done = True
                                st.session_state.show_results = True
                                st.success(f"✅ Analyse {selected_indicator} terminée avec succès!")
                    
                    # ==================== ALERTE NDVI ====================
                    elif selected_indicator == "Alerte NDVI":
                        img, _ = get_satellite_image(st.session_state.ee_polygon, sensor_config, year, month, annual, cloud_threshold)
                        
                        if img is None:
                            st.error("Aucune image NDVI disponible")
                        else:
                            ndvi_result = calculate_indicator(img, sensor_config, "NDVI")
                            
                            if ndvi_result is None:
                                st.error("Erreur lors du calcul du NDVI")
                            else:
                                alert_system = NDVIAlert()
                                
                                st.sidebar.markdown("---")
                                st.sidebar.markdown("### 🚨 Paramètres d'alerte")
                                
                                alert_method = st.sidebar.radio(
                                    "Méthode d'alerte",
                                    ["Seuils absolus", "Anomalies NDVI (5 ans)"],
                                    key="alert_method_ndvi"
                                )
                                
                                if alert_method == "Seuils absolus":
                                    with st.spinner("Classification par seuils absolus..."):
                                        alert_map = alert_system.classify_absolute(ndvi_result, st.session_state.ee_polygon)
                                        stats = alert_system.get_stats(alert_map, st.session_state.ee_polygon, analysis_scale)
                                        
                                        vis_alert = {'min': 1, 'max': 5, 'palette': alert_system.alert_palette}
                                        map_id = alert_map.getMapId(vis_alert)
                                        folium.TileLayer(
                                            tiles=map_id['tile_fetcher'].url_format,
                                            attr='Google Earth Engine',
                                            name=f"Alertes NDVI ({period_display})",
                                            overlay=True,
                                            show=True
                                        ).add_to(m)
                                        
                                        m = add_legend_to_map(m, "Alerte NDVI")
                                        
                                        st.session_state.result_image = alert_map
                                        st.session_state.analysis_results = {
                                            'indicator': 'Alerte NDVI',
                                            'date': period_display,
                                            'area': format_area(area),
                                            'sensor': selected_sensor,
                                            'cloud_threshold': cloud_threshold,
                                            'method': 'Seuils absolus',
                                            'stats': stats
                                        }
                                else:
                                    with st.spinner("Calcul des anomalies historiques (5 ans)..."):
                                        if analysis_type == "Annuelle":
                                            hist_start = f"{year-5}-01-01"
                                            hist_end = f"{year}-12-31"
                                        else:
                                            hist_start = f"{year-5}-{month:02d}-01"
                                            hist_end = f"{year}-{month:02d}-28"
                                        
                                        anomaly, hist_mean = alert_system.calculate_anomaly(
                                            ndvi_result, hist_start, hist_end, 
                                            st.session_state.ee_polygon, sensor_config
                                        )
                                        
                                        if anomaly is not None:
                                            alert_map = alert_system.classify_anomaly(anomaly, st.session_state.ee_polygon)
                                            stats = alert_system.get_stats(alert_map, st.session_state.ee_polygon, analysis_scale)
                                            
                                            vis_anomaly = {'min': -0.3, 'max': 0.3, 'palette': ['#D73027', '#FFFFBF', '#1A9850']}
                                            map_id_anomaly = anomaly.getMapId(vis_anomaly)
                                            folium.TileLayer(
                                                tiles=map_id_anomaly['tile_fetcher'].url_format,
                                                attr='Google Earth Engine',
                                                name=f"Anomalies NDVI ({period_display})",
                                                overlay=True,
                                                show=False
                                            ).add_to(m)
                                            
                                            vis_alert = {'min': 1, 'max': 5, 'palette': alert_system.alert_palette}
                                            map_id_alert = alert_map.getMapId(vis_alert)
                                            folium.TileLayer(
                                                tiles=map_id_alert['tile_fetcher'].url_format,
                                                attr='Google Earth Engine',
                                                name=f"Alertes NDVI ({period_display})",
                                                overlay=True,
                                                show=True
                                            ).add_to(m)
                                            
                                            m = add_legend_to_map(m, "Alerte NDVI")
                                            
                                            st.session_state.result_image = alert_map
                                            st.session_state.analysis_results = {
                                                'indicator': 'Alerte NDVI',
                                                'date': period_display,
                                                'area': format_area(area),
                                                'sensor': selected_sensor,
                                                'cloud_threshold': cloud_threshold,
                                                'method': 'Anomalies NDVI',
                                                'stats': stats
                                            }
                                        else:
                                            st.error("Erreur calcul des anomalies")
                                
                                st.session_state.analysis_done = True
                                st.session_state.show_results = True
                                st.success(f"✅ Alerte NDVI terminée - {alert_method}")
                    
                    # ==================== CLASSIFICATION RF ====================
                    elif selected_indicator == "Classification RF":
                        geojson_path = os.path.join("data", "zones_entrainement.geojson")
                        
                        if not os.path.exists(geojson_path):
                            st.error(f"❌ Fichier non trouvé: `{geojson_path}`")
                        else:
                            if analysis_type == "Annuelle":
                                start_date = f"{year}-01-01"
                                end_date = f"{year}-12-31"
                            else:
                                start_date = f"{year}-{month:02d}-01"
                                end_date = f"{year}-{month:02d}-28"
                            
                            rf_classifier = RandomForestClassifier()
                            
                            with st.spinner("📡 Récupération image..."):
                                image = rf_classifier.get_satellite_image(
                                    roi=st.session_state.ee_polygon,
                                    start_date=start_date,
                                    end_date=end_date,
                                    cloud_threshold=cloud_threshold
                                )
                            
                            if image:
                                with st.spinner("📁 Chargement zones..."):
                                    training_zones = rf_classifier.load_training_zones(geojson_path)
                                
                                if training_zones:
                                    with st.spinner(f"🌲 Entraînement (scale={analysis_scale}m)..."):
                                        metrics = rf_classifier.train_and_classify(
                                            image=image, training_zones=training_zones,
                                            num_trees=100, training_ratio=0.7, scale=analysis_scale
                                        )
                                    
                                    if metrics:
                                        classified = image.select(rf_classifier.bands).classify(rf_classifier.classifier)
                                        
                                        vis_rf = {'min': 0, 'max': 6, 'palette': rf_classifier.palette}
                                        map_id = classified.getMapId(vis_rf)
                                        folium.TileLayer(
                                            tiles=map_id['tile_fetcher'].url_format,
                                            attr='Google Earth Engine',
                                            name=f"Classification RF ({period_display})",
                                            overlay=True,
                                            show=True
                                        ).add_to(m)
                                        
                                        m = add_legend_to_map(m, "Classification RF")
                                        
                                        st.session_state.result_image = classified
                                        st.session_state.analysis_results = {
                                            'indicator': 'Classification RF', 'date': period_display,
                                            'area': format_area(area), 'sensor': selected_sensor,
                                            'cloud_threshold': cloud_threshold, 'mean': 0, 'std': 0, 'min': 0, 'max': 6,
                                            'metrics': metrics
                                        }
                                        st.session_state.analysis_done = True
                                        st.session_state.show_results = True
                                        st.session_state.classification_done = True
                                        st.session_state.rf_classifier = rf_classifier
                                        st.session_state.classified_image = classified
                                        
                                        st.success(f"✅ Classification terminée")
                            
            except Exception as e:
                st.error(f"Erreur: {str(e)[:100]}")

# ==================== AFFICHAGE DES LÉGENDES DANS STREAMLIT ====================
if st.session_state.analysis_done and st.session_state.show_results:
    indicator = st.session_state.analysis_results.get('indicator')
    
    if indicator == "NDVI":
        st.markdown("---")
        display_ndvi_legend()
    
    elif indicator == "NDWI":
        st.markdown("---")
        display_ndwi_legend()
    
    elif indicator == "LST":
        st.markdown("---")
        display_lst_legend()
    
    elif indicator == "VCI":
        st.markdown("---")
        display_vci_legend()
    
    elif indicator == "Alerte NDVI":
        st.markdown("---")
        display_alert_ndvi_legend()
    
    elif indicator == "Classification RF":
        st.markdown("---")
        display_rf_legend()

# --------------------------
# AFFICHAGE DES RÉSULTATS STANDARDS
# --------------------------
if st.session_state.analysis_done and st.session_state.show_results:
    if st.session_state.analysis_results.get('indicator') in ["NDVI", "NDWI", "LST", "VCI"]:
        res = st.session_state.analysis_results
        st.markdown("---")
        st.markdown("### 📈 Résultats de l'analyse")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**{res['indicator']}** | {res['date']}")
            st.markdown(f"**Surface:** {res['area']}")
        with col2:
            st.markdown(f"**Moyenne:** {res['mean']:.3f}")
            st.markdown(f"**Minimum:** {res['min']:.3f}")
        with col3:
            st.markdown(f"**Maximum:** {res['max']:.3f}")
            st.markdown(f"**Écart-type:** {res['std']:.3f}")
        
        # Interprétation spécifique pour LST
        if res['indicator'] == "LST":
            st.markdown("---")
            st.markdown("### 📊 Interprétation de la température de surface")
            lst_value = res['mean']
            
            if lst_value > 40:
                st.error("🔴 **Température extrême** (>40°C) - Risque de canicule")
            elif lst_value > 35:
                st.warning("🟠 **Très chaud** (35-40°C) - Vague de chaleur")
            elif lst_value > 30:
                st.warning("🟡 **Chaud** (30-35°C) - Température élevée")
            elif lst_value > 20:
                st.info("🟢 **Tempéré** (20-30°C) - Conditions normales")
            elif lst_value > 10:
                st.info("🔵 **Frais** (10-20°C) - Température douce")
            else:
                st.success("❄️ **Froid** (<10°C) - Température basse")
        
        # Interprétation spécifique pour VCI
        if res['indicator'] == "VCI":
            st.markdown("---")
            st.markdown("### 📊 Interprétation du VCI")
            vci_value = res['mean']
            
            if vci_value > 80:
                st.success("🟢 **Végétation très saine** - Conditions idéales")
            elif vci_value > 60:
                st.success("🟢 **Végétation saine** - Bonnes conditions")
            elif vci_value > 40:
                st.info("🟡 **Condition normale** - Végétation modérée")
            elif vci_value > 20:
                st.warning("🟠 **Stress modéré** - Surveillance recommandée")
            else:
                st.error("🔴 **Stress sévère** - Risque de sécheresse")
        
        st.markdown("---")
        
        col_graph1, col_graph2 = st.columns(2)
        with col_graph1:
            if show_timeseries and st.session_state.fig_timeseries is not None:
                st.pyplot(st.session_state.fig_timeseries)
                plt.close(st.session_state.fig_timeseries)
            else:
                st.info("📊 Aucune donnée de série temporelle disponible")
        with col_graph2:
            if show_seasonal and st.session_state.fig_seasonal is not None:
                st.pyplot(st.session_state.fig_seasonal)
                plt.close(st.session_state.fig_seasonal)
            else:
                st.info("📊 Aucune donnée de variation saisonnière disponible")
        
        st.markdown("---")
        
        if st.button("❌ Fermer les résultats", use_container_width=True):
            st.session_state.show_results = False
            st.rerun()

# --------------------------
# AFFICHAGE DES RÉSULTATS ALERTE NDVI
# --------------------------
if (st.session_state.analysis_done and st.session_state.show_results and 
    st.session_state.analysis_results.get('indicator') == "Alerte NDVI"):
    
    st.markdown("---")
    st.markdown("## 🚨 Système d'Alerte NDVI")
    
    res = st.session_state.analysis_results
    alert_system = NDVIAlert()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Méthode", res.get('method', 'N/A'))
    with col2:
        st.metric("📅 Période", res['date'])
    with col3:
        st.metric("🗺️ Surface", res['area'])
    with col4:
        st.metric("🛰️ Capteur", res['sensor'])
    
    st.markdown("---")
    alert_system.display_legend()
    st.markdown("---")
    
    if 'stats' in res and res['stats']:
        alert_system.display_stats(res['stats'])
        alert_system.display_recommendations(res['stats'])
    
    st.markdown("---")
    
    if st.button("❌ Fermer", use_container_width=True):
        st.session_state.show_results = False
        st.rerun()

# --------------------------
# AFFICHAGE DES RÉSULTATS CLASSIFICATION RF
# --------------------------
if (st.session_state.analysis_done and st.session_state.show_results and 
    st.session_state.analysis_results.get('indicator') == "Classification RF" and st.session_state.classification_done):
    
    st.markdown("---")
    st.markdown("## 🌲 Classification Random Forest")
    
    if st.session_state.rf_classifier is not None and st.session_state.classified_image is not None:
        rf_classifier = st.session_state.rf_classifier
        classified = st.session_state.classified_image
        
        if hasattr(rf_classifier, 'validation_metrics') and rf_classifier.validation_metrics:
            metrics = rf_classifier.validation_metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Exactitude globale", f"{metrics['overall_accuracy']*100:.1f}%")
            with col2:
                kappa = metrics['kappa']
                st.metric("Indice Kappa", f"{kappa:.3f}")
            with col3:
                st.metric("Échantillons", f"{metrics['training_samples']} train | {metrics['validation_samples']} val")
        
        st.markdown("### 📊 Répartition des classes")
        
        try:
            histogram = classified.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=st.session_state.ee_polygon,
                scale=30,
                bestEffort=True,
                maxPixels=1e9
            ).getInfo()
        except Exception as e:
            st.warning(f"Erreur calcul histogramme: {str(e)[:100]}")
            histogram = None
        
        if histogram and 'classification' in histogram:
            total_pixels = sum(histogram['classification'].values())
            class_items = []
            for class_id_str, count in histogram['classification'].items():
                class_id = int(class_id_str)
                class_info = rf_classifier.classes.get(class_id, {'name': f'Classe {class_id}', 'color': '#ccc'})
                percentage = (count / total_pixels) * 100
                class_items.append((class_info['name'], percentage, class_info['color']))
            
            class_items.sort(key=lambda x: x[1], reverse=True)
            
            fig, ax = plt.subplots(figsize=(10, 5))
            names = [item[0] for item in class_items]
            pcts = [item[1] for item in class_items]
            colors = [item[2] for item in class_items]
            
            bars = ax.barh(names, pcts, color=colors, edgecolor='black', linewidth=0.5)
            ax.set_xlabel('Pourcentage (%)', fontsize=12)
            ax.set_title('Occupation du sol', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='x')
            for bar, pct in zip(bars, pcts):
                ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, f'{pct:.1f}%', va='center', fontsize=10)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
        else:
            st.info("Aucune donnée de répartition disponible")
        
        st.info("💡 La carte de classification est visible sur la carte principale ci-dessous (calque 'Classification RF')")
        
        st.markdown("---")
        st.markdown("### 💾 Export des résultats")
        
        col_csv, col_pdf = st.columns(2)
        
        with col_csv:
            if histogram and 'classification' in histogram:
                export_data = []
                for name, pct, color in class_items:
                    export_data.append({"Classe": name, "Pourcentage": f"{pct:.1f}%", "Couleur": color})
                export_df = pd.DataFrame(export_data)
                st.download_button(
                    "📊 CSV",
                    data=export_df.to_csv(index=False, encoding='utf-8-sig'),
                    file_name=f"rf_classification_{st.session_state.analysis_results.get('date', 'unknown')}.csv",
                    width='stretch'
                )
            else:
                st.download_button(
                    "📊 CSV",
                    data=pd.DataFrame({"Information": ["Aucune donnée disponible"]}).to_csv(index=False),
                    file_name=f"rf_classification_{st.session_state.analysis_results.get('date', 'unknown')}.csv",
                    width='stretch',
                    disabled=True
                )
        
        with col_pdf:
            try:
                pdf_path = export_pdf(
                    results=st.session_state.analysis_results,
                    timeseries_df=None,
                    seasonal_df=None,
                    COLOR_PALETTES=COLOR_PALETTES,
                    classified_image=classified,
                    region=st.session_state.ee_polygon,
                    palette=rf_classifier.palette
                )
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📄 PDF",
                            data=f,
                            file_name=f"rapport_RF_{st.session_state.analysis_results.get('date', 'unknown')}.pdf",
                            width='stretch'
                        )
                else:
                    st.download_button("📄 PDF", data="", disabled=True, width='stretch')
            except Exception as e:
                st.error(f"Erreur génération PDF: {str(e)[:100]}")
                st.download_button("📄 PDF", data="", disabled=True, width='stretch')

# --------------------------
# Carte principale
# --------------------------
st.markdown("### 🗺️ Visualisation cartographique")

# Ajouter le contrôle des couches
folium.LayerControl(collapsed=False).add_to(m)

# Afficher la carte
folium_static(m, width=1300, height=600)

# Aide compacte
with st.expander("ℹ️ Aide"):
    st.markdown("""
    **Utilisation rapide:**
    1. Chargez un shapefile (ZIP)
    2. Choisissez NDVI, NDWI, LST, VCI, Classification RF ou Alerte NDVI
    3. Sélectionnez la période
    4. Cliquez "Lancer l'analyse"
    
    **NDVI (Normalized Difference Vegetation Index):**
    - Indice de végétation (Très forte → Très faible)
    
    **LST (Land Surface Temperature):**
    - Température de surface issue des satellites Landsat 8/9
    - <10°C: Froid | 10-20°C: Frais | 20-30°C: Tempéré | 30-35°C: Chaud | 35-40°C: Très chaud | >40°C: Extrême
    
    **VCI (Vegetation Condition Index):**
    - Compare le NDVI actuel avec l'historique (5 ans)
    - 🔴 Stress sévère (0-20%) | 🟠 Stress modéré (20-40%) | 🟡 Normal (40-60%) | 🟢 Bon (60-80%) | 🌲 Très bon (80-100%)
    - Les zones d'eau sont masquées
    
    **Classification RF:** Utilisez échelle 30m pour un calcul rapide (10m = très lent)
    """)