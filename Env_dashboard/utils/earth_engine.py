# utils/earth_engine.py
"""
Fonctions pour interagir avec Earth Engine
"""
import ee
import streamlit as st


# Remplacez par l'ID de votre projet Google Cloud
PROJECT_ID = "mon-projet-spatial"


def load_engine():
    """Charge et initialise Google Earth Engine"""
    try:
        # Initialisation AVEC le projet specifie
        ee.Initialize(project=PROJECT_ID)
        st.success("✅ Google Earth Engine initialise avec succes !")
        return True
    except Exception as e:
        # Essai sans projet (au cas ou deja configure)
        try:
            ee.Initialize()
            return True
        except:
            pass
        
        # Essai avec service account (Streamlit Cloud)
        try:
            if hasattr(st, 'secrets') and st.secrets and "earth_engine" in st.secrets:
                secrets = st.secrets["earth_engine"]
                if "client_email" in secrets and "private_key" in secrets:
                    credentials = ee.ServiceAccountCredentials(
                        secrets["client_email"], 
                        key_data=secrets["private_key"].replace('\\n', '\n')
                    )
                    ee.Initialize(credentials, project=PROJECT_ID)
                    st.success("✅ Google Earth Engine initialise avec succes !")
                    return True
        except:
            pass
        
        # Message d'erreur avec instructions
        st.error(f"""
❌ Erreur Earth Engine: {str(e)[:150]}

Solution 1 - Configurer le projet dans le terminal:
    earthengine set_project {PROJECT_ID}
    earthengine authenticate --force

Solution 2 - Si vous n'avez pas de compte:
    Inscrivez-vous sur: https://signup.earthengine.google.com/

Solution 3 - Verifiez votre projet:
    https://console.cloud.google.com/apis/library/earthengine.googleapis.com
        """)
        return None


def get_geotiff_url(image, geometry, filename, scale=30):
    """Genere l'URL de telechargement GeoTIFF"""
    try:
        url = image.getDownloadURL({
            'scale': scale,
            'region': geometry,
            'format': 'GeoTIFF',
            'name': filename.replace('.tif', '')
        })
        return url
    except Exception as e:
        st.warning(f"Erreur URL GeoTIFF: {str(e)[:100]}")
        return None


def calculate_change(img1, img2):
    """Calcule le changement entre deux images"""
    try:
        bands1 = img1.bandNames().getInfo()
        bands2 = img2.bandNames().getInfo()
        common_bands = list(set(bands1) & set(bands2))
        if not common_bands:
            return None
        change = img2.select(common_bands).subtract(img1.select(common_bands)).rename('change')
        return change
    except:
        return None


def calculate_indicator(image, sensor_config, indicator_key):
    """Calcule un indicateur (NDVI, NDWI, LST, VCI)"""
    try:
        sensor_name = sensor_config.get('name', 'Sentinel-2')
        bands = sensor_config.get('bands', {})
        band_names = image.bandNames().getInfo()
        
        # ==================== NDVI ====================
        if indicator_key == "NDVI":
            if sensor_name == 'MODIS':
                return image
            
            nir_band = bands.get('nir')
            red_band = bands.get('red')
            
            if nir_band not in band_names or red_band not in band_names:
                return None
                
            ndvi = image.normalizedDifference([nir_band, red_band]).rename('NDVI')
            return ndvi
        
        # ==================== NDWI ====================
        elif indicator_key == "NDWI":
            if sensor_name == 'MODIS':
                return None
            
            green_band = bands.get('green')
            nir_band = bands.get('nir')
            
            if green_band not in band_names or nir_band not in band_names:
                return None
                
            ndwi = image.normalizedDifference([green_band, nir_band]).rename('NDWI')
            return ndwi
        
        # ==================== LST (Land Surface Temperature) ====================
        elif indicator_key == "LST":
            if sensor_name == "Landsat":
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
        
        # ==================== VCI ====================
        elif indicator_key == "VCI":
            # VCI nécessite une approche spécifique (période historique)
            # Cette fonction ne gère que le NDVI de base pour VCI
            if sensor_name == 'MODIS':
                return image
            return None
        
        # ==================== TEMPERATURE (ancien, gardé pour compatibilité) ====================
        elif indicator_key == "Temperature":
            if sensor_name == "Landsat":
                thermal_band = bands.get('thermal', 'ST_B10')
                if thermal_band in band_names:
                    temp = image.select(thermal_band).multiply(0.00341802).add(149.0).rename('temperature')
                    return temp
            return None
            
        return None
        
    except Exception as e:
        st.error(f"Erreur calculate_indicator: {str(e)[:100]}")
        return None


def get_satellite_image(geometry, sensor_config, year, month=None, annual=False, cloud_threshold=20):
    """Recupere une image satellite avec un seuil de nuages personnalisable"""
    try:
        if annual:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        else:
            if month is None:
                month = 6
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year+1}-01-01"
            else:
                end_date = f"{year}-{month+1:02d}-01"
        
        sensor_name = sensor_config.get('name', 'Sentinel-2')
        
        # ==================== MODIS ====================
        if sensor_name == 'MODIS':
            collection = ee.ImageCollection(sensor_config["collection"]) \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date)
            
            size = collection.size().getInfo()
            if size == 0:
                st.warning(f"Aucune image MODIS trouvee pour {start_date} a {end_date}")
                return None, None
            
            image = collection.median().clip(geometry)
            ndvi = image.select('NDVI').rename('NDVI')
            ndvi = ndvi.multiply(0.0001)
            return ndvi, image
        
        # ==================== LANDSAT / SENTINEL-2 ====================
        else:
            collection = ee.ImageCollection(sensor_config["collection"]) \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date)
            
            if sensor_config.get("cloud_filter"):
                cloud_field = sensor_config["cloud_filter"]
                collection = collection.filter(ee.Filter.lt(cloud_field, cloud_threshold))
            
            size = collection.size().getInfo()
            if size == 0:
                # Essayer sans filtre nuages
                collection = ee.ImageCollection(sensor_config["collection"]) \
                    .filterBounds(geometry) \
                    .filterDate(start_date, end_date)
                size = collection.size().getInfo()
                if size == 0:
                    st.warning(f"Aucune image trouvee pour {start_date} a {end_date}")
                    return None, None
            
            image = collection.median().clip(geometry)
            return image, None
            
    except Exception as e:
        st.error(f"Erreur get_satellite_image: {str(e)[:100]}")
        return None, None


def calculate_stats(image, geometry, scale=1000):
    """Calcule les statistiques d'une image sur une geometrie"""
    try:
        # Ajuster l'echelle si la zone est grande
        try:
            area = geometry.area().getInfo()
            if area > 1000000000:  # Plus de 1000 km²
                scale = max(scale, 500)
        except:
            pass
        
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.stdDev(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.min(),
                sharedInputs=True
            ).combine(
                reducer2=ee.Reducer.max(),
                sharedInputs=True
            ),
            geometry=geometry,
            scale=scale,
            bestEffort=True,
            maxPixels=1e9,
            tileScale=4
        )
        
        return stats.getInfo()
        
    except Exception as e:
        st.warning(f"Erreur calculate_stats: {str(e)[:100]}")
        return None


def coords_to_ee_polygon(coords):
    """Convertit des coordonnees en polygone Earth Engine"""
    try:
        if not coords or len(coords) < 3:
            return None
        ee_coords = []
        for coord in coords:
            if len(coord) == 2:
                ee_coords.append([coord[1], coord[0]])
        return ee.Geometry.Polygon(ee_coords)
    except Exception as e:
        return None


def format_area(area_m2):
    """Formate une surface en m² vers une unite lisible"""
    if area_m2 is None:
        return "N/A"
    if area_m2 < 10000:
        return f"{area_m2:.0f} m²"
    elif area_m2 < 1000000:
        return f"{area_m2/10000:.2f} ha"
    else:
        return f"{area_m2/1000000:.2f} km²"