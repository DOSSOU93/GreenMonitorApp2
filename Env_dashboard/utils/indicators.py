# utils/indicators.py
"""
Calcul des indicateurs environnementaux
"""
import ee
import streamlit as st


def calculate_indicator(image, sensor_config, indicator_type):
    """Calcule l'indicateur selon le type et le capteur"""
    try:
        if sensor_config["name"] == "MODIS":
            return image
        
        bands = sensor_config["bands"]
        band_names = image.bandNames().getInfo()
        
        # ==================== NDVI ====================
        if indicator_type == "NDVI":
            if bands["nir"] not in band_names or bands["red"] not in band_names:
                return None
            ndvi = image.normalizedDifference([bands["nir"], bands["red"]]).rename('NDVI')
            return ndvi
        
        # ==================== NDWI ====================
        elif indicator_type == "NDWI":
            if bands["green"] not in band_names or bands["nir"] not in band_names:
                return None
            ndwi = image.normalizedDifference([bands["green"], bands["nir"]]).rename('NDWI')
            return ndwi
        
        # ==================== LST (Land Surface Temperature) ====================
        elif indicator_type == "LST":
            if sensor_config["name"] == "Landsat":
                thermal_band = bands.get('thermal', 'ST_B10')
                if thermal_band in band_names:
                    # Conversion de la bande thermale en LST (°C)
                    # Formule standard pour Landsat 8/9
                    lst = image.select(thermal_band) \
                        .multiply(0.00341802) \
                        .add(149.0) \
                        .subtract(273.15) \
                        .rename('LST')
                    return lst
            return None
        
        # ==================== TEMPERATURE (ancien, gardé pour compatibilité) ====================
        elif indicator_type == "Temperature":
            if sensor_config["name"] == "Landsat":
                thermal_band = bands.get('thermal', 'ST_B10')
                if thermal_band in band_names:
                    temp = image.select(thermal_band).multiply(0.00341802).add(149.0).rename('temperature')
                    return temp
            return None
            
        return None
        
    except Exception as e:
        st.error(f"Erreur calculate_indicator: {str(e)}")
        return None


def interpret_value(indicator, value):
    """Interprète la valeur de l'indicateur"""
    
    # ==================== NDVI ====================
    if indicator == "NDVI":
        if value > 0.6:
            return "Forêt dense", "success"
        elif value > 0.4:
            return "Végétation dense", "success"
        elif value > 0.2:
            return "Végétation modérée", "info"
        elif value > 0:
            return "Sol nu", "warning"
        else:
            return "Eau", "info"
    
    # ==================== NDWI ====================
    elif indicator == "NDWI":
        if value > 0.3:
            return "Eau abondante", "success"
        elif value > 0:
            return "Humidité", "info"
        else:
            return "Sec", "warning"
    
    # ==================== LST (Land Surface Temperature) ====================
    elif indicator == "LST":
        if value > 40:
            return f"Température extrême ({value:.1f}°C)", "error"
        elif value > 35:
            return f"Très chaud ({value:.1f}°C)", "error"
        elif value > 30:
            return f"Chaud ({value:.1f}°C)", "warning"
        elif value > 20:
            return f"Tempéré ({value:.1f}°C)", "info"
        elif value > 10:
            return f"Frais ({value:.1f}°C)", "info"
        else:
            return f"Froid ({value:.1f}°C)", "success"
    
    # ==================== TEMPERATURE (ancien, en Kelvin) ====================
    elif indicator == "Temperature":
        temp_c = value - 273.15
        if temp_c > 35:
            return f"Extrême {temp_c:.0f}°C", "error"
        elif temp_c > 30:
            return f"Chaud {temp_c:.0f}°C", "warning"
        elif temp_c > 20:
            return f"Tempéré {temp_c:.0f}°C", "info"
        else:
            return f"Frais {temp_c:.0f}°C", "info"
    
    # ==================== VCI (Vegetation Condition Index) ====================
    elif indicator == "VCI":
        if value > 80:
            return "Végétation très saine", "success"
        elif value > 60:
            return "Végétation saine", "success"
        elif value > 40:
            return "Condition normale", "info"
        elif value > 20:
            return "Stress modéré", "warning"
        else:
            return "Stress sévère (Sécheresse)", "error"
    
    # ==================== ALERTE NDVI ====================
    elif indicator == "Alerte NDVI":
        if value == 1:
            return "Normal - Végétation saine", "success"
        elif value == 2:
            return "Vigilance - Stress léger", "info"
        elif value == 3:
            return "Alerte - Dégradation", "warning"
        elif value == 4:
            return "Alerte critique - Dégradation sévère", "error"
        else:
            return "Eau / Sol nu", "secondary"
    
    # ==================== DEFAULT ====================
    else:
        return "Valeur normale", "info"